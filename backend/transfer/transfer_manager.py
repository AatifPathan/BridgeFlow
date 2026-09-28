"""
Bridge Flow - Transfer Manager (high-level orchestration)

This is the module the API layer calls into. It ties together the
pipeline described in the project brief:

  SELECT FILE/FOLDER -> OPTIONAL COMPRESSION -> CREATE ARCHIVE
  -> CALCULATE HASH -> SPLIT INTO CHUNKS -> TRANSFER
  -> (receiver: REASSEMBLE -> VERIFY HASH -> EXTRACT IF NEEDED)

Compression/hashing/chunk-planning happens here; the actual byte
streaming happens in transfer/tcp_client.py.
"""

import asyncio
import uuid
from pathlib import Path

from compression.compression_manager import compress_to_zip
from database import dao
from integrity.hashing import compute_file_sha256
from transfer.chunk_io import DEFAULT_CHUNK_SIZE, calculate_total_chunks
from transfer.progress import progress_hub
from transfer.tcp_client import send_transfer
from utils.logger import get_logger
from utils.resource_path import writable_data_dir

logger = get_logger("transfer_manager")

WORK_DIR = writable_data_dir() / "storage" / "outgoing"
WORK_DIR.mkdir(parents=True, exist_ok=True)


def prepare_outgoing_item(source_path: Path, compression_mode: str = "none") -> dict:
    """
    Runs the compress -> hash -> chunk-plan steps and returns everything
    tcp_client.send_transfer() needs. This is intentionally synchronous
    (CPU/disk-bound work) - called from an API route via a thread/async
    wrapper so it doesn't block the event loop during large compress/hash
    operations (see api/routes_transfers.py).
    """
    source_path = Path(source_path)
    item_type = "folder" if source_path.is_dir() else "file"
    transfer_id = str(uuid.uuid4())

    # Folders are always archived (there's no other way to send a tree
    # of files as one stream). Files are archived only if the user opted in.
    needs_archive = item_type == "folder" or compression_mode != "none"

    if needs_archive:
        archive_path = WORK_DIR / f"{transfer_id}.zip"
        result = compress_to_zip(source_path, archive_path, mode=compression_mode)
        send_path = result.archive_path
        original_size = result.original_size
        compressed_size = result.compressed_size
        item_name = f"{source_path.name}.zip"
    else:
        send_path = source_path
        original_size = source_path.stat().st_size
        compressed_size = None
        item_name = source_path.name

    logger.info(f"Hashing {send_path.name}...")
    sha256_expected = compute_file_sha256(send_path)

    chunk_size = DEFAULT_CHUNK_SIZE
    total_chunks = calculate_total_chunks(compressed_size or original_size, chunk_size)

    return {
        "transfer_id": transfer_id,
        "send_path": send_path,
        "item_name": item_name,
        "item_type": item_type,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "compression_mode": compression_mode,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "sha256_expected": sha256_expected,
    }


async def start_send(peer_device_id: str, peer_ip: str, peer_port: int,
                      peer_device_name: str, source_path: Path, compression_mode: str = "none") -> dict:
    # Compression + hashing are CPU/disk-bound and can take a while for
    # large items - run them in a worker thread so they don't block the
    # asyncio event loop (which also needs to keep serving other API
    # requests and WebSocket progress updates while this runs).
    item = await asyncio.to_thread(prepare_outgoing_item, source_path, compression_mode)

    dao.create_transfer({
        "transfer_id": item["transfer_id"],
        "direction": "sent",
        "peer_device_id": peer_device_id,
        "peer_device_name": peer_device_name,
        "item_name": item["item_name"],
        "item_type": item["item_type"],
        "original_size": item["original_size"],
        "compressed_size": item["compressed_size"],
        "compression_mode": item["compression_mode"],
        "total_chunks": item["total_chunks"],
        "chunk_size": item["chunk_size"],
        "sha256_expected": item["sha256_expected"],
        "status": "in_progress",
    })

    # Run the actual network send in the background and return right away
    # with the transfer_id, so the UI can subscribe to live progress WHILE
    # the transfer runs (before this change the API only replied once the
    # whole transfer was over, so progress could never be shown).
    task = asyncio.create_task(_run_send(item, peer_ip, peer_port, peer_device_id))
    _background_tasks.add(task)  # keep a reference so it isn't garbage-collected
    task.add_done_callback(_background_tasks.discard)

    original = item["original_size"]
    compressed = item["compressed_size"]
    saved = max(0, original - compressed) if compressed is not None else 0
    return {
        "transfer_id": item["transfer_id"],
        "status": "in_progress",
        "item_name": item["item_name"],
        "compression_mode": item["compression_mode"],
        "original_size": original,
        "compressed_size": compressed,
        "space_saved_bytes": saved,
        "space_saved_percent": round(saved / original * 100, 2) if compressed is not None and original else 0.0,
    }


_background_tasks: set = set()


def _cleanup_archive(send_path, transfer_id: str):
    """Remove the temporary archive after a completed transfer (it's kept
    while a transfer is interrupted, because Resume needs it)."""
    record = dao.get_transfer(transfer_id)
    send_path = Path(send_path)
    if record and record["status"] == "completed" and send_path.parent == WORK_DIR:
        try:
            send_path.unlink()
        except OSError:
            pass


async def _run_send(item: dict, peer_ip: str, peer_port: int, peer_device_id: str):
    """Runs send_transfer and guarantees the DB row always ends in a
    final state, even for early exits (auth rejected, unexpected errors)."""
    transfer_id = item["transfer_id"]
    try:
        result = await send_transfer(peer_ip, peer_port, item, peer_device_id)
        _cleanup_archive(item["send_path"], transfer_id)
        # send_transfer already records completed/failed/interrupted itself,
        # but returns early (without touching the DB) if the peer rejected
        # us - record that here so the UI never waits forever.
        current = dao.get_transfer(transfer_id)
        if current and current["status"] == "in_progress":
            final_status = "rejected" if result.get("status") == "rejected" else "failed"
            dao.update_transfer_status(transfer_id, final_status)
            progress_hub.publish(transfer_id, {"event": final_status, "reason": result.get("reason", "")})
    except OSError as e:
        logger.warning(f"Transfer {transfer_id[:8]}... network error: {e}")
        dao.update_transfer_status(transfer_id, "interrupted")
        progress_hub.publish(transfer_id, {"event": "interrupted", "reason": str(e)})
    except Exception as e:
        logger.exception(f"Transfer {transfer_id[:8]}... crashed: {e}")
        dao.update_transfer_status(transfer_id, "failed")
        progress_hub.publish(transfer_id, {"event": "failed", "reason": str(e)})


async def resume_send(transfer_id: str, peer_ip: str, peer_port: int, peer_device_id: str) -> dict:
    """
    Resumes a previously interrupted SEND. Requires the original
    outgoing archive/file to still exist in storage/outgoing/ - if the
    user cleared temp files, a resume isn't possible and a fresh send
    is needed instead (this tradeoff is worth a line in the report).
    """
    record = dao.get_transfer(transfer_id)
    if not record:
        raise ValueError(f"Unknown transfer_id: {transfer_id}")

    send_path = WORK_DIR / f"{transfer_id}.zip"
    if not send_path.exists():
        # Wasn't archived (plain file send) - the caller must supply the
        # original path again; not resolvable from DB alone in this
        # simplified design.
        raise FileNotFoundError(
            "Original send file not found for resume. Uncompressed file "
            "sends must be re-initiated with the source path."
        )

    item = {
        "transfer_id": transfer_id,
        "send_path": send_path,
        "item_name": record["item_name"],
        "item_type": record["item_type"],
        "original_size": record["original_size"],
        "compressed_size": record["compressed_size"],
        "compression_mode": record["compression_mode"],
        "chunk_size": record["chunk_size"],
        "total_chunks": record["total_chunks"],
        "sha256_expected": record["sha256_expected"],
    }
    result = await send_transfer(peer_ip, peer_port, item, peer_device_id)
    _cleanup_archive(send_path, transfer_id)
    return {"transfer_id": transfer_id, **result}
