"""
Bridge Flow - Chunk I/O (Phase 5: Chunk-based transfer)

Reads/writes fixed-size chunks directly at their byte offset in a file,
using seek(). This is what makes resume possible: the receiver can
write chunk #340 to its correct position even if chunks 0-339 haven't
all round-tripped yet, and re-requesting a missing chunk later doesn't
disturb anything already on disk.
"""

from pathlib import Path

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


def calculate_total_chunks(file_size: int, chunk_size: int = DEFAULT_CHUNK_SIZE) -> int:
    if file_size == 0:
        return 1
    return (file_size + chunk_size - 1) // chunk_size  # ceiling division


def read_chunk_from_file(file_path: Path, chunk_index: int, chunk_size: int = DEFAULT_CHUNK_SIZE) -> bytes:
    with open(file_path, "rb") as f:
        f.seek(chunk_index * chunk_size)
        return f.read(chunk_size)


def preallocate_file(file_path: Path, total_size: int):
    """Creates a file of the exact final size up front (sparse on most
    filesystems), so out-of-order chunk writes always land at a valid
    offset instead of requiring the file to already be that long."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "wb") as f:
        if total_size > 0:
            f.seek(total_size - 1)
            f.write(b"\0")


def write_chunk_to_file(file_path: Path, chunk_index: int, data: bytes, chunk_size: int = DEFAULT_CHUNK_SIZE):
    with open(file_path, "r+b") as f:
        f.seek(chunk_index * chunk_size)
        f.write(data)
