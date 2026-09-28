"""
Bridge Flow - Unit tests for the core, network-independent logic:
chunk math, SHA-256 hashing, and ZIP compression/extraction round-trips.

Run with:  pytest tests/test_core.py -v
"""

import os
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from compression.compression_manager import compress_to_zip, extract_zip
from integrity.hashing import compute_file_sha256, verify_file_sha256
from transfer.chunk_io import (
    DEFAULT_CHUNK_SIZE,
    calculate_total_chunks,
    preallocate_file,
    read_chunk_from_file,
    write_chunk_to_file,
)


@pytest.fixture
def tmp_file(tmp_path):
    path = tmp_path / "sample.bin"
    path.write_bytes(os.urandom(10 * 1024 * 1024 + 1234))  # not a round chunk multiple
    return path


# ---------------------------------------------------------------------
# Chunk math (Phase 5)
# ---------------------------------------------------------------------

def test_calculate_total_chunks_exact_multiple():
    assert calculate_total_chunks(8 * 1024 * 1024, chunk_size=4 * 1024 * 1024) == 2


def test_calculate_total_chunks_with_remainder():
    # 10MB + a bit, 4MB chunks -> should round UP to 3 chunks, not truncate to 2
    assert calculate_total_chunks(10 * 1024 * 1024 + 1, chunk_size=4 * 1024 * 1024) == 3


def test_calculate_total_chunks_empty_file():
    assert calculate_total_chunks(0) == 1


# ---------------------------------------------------------------------
# Chunk I/O + resume correctness (Phase 5 / 6)
# ---------------------------------------------------------------------

def test_chunk_roundtrip_preserves_bytes_exactly(tmp_file, tmp_path):
    chunk_size = 3 * 1024 * 1024
    total_size = tmp_file.stat().st_size
    total_chunks = calculate_total_chunks(total_size, chunk_size)

    dest = tmp_path / "rebuilt.bin"
    preallocate_file(dest, total_size)

    # Write chunks in REVERSE order on purpose - proves resume/out-of-order
    # writes land at the correct offset regardless of arrival sequence.
    for i in reversed(range(total_chunks)):
        data = read_chunk_from_file(tmp_file, i, chunk_size)
        write_chunk_to_file(dest, i, data, chunk_size)

    assert dest.read_bytes() == tmp_file.read_bytes()


def test_partial_resume_only_needs_missing_chunks(tmp_file, tmp_path):
    """Simulates exactly what tcp_server.py does: write SOME chunks,
    treat the rest as 'missing', then fill only those in, and confirm
    the final file is still byte-identical to the source."""
    chunk_size = 3 * 1024 * 1024
    total_size = tmp_file.stat().st_size
    total_chunks = calculate_total_chunks(total_size, chunk_size)

    dest = tmp_path / "resumed.bin"
    preallocate_file(dest, total_size)

    already_written = set(random.sample(range(total_chunks), k=max(1, total_chunks // 2)))
    for i in already_written:
        write_chunk_to_file(dest, i, read_chunk_from_file(tmp_file, i, chunk_size), chunk_size)

    missing = [i for i in range(total_chunks) if i not in already_written]
    for i in missing:
        write_chunk_to_file(dest, i, read_chunk_from_file(tmp_file, i, chunk_size), chunk_size)

    assert dest.read_bytes() == tmp_file.read_bytes()


# ---------------------------------------------------------------------
# Integrity (Phase 7)
# ---------------------------------------------------------------------

def test_hash_matches_for_identical_content(tmp_file, tmp_path):
    copy = tmp_path / "copy.bin"
    copy.write_bytes(tmp_file.read_bytes())
    assert compute_file_sha256(tmp_file) == compute_file_sha256(copy)


def test_hash_detects_single_byte_corruption(tmp_file, tmp_path):
    corrupted = tmp_path / "corrupted.bin"
    data = bytearray(tmp_file.read_bytes())
    data[0] ^= 0xFF  # flip one byte
    corrupted.write_bytes(bytes(data))

    expected = compute_file_sha256(tmp_file)
    assert verify_file_sha256(corrupted, expected) is False


def test_verify_file_sha256_true_for_untouched_file(tmp_file):
    expected = compute_file_sha256(tmp_file)
    assert verify_file_sha256(tmp_file, expected) is True


# ---------------------------------------------------------------------
# Compression round-trip (Phase 8)
# ---------------------------------------------------------------------

def test_compress_and_extract_folder_preserves_structure(tmp_path):
    source = tmp_path / "project"
    (source / "src").mkdir(parents=True)
    (source / "src" / "main.py").write_text("print('hi')")
    (source / "README.md").write_text("hello")

    archive = tmp_path / "out.zip"
    result = compress_to_zip(source, archive, mode="standard")
    assert result.archive_path.exists()
    assert result.original_size > 0

    extracted_root = tmp_path / "extracted"
    extract_zip(archive, extracted_root)

    assert (extracted_root / "project" / "src" / "main.py").read_text() == "print('hi')"
    assert (extracted_root / "project" / "README.md").read_text() == "hello"


def test_compression_mode_none_still_produces_valid_archive(tmp_path):
    source = tmp_path / "file.txt"
    source.write_text("some content")
    archive = tmp_path / "file.zip"

    result = compress_to_zip(source, archive, mode="none")
    extracted_root = tmp_path / "extracted"
    extract_zip(archive, extracted_root)

    assert (extracted_root / "file.txt").read_text() == "some content"
