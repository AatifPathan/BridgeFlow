"""
Bridge Flow - TCP Transfer Server (receiver side)

Handles three kinds of incoming TCP connections, distinguished by the
first JSON message's "type":
  - PAIR_REQUEST / PAIR_CONFIRM  -> security/pairing_manager.py
  - AUTH + TRANSFER_REQUEST      -> accepts/resumes a file transfer

Resume logic lives here: if a TRANSFER_REQUEST arrives for a
transfer_id we already have a partial record of, we tell the sender
exactly which chunk indices are still missing instead of starting over.
"""

import asyncio
import os
import uuid
from pathlib import Path

from config import DEVICE_ID, DEVICE_NAME, TCP_TRANSFER_PORT
from database import dao
from integrity.hashing import compute_file_sha256
from security import pairing_manager
from transfer import protocol
from transfer.chunk_io import preallocate_file, write_chunk_to_file
from transfer.progress import ProgressTracker, progress_hub
from compression.compression_manager import extract_zip
from utils.logger import get_logger
from utils.filenames import sanitize_filename, unique_path
from utils.resource_path import writable_data_dir

logger = get_logger("tcp_server")

RECEIVED_DIR = writable_data_dir() / "storage" / "received"
INCOMING_DIR = writable_data_dir() / "storage" / "incoming"  # raw archive landing zone
RECEIVED_DIR.mkdir(parents=True, exist_ok=True)
INCOMING_DIR.mkdir(parents=True, exist_ok=True)

# Auto-accept incoming transfers for now (a manual accept/reject queue,
# mirroring pairing_manager's pattern, is a natural extension for the
# "Receive" screen's Accept/Reject buttons).
AUTO_ACCEPT_TRANSFERS = True


async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer_ip = writer.get_extra_info("peername")[0]
    try:
        first_message = await protocol.read_json(reader)
        msg_type = first_message.get("type")

        if msg_type == protocol.MSG_PAIR_REQUEST:
            await _handle_pair_request(reader, writer, first_message, peer_ip)
        elif msg_type == protocol.MSG_PAIR_CONFIRM:
            await _handle_pair_confirm(reader, writer, first_message, peer_ip)
        elif msg_type == protocol.MSG_AUTH:
            await _handle_authenticated_session(reader, writer, first_message, peer_ip)
        else:
            logger.warning(f"Unknown first message type from {peer_ip}: {msg_type}")

    except (asyncio.IncompleteReadError, ConnectionResetError):
        logger.info(f"Connection from {peer_ip} closed/reset (may be normal, e.g. mid-transfer drop)")
    except Exception as e:
        logger.exception(f"Error handling connection from {peer_ip}: {e}")
    finally:
        await protocol.close_writer(writer)


# ---------------------------------------------------------------------
# Pairing
# ---------------------------------------------------------------------

async def _handle_pair_request(reader, writer, message, peer_ip):
    device_id = message["device_id"]
    device_name = message["device_name"]
    code = pairing_manager.generate_pairing_code(device_id)
    if code is None:  # rate limited
        await protocol.send_json(writer, {"type": protocol.MSG_PAIR_REJECTED})
        return

    # In the full app, the Devices/Pairing UI polls or gets pushed this
    # code via the API layer. For now we also print it so this is
    # demoable purely from the console/logs.
    print(f"\n>>> PAIRING REQUEST from '{device_name}' ({peer_ip})")
    print(f">>> Enter this code on the OTHER device to confirm pairing: {code}\n")

    await protocol.send_json(writer, {"type": protocol.MSG_PAIR_ACCEPTED})


async def _handle_pair_confirm(reader, writer, message, peer_ip):
    device_id = message["device_id"]
    device_name = message["device_name"]
    submitted_code = message["code"]

    if pairing_manager.verify_pairing_code(device_id, submitted_code):
        shared_key = pairing_manager.complete_pairing(device_id, device_name, peer_ip)
        await protocol.send_json(writer, {
            "type": protocol.MSG_PAIR_ACCEPTED,
            "shared_key": shared_key,
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
        })
        logger.info(f"Paired successfully with {device_name}")
    else:
        await protocol.send_json(writer, {"type": protocol.MSG_PAIR_REJECTED})
        logger.warning(f"Pairing code mismatch/expired for {device_name}")


# ---------------------------------------------------------------------
# Authenticated transfer session
# ---------------------------------------------------------------------

async def _handle_authenticated_session(reader, writer, message, peer_ip):
    device_id = message["device_id"]

    if not dao.is_trusted(device_id):
        await protocol.send_json(writer, {"type": protocol.MSG_AUTH_REJECT})
        logger.warning(f"Rejected untrusted device {device_id[:8]}... ({peer_ip})")
        return

    await protocol.send_json(writer, {"type": protocol.MSG_AUTH_OK})

    request = await protocol.read_json(reader)
    if request.get("type") != protocol.MSG_TRANSFER_REQUEST:
        return

    await _handle_transfer_request(reader, writer, request, device_id, peer_ip)


async def _handle_transfer_request(reader, writer, request, device_id, peer_ip):
    # transfer_id and item_name come from the network and end up in file
    # paths - validate/sanitize them so a peer can't write outside our folders.
    try:
        transfer_id = str(uuid.UUID(str(request["transfer_id"])))
    except ValueError:
        logger.warning(f"Rejected transfer with invalid transfer_id from {peer_ip}")
        return
    item_name = sanitize_filename(request["item_name"])
    request["transfer_id"] = transfer_id
    request["item_name"] = item_name
    total_chunks = request["total_chunks"]
    chunk_size = request["chunk_size"]

    existing = dao.get_transfer(transfer_id)
    is_resume = existing is not None and existing["status"] in ("interrupted", "in_progress", "paused")

    dest_filename = f"{transfer_id}__{item_name}"
    dest_path = INCOMING_DIR / dest_filename

    if is_resume:
        missing_chunks = dao.get_missing_chunks(transfer_id)
        logger.info(f"Resuming transfer {transfer_id[:8]}... - {len(missing_chunks)} chunks missing")
    else:
        if not AUTO_ACCEPT_TRANSFERS:
            await protocol.send_json(writer, {"type": protocol.MSG_TRANSFER_REJECT})
            return

        preallocate_file(dest_path, request["original_size"] if request["compression_mode"] == "none"
                          else request["compressed_size"])
        dao.create_transfer({
            "transfer_id": transfer_id,
            "direction": "received",
            "peer_device_id": device_id,
            "peer_device_name": request.get("device_name", "Unknown"),
            "item_name": item_name,
            "item_type": request["item_type"],
            "original_size": request["original_size"],
            "compressed_size": request.get("compressed_size"),
            "compression_mode": request["compression_mode"],
            "total_chunks": total_chunks,
            "chunk_size": chunk_size,
            "sha256_expected": request["sha256_expected"],
            "status": "in_progress",
        })
        missing_chunks = list(range(total_chunks))

    await protocol.send_json(writer, {
        "type": protocol.MSG_TRANSFER_ACCEPT,
        "resume": is_resume,
        "missing_chunks": missing_chunks,
    })

    tracker = ProgressTracker(total_bytes=request.get("compressed_size") or request["original_size"])
    tracker.update((total_chunks - len(missing_chunks)) * chunk_size)

    # Receive exactly the chunks we told the sender we're missing.
    for _ in missing_chunks:
        chunk_index, data = await protocol.read_chunk(reader)
        write_chunk_to_file(dest_path, chunk_index, data, chunk_size)
        dao.mark_chunk_received(transfer_id, chunk_index)

        tracker.update(dao.count_received_chunks(transfer_id) * chunk_size)
        progress_hub.publish(transfer_id, {"event": "progress", **tracker.snapshot()})

        # Test-only hook: artificially slow chunk writes so an interrupted
        # transfer can be reproduced deterministically (see README_PHASE_RESUME.md).
        if os.environ.get("DATABRIDGE_TEST_SLOW_CHUNKS"):
            await asyncio.sleep(float(os.environ["DATABRIDGE_TEST_SLOW_CHUNKS"]))

    complete_msg = await protocol.read_json(reader)
    if complete_msg.get("type") != protocol.MSG_TRANSFER_COMPLETE:
        return

    await _finalize_received_transfer(transfer_id, dest_path, request, writer)


async def _finalize_received_transfer(transfer_id, dest_path, request, writer):
    expected_hash = request["sha256_expected"]
    actual_hash = compute_file_sha256(dest_path)
    match = actual_hash.lower() == expected_hash.lower()

    await protocol.send_json(writer, {"type": protocol.MSG_VERIFY_RESULT, "match": match})

    if not match:
        dao.update_transfer_status(transfer_id, "failed", sha256_actual=actual_hash)
        progress_hub.publish(transfer_id, {"event": "failed", "reason": "hash_mismatch"})
        logger.error(f"Transfer {transfer_id[:8]}... FAILED hash verification")
        return

    was_zipped = request["item_type"] == "folder" or request["compression_mode"] != "none"
    if was_zipped:
        # The zip already contains the right top-level folder name for
        # folder sends (compression_manager prefixes entries with the
        # source folder's name), or just the bare filename for a
        # compressed single file - so we extract straight into
        # RECEIVED_DIR rather than into an extra named subfolder,
        # otherwise folders end up double-nested (received/x/x/...).
        try:
            extract_zip(dest_path, RECEIVED_DIR)
        except Exception as e:
            # Hash matched (the bytes are intact) but unpacking failed, e.g.
            # a permissions problem or an invalid file name on this OS.
            logger.exception(f"Transfer {transfer_id[:8]}... received OK but extraction failed: {e}")
            dao.update_transfer_status(transfer_id, "failed", sha256_actual=actual_hash)
            progress_hub.publish(transfer_id, {"event": "failed", "reason": f"extraction failed: {e}"})
            return
        # The archive was only a transport container - the user wants the
        # extracted files, so don't leave a duplicate copy on disk.
        try:
            dest_path.unlink()
        except OSError:
            pass
    else:
        # Never overwrite an existing file of the same name.
        final_path = unique_path(RECEIVED_DIR / request["item_name"])
        try:
            dest_path.replace(final_path)
        except OSError as e:
            logger.exception(f"Transfer {transfer_id[:8]}... received OK but saving failed: {e}")
            dao.update_transfer_status(transfer_id, "failed", sha256_actual=actual_hash)
            progress_hub.publish(transfer_id, {"event": "failed", "reason": f"saving failed: {e}"})
            return

    dao.update_transfer_status(transfer_id, "completed", sha256_actual=actual_hash)
    progress_hub.publish(transfer_id, {"event": "completed", "match": True})
    logger.info(f"Transfer {transfer_id[:8]}... completed and verified")


# ---------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------

async def start_tcp_server():
    server = await asyncio.start_server(handle_connection, host="0.0.0.0", port=TCP_TRANSFER_PORT)
    logger.info(f"TCP transfer server listening on port {TCP_TRANSFER_PORT}")
    return server
