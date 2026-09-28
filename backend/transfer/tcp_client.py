"""
Bridge Flow - TCP Transfer Client (sender side)

Two responsibilities:
  - request_pairing() / confirm_pairing() - initiate the pairing
    handshake with a discovered-but-untrusted peer.
  - send_transfer() - open an authenticated session and stream a
    file's chunks to a trusted peer, honoring the receiver's
    "missing_chunks" list so a retried/resumed transfer only re-sends
    what's actually missing.
"""

import asyncio

from config import DEVICE_ID, DEVICE_NAME
from database import dao
from transfer import protocol
from transfer.chunk_io import read_chunk_from_file
from transfer.progress import ProgressTracker, progress_hub
from security import pairing_manager
from utils.logger import get_logger

logger = get_logger("tcp_client")

CONNECT_TIMEOUT_SECONDS = 8


async def _connect(peer_ip: str, peer_port: int):
    """Fail fast (8s) if a peer is unreachable, instead of hanging for the
    OS default (~21s on Windows) - important once peers can be on the internet."""
    return await asyncio.wait_for(asyncio.open_connection(peer_ip, peer_port),
                                  timeout=CONNECT_TIMEOUT_SECONDS)


# ---------------------------------------------------------------------
# Pairing (initiator side)
# ---------------------------------------------------------------------

async def request_pairing(peer_ip: str, peer_port: int) -> bool:
    """Step 1: tell the peer we want to pair. Their screen will show a code."""
    reader, writer = await _connect(peer_ip, peer_port)
    try:
        await protocol.send_json(writer, {
            "type": protocol.MSG_PAIR_REQUEST,
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
        })
        response = await protocol.read_json(reader)
        return response.get("type") == protocol.MSG_PAIR_ACCEPTED
    finally:
        await protocol.close_writer(writer)


async def confirm_pairing(peer_ip: str, peer_port: int, code_entered_by_user: str) -> bool:
    """Step 2: submit the code the human read off the peer's screen."""
    reader, writer = await _connect(peer_ip, peer_port)
    try:
        await protocol.send_json(writer, {
            "type": protocol.MSG_PAIR_CONFIRM,
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
            "code": code_entered_by_user,
        })
        response = await protocol.read_json(reader)
        if response.get("type") == protocol.MSG_PAIR_ACCEPTED:
            pairing_manager.store_received_key(
                response["device_id"], response["device_name"], peer_ip, response["shared_key"]
            )
            return True
        return False
    finally:
        await protocol.close_writer(writer)


# ---------------------------------------------------------------------
# Sending a transfer
# ---------------------------------------------------------------------

async def send_transfer(peer_ip: str, peer_port: int, item: dict, peer_device_id: str) -> dict:
    """
    item: the dict produced by transfer.transfer_manager.prepare_outgoing_item()
    Returns a dict summarizing the outcome (status, match, etc).
    """
    transfer_id = item["transfer_id"]

    writer = None
    try:
        reader, writer = await _connect(peer_ip, peer_port)
        await protocol.send_json(writer, {"type": protocol.MSG_AUTH, "device_id": DEVICE_ID})
        auth_response = await protocol.read_json(reader)
        if auth_response.get("type") != protocol.MSG_AUTH_OK:
            logger.error("Peer rejected AUTH - is this device paired?")
            return {"status": "failed", "reason": "auth_rejected"}

        await protocol.send_json(writer, {
            "type": protocol.MSG_TRANSFER_REQUEST,
            "transfer_id": transfer_id,
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
            "item_name": item["item_name"],
            "item_type": item["item_type"],
            "original_size": item["original_size"],
            "compressed_size": item.get("compressed_size"),
            "compression_mode": item["compression_mode"],
            "total_chunks": item["total_chunks"],
            "chunk_size": item["chunk_size"],
            "sha256_expected": item["sha256_expected"],
        })

        accept_response = await protocol.read_json(reader)
        if accept_response.get("type") != protocol.MSG_TRANSFER_ACCEPT:
            return {"status": "rejected"}

        chunks_to_send = accept_response["missing_chunks"]
        logger.info(f"Sending {len(chunks_to_send)}/{item['total_chunks']} chunks "
                    f"({'resume' if accept_response['resume'] else 'new'} transfer)")

        tracker = ProgressTracker(total_bytes=item.get("compressed_size") or item["original_size"])
        already_sent_bytes = (item["total_chunks"] - len(chunks_to_send)) * item["chunk_size"]
        tracker.update(already_sent_bytes)

        for chunk_index in chunks_to_send:
            data = read_chunk_from_file(item["send_path"], chunk_index, item["chunk_size"])
            await protocol.send_chunk(writer, chunk_index, data)

            tracker.update(tracker.bytes_done + len(data))
            progress_hub.publish(transfer_id, {"event": "progress", **tracker.snapshot()})

        await protocol.send_json(writer, {"type": protocol.MSG_TRANSFER_COMPLETE, "transfer_id": transfer_id})

        verify_response = await protocol.read_json(reader)
        match = verify_response.get("match", False)

        status = "completed" if match else "failed"
        dao.update_transfer_status(transfer_id, status)
        progress_hub.publish(transfer_id, {"event": status, "match": match})

        return {"status": status, "match": match}

    except (OSError, asyncio.IncompleteReadError, asyncio.TimeoutError) as e:
        logger.warning(f"Transfer {transfer_id[:8]}... interrupted: {e}")
        dao.update_transfer_status(transfer_id, "interrupted")
        progress_hub.publish(transfer_id, {"event": "interrupted"})
        return {"status": "interrupted"}
    finally:
        if writer is not None:
            await protocol.close_writer(writer)
