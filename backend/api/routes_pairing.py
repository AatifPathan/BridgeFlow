"""
Bridge Flow - /api/pairing routes

Maps directly to the two-step handshake in transfer/tcp_client.py and
transfer/tcp_server.py:

  1. This device calls POST /request on a peer it discovered -> the
     PEER generates a code and shows it in ITS OWN UI (via GET /incoming).
  2. The human reads that code and types it into THIS device's UI,
     which calls POST /confirm.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from models.schemas import PairConfirmIn, PairRequestIn
from security import pairing_manager
from transfer import tcp_client

router = APIRouter(prefix="/api/pairing", tags=["pairing"])

UNREACHABLE = ("Couldn't reach {ip}:{port}. Check the IP address, that Bridge Flow is "
               "running there, and that the firewall (and any cloud/router port rule) allows TCP {port}.")


@router.post("/request")
async def request_pairing(body: PairRequestIn):
    try:
        accepted = await tcp_client.request_pairing(body.peer_ip, body.peer_port)
    except (OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=502, detail=UNREACHABLE.format(ip=body.peer_ip, port=body.peer_port))
    if not accepted:
        raise HTTPException(status_code=502, detail="Peer did not accept the pairing request")
    return {"status": "code_requested", "message": "Check the code shown on the other device's screen"}


@router.get("/incoming")
def incoming_requests():
    """Requests where a PEER wants to pair with US - shows the code we
    generated, for the human to relay to the other device's user."""
    return {"requests": pairing_manager.list_pending_incoming_requests()}


@router.post("/confirm")
async def confirm_pairing(body: PairConfirmIn):
    try:
        success = await tcp_client.confirm_pairing(body.peer_ip, body.peer_port, body.code)
    except (OSError, asyncio.TimeoutError):
        raise HTTPException(status_code=502, detail=UNREACHABLE.format(ip=body.peer_ip, port=body.peer_port))
    if not success:
        raise HTTPException(status_code=400, detail="Incorrect or expired pairing code")
    return {"status": "paired"}
