"""
Bridge Flow - Data Access functions

Thin, explicit functions over raw SQL - kept separate from db.py
(connection/schema) so callers never write SQL directly in the
transfer/security/API layers. Each function opens and closes its own
short-lived connection, which is the simplest safe pattern for
SQLite under asyncio (avoids holding one connection across awaits).
"""

import time
from typing import Optional

from database.db import get_connection

# ---------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------

def upsert_device(device_id: str, device_name: str, ip: str):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO devices (device_id, device_name, last_known_ip, last_seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                device_name = excluded.device_name,
                last_known_ip = excluded.last_known_ip,
                last_seen_at = excluded.last_seen_at
            """,
            (device_id, device_name, ip, str(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def set_device_trusted(device_id: str, shared_key: str):
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE devices
            SET is_trusted = 1, shared_key = ?, first_paired_at = ?
            WHERE device_id = ?
            """,
            (shared_key, str(time.time()), device_id),
        )
        conn.commit()
    finally:
        conn.close()


def unpair_device(device_id: str):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE devices SET is_trusted = 0, shared_key = NULL WHERE device_id = ?",
            (device_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_device(device_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_devices() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM devices ORDER BY last_seen_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def is_trusted(device_id: str) -> bool:
    device = get_device(device_id)
    return bool(device and device["is_trusted"])


# ---------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------

def create_transfer(transfer: dict):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO transfers (
                transfer_id, direction, peer_device_id, peer_device_name,
                item_name, item_type, original_size, compressed_size,
                compression_mode, total_chunks, chunk_size,
                sha256_expected, status, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transfer["transfer_id"], transfer["direction"], transfer["peer_device_id"],
                transfer.get("peer_device_name", ""), transfer["item_name"], transfer["item_type"],
                transfer["original_size"], transfer.get("compressed_size"),
                transfer.get("compression_mode", "none"), transfer["total_chunks"],
                transfer["chunk_size"], transfer.get("sha256_expected"),
                transfer.get("status", "pending"), str(time.time()),
            ),
        )
        # Pre-populate chunk tracking rows
        conn.executemany(
            "INSERT INTO transfer_chunks (transfer_id, chunk_index, is_received) VALUES (?, ?, 0)",
            [(transfer["transfer_id"], i) for i in range(transfer["total_chunks"])],
        )
        conn.commit()
    finally:
        conn.close()


def update_transfer_status(transfer_id: str, status: str, **extra_fields):
    conn = get_connection()
    try:
        fields = {"status": status, **extra_fields}
        if status == "completed":
            fields["completed_at"] = str(time.time())
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(
            f"UPDATE transfers SET {set_clause} WHERE transfer_id = ?",
            (*fields.values(), transfer_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_transfer(transfer_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM transfers WHERE transfer_id = ?", (transfer_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_transfers() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM transfers ORDER BY started_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Chunks (resume support)
# ---------------------------------------------------------------------

def mark_chunk_received(transfer_id: str, chunk_index: int):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE transfer_chunks SET is_received = 1 WHERE transfer_id = ? AND chunk_index = ?",
            (transfer_id, chunk_index),
        )
        conn.commit()
    finally:
        conn.close()


def get_missing_chunks(transfer_id: str) -> list[int]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT chunk_index FROM transfer_chunks WHERE transfer_id = ? AND is_received = 0 ORDER BY chunk_index",
            (transfer_id,),
        ).fetchall()
        return [r["chunk_index"] for r in rows]
    finally:
        conn.close()


def count_received_chunks(transfer_id: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM transfer_chunks WHERE transfer_id = ? AND is_received = 1",
            (transfer_id,),
        ).fetchone()
        return row["c"]
    finally:
        conn.close()
