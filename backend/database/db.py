"""
Bridge Flow - Database Layer (Phase 10)

SQLite, accessed through Python's built-in sqlite3 module. No ORM -
for a schema this small (4 tables), raw SQL is more transparent for a
student project and easier to explain line-by-line in a viva than an
ORM's generated queries would be.

check_same_thread=False is used because our FastAPI app runs async
code and background asyncio tasks (discovery, TCP server) that may all
touch the DB from different points in the event loop; we guard actual
writes with a single asyncio.Lock in db.py's callers where needed.
"""

import sqlite3
from pathlib import Path

from utils.logger import get_logger
from utils.resource_path import writable_data_dir

logger = get_logger("database")

DB_DIR = writable_data_dir() / "storage"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "bridgeflow.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id       TEXT PRIMARY KEY,
    device_name     TEXT NOT NULL,
    last_known_ip   TEXT,
    is_trusted      INTEGER DEFAULT 0,
    shared_key      TEXT,
    first_paired_at TEXT,
    last_seen_at    TEXT
);

CREATE TABLE IF NOT EXISTS transfers (
    transfer_id       TEXT PRIMARY KEY,
    direction         TEXT CHECK(direction IN ('sent','received')),
    peer_device_id    TEXT,
    peer_device_name  TEXT,
    item_name         TEXT NOT NULL,
    item_type         TEXT CHECK(item_type IN ('file','folder')),
    original_size     INTEGER,
    compressed_size   INTEGER,
    compression_mode  TEXT CHECK(compression_mode IN ('none','standard','max')),
    total_chunks      INTEGER,
    chunk_size        INTEGER,
    sha256_expected   TEXT,
    sha256_actual     TEXT,
    status            TEXT CHECK(status IN
                        ('pending','in_progress','paused',
                         'interrupted','resumed','completed','failed','rejected')),
    started_at        TEXT,
    completed_at      TEXT,
    duration_seconds  REAL
);

CREATE TABLE IF NOT EXISTS transfer_chunks (
    transfer_id   TEXT,
    chunk_index   INTEGER,
    is_received   INTEGER DEFAULT 0,
    PRIMARY KEY (transfer_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        logger.info(f"Database ready at {DB_PATH}")
    finally:
        conn.close()
