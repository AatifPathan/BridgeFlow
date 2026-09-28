"""
Bridge Flow - API Schemas

Pydantic models define and validate the shape of every request/response
body. FastAPI uses these to auto-generate the /docs OpenAPI page too,
which is handy to show in a viva as "here's the live API contract".
"""

from typing import Literal, Optional

from pydantic import BaseModel


class DeviceOut(BaseModel):
    device_id: str
    device_name: str
    ip: str
    online: bool


class PairRequestIn(BaseModel):
    peer_ip: str
    peer_port: int = 51000


class PairConfirmIn(BaseModel):
    peer_ip: str
    peer_port: int = 51000
    code: str


class SendTransferIn(BaseModel):
    peer_device_id: str
    peer_ip: str
    peer_port: int = 51000
    peer_device_name: str
    source_path: str
    compression_mode: Literal["none", "standard", "max"] = "none"


class ResumeTransferIn(BaseModel):
    transfer_id: str
    peer_ip: str
    peer_port: int = 51000
    peer_device_id: str


class TransferOut(BaseModel):
    transfer_id: str
    direction: str
    peer_device_id: Optional[str] = None
    peer_device_name: Optional[str] = None
    item_name: str
    item_type: str
    original_size: Optional[int] = None
    compressed_size: Optional[int] = None
    compression_mode: Optional[str] = None
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class SettingsIn(BaseModel):
    device_name: Optional[str] = None
    download_directory: Optional[str] = None
