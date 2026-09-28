"""
Bridge Flow - WebSocket routes

/ws/transfers/{transfer_id} - subscribes to progress_hub events for one
  transfer (percent, speed, ETA, completed/failed/interrupted) so the
  ActiveTransfer screen updates live instead of polling.

/ws/devices - simple periodic push of the live peer table, so the
  Devices screen updates without the user refreshing.
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app_state import discovery_service
from transfer.progress import progress_hub

router = APIRouter()


@router.websocket("/ws/transfers/{transfer_id}")
async def transfer_progress_ws(websocket: WebSocket, transfer_id: str):
    await websocket.accept()
    queue = progress_hub.subscribe(transfer_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("event") in ("completed", "failed", "interrupted"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        progress_hub.unsubscribe(transfer_id, queue)


@router.websocket("/ws/devices")
async def devices_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            peers = [
                {
                    "device_id": p.device_id,
                    "device_name": p.device_name,
                    "ip": p.ip,
                    "online": p.online,
                }
                for p in discovery_service.get_peers()
            ]
            await websocket.send_json({"devices": peers})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
