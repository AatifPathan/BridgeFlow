"""
Bridge Flow - /api/settings routes

A simple key/value store backed by the `settings` table. Only
device_name and download_directory are wired up for now - port
configuration and discovery toggles are natural extensions of this
same pattern.
"""

from fastapi import APIRouter

from config import DEVICE_NAME
from database.db import get_connection
from models.schemas import SettingsIn

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        settings = {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()
    settings.setdefault("device_name", DEVICE_NAME)
    return settings


@router.put("")
def update_settings(body: SettingsIn):
    conn = get_connection()
    try:
        updates = body.model_dump(exclude_none=True)
        for key, value in updates.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
        conn.commit()
    finally:
        conn.close()
    return {"status": "updated"}
