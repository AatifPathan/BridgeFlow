"""
Bridge Flow - Transfer Progress Tracking

Two things live here:
1. ProgressTracker - given bytes transferred so far and elapsed time,
   computes speed (bytes/sec) and ETA. Used by both sender and
   receiver so the UI's numbers are calculated the same way on both ends.
2. ProgressHub - a tiny in-process pub/sub so the TCP transfer code
   (which knows nothing about HTTP/WebSockets) can publish progress
   events, and the FastAPI WebSocket route (which knows nothing about
   sockets/chunking) can subscribe to them. This keeps the two layers
   decoupled, per the modular architecture in the design doc.
"""

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class ProgressTracker:
    total_bytes: int
    started_at: float = field(default_factory=time.time)
    bytes_done: int = 0

    def update(self, bytes_done: int):
        self.bytes_done = bytes_done

    @property
    def percent(self) -> float:
        if self.total_bytes == 0:
            return 100.0
        return round((self.bytes_done / self.total_bytes) * 100, 2)

    @property
    def elapsed_seconds(self) -> float:
        return max(0.001, time.time() - self.started_at)

    @property
    def speed_bytes_per_sec(self) -> float:
        return self.bytes_done / self.elapsed_seconds

    @property
    def eta_seconds(self) -> float:
        remaining = self.total_bytes - self.bytes_done
        speed = self.speed_bytes_per_sec
        if speed <= 0:
            return -1
        return round(remaining / speed, 1)

    def snapshot(self) -> dict:
        return {
            "percent": self.percent,
            "bytes_done": self.bytes_done,
            "total_bytes": self.total_bytes,
            "speed_bytes_per_sec": round(self.speed_bytes_per_sec, 2),
            "eta_seconds": self.eta_seconds,
        }


class ProgressHub:
    """In-process pub/sub keyed by transfer_id. Each WebSocket
    connection subscribes to one transfer_id's queue."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, transfer_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(transfer_id, []).append(queue)
        return queue

    def unsubscribe(self, transfer_id: str, queue: asyncio.Queue):
        if transfer_id in self._subscribers and queue in self._subscribers[transfer_id]:
            self._subscribers[transfer_id].remove(queue)

    def publish(self, transfer_id: str, event: dict):
        for queue in self._subscribers.get(transfer_id, []):
            queue.put_nowait(event)


# One shared instance for the whole app (imported by tcp_server, tcp_client, api/ws.py)
progress_hub = ProgressHub()
