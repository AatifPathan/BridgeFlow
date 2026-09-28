"""
Bridge Flow - /api/devices routes

Merges two sources of truth:
  - discovery_service.get_peers() - who's currently reachable on the LAN
  - database.dao.list_devices()   - who we've ever paired with (may be
    offline right now, but still shown so Send can target a known
    device even if discovery hasn't refreshed yet)
"""

from fastapi import APIRouter

from app_state import discovery_service
from database import dao

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("")
def list_devices():
    live_peers = {p.device_id: p for p in discovery_service.get_peers()}
    known_devices = {d["device_id"]: d for d in dao.list_devices()}

    merged = {}
    for device_id, peer in live_peers.items():
        merged[device_id] = {
            "device_id": device_id,
            "device_name": peer.device_name,
            "ip": peer.ip,
            "tcp_port": peer.tcp_port,
            "online": peer.online,
            "is_trusted": dao.is_trusted(device_id),
        }
    for device_id, device in known_devices.items():
        if device_id not in merged:
            merged[device_id] = {
                "device_id": device_id,
                "device_name": device["device_name"],
                "ip": device["last_known_ip"],
                "tcp_port": None,
                "online": False,
                "is_trusted": bool(device["is_trusted"]),
            }

    return {"devices": list(merged.values())}


@router.delete("/{device_id}")
def unpair(device_id: str):
    dao.unpair_device(device_id)
    return {"status": "unpaired", "device_id": device_id}
