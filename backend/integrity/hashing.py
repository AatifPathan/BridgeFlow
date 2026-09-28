"""
Bridge Flow - Integrity Manager (Phase 7)

Uses hashlib.sha256 (Python standard library) exclusively. No custom
hashing of any kind - integrity verification is a place where "clever"
homemade solutions are actively a red flag, so we lean entirely on a
well-audited standard implementation.

Files are hashed in fixed-size chunks so this works correctly even for
multi-GB files on an 8GB RAM machine - we never load a whole file into
memory just to hash it.
"""

import hashlib
from pathlib import Path

HASH_READ_BLOCK_SIZE = 1024 * 1024  # 1 MB read buffer for hashing


def compute_file_sha256(file_path: Path) -> str:
    """Stream a file through SHA-256 and return the hex digest."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            block = f.read(HASH_READ_BLOCK_SIZE)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()


def verify_file_sha256(file_path: Path, expected_hash: str) -> bool:
    """Returns True if the file's SHA-256 matches expected_hash exactly."""
    actual_hash = compute_file_sha256(file_path)
    return actual_hash.lower() == expected_hash.lower()
