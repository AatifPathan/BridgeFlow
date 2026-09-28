"""
Bridge Flow - /api/transfers routes
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from database import dao
from utils.filenames import clean_user_path
from models.schemas import ResumeTransferIn, SendTransferIn
from transfer import transfer_manager

router = APIRouter(prefix="/api/transfers", tags=["transfers"])


@router.get("")
def list_transfers():
    return {"transfers": dao.list_transfers()}


@router.get("/{transfer_id}")
def get_transfer(transfer_id: str):
    transfer = dao.get_transfer(transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return transfer


@router.post("")
async def send(body: SendTransferIn):
    source = clean_user_path(body.source_path)
    if not source.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {body.source_path}")

    result = await transfer_manager.start_send(
        peer_device_id=body.peer_device_id,
        peer_ip=body.peer_ip,
        peer_port=body.peer_port,
        peer_device_name=body.peer_device_name,
        source_path=source,
        compression_mode=body.compression_mode,
    )
    return result


@router.post("/{transfer_id}/resume")
async def resume(transfer_id: str, body: ResumeTransferIn):
    try:
        result = await transfer_manager.resume_send(
            transfer_id=transfer_id,
            peer_ip=body.peer_ip,
            peer_port=body.peer_port,
            peer_device_id=body.peer_device_id,
        )
        return result
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
