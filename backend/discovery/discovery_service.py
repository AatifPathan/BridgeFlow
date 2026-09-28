"""
Bridge Flow - Phase 1: UDP Discovery Service

Two responsibilities, kept deliberately separate from everything else
in the app (no transfer logic, no UI, no database here):

1. Periodically BROADCAST an "ANNOUNCE" UDP packet so other Bridge Flow
   instances on the same LAN know we exist.
2. LISTEN for ANNOUNCE packets from other instances and maintain a live
   in-memory peer table (added / updated / marked offline).

Why UDP broadcast: discovery doesn't need reliable delivery. If one
ANNOUNCE packet is lost, the next one (a few seconds later) corrects it.
Using TCP here would require already knowing who to connect to - which
is exactly the problem discovery is solving. UDP broadcast is the
standard, correct tool for "find things on my LAN I don't know about yet".
"""

import asyncio
import json
import socket
import time
from dataclasses import dataclass, field

from config import (
    ANNOUNCE_INTERVAL_SECONDS,
    DEVICE_ID,
    DEVICE_NAME,
    OFFLINE_TIMEOUT_SECONDS,
    TCP_TRANSFER_PORT,
    UDP_DISCOVERY_PORT,
)


def _broadcast_targets() -> list[str]:
    """
    Where to send ANNOUNCE packets:
      - 255.255.255.255 (limited broadcast) - works on most networks, but on
        Windows it only leaves through ONE network adapter, which may be a
        VPN or virtual adapter rather than your Wi-Fi.
      - x.y.z.255 for this machine's LAN (subnet-directed broadcast, assumes
        a /24 network, which covers typical home/hotspot/college Wi-Fi) so
        the packet definitely goes out the Wi-Fi adapter.
    Recomputed on every broadcast so switching networks keeps working.
    """
    targets = ["255.255.255.255"]
    try:
        # connect() on a UDP socket sends nothing; it just makes the OS pick
        # the outgoing interface, whose IP we then read back.
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))
        local_ip = probe.getsockname()[0]
        probe.close()
        parts = local_ip.split(".")
        if len(parts) == 4 and not local_ip.startswith(("127.", "0.")):
            targets.append(".".join(parts[:3] + ["255"]))
    except OSError:
        pass
    return targets


@dataclass
class PeerInfo:
    device_id: str
    device_name: str
    ip: str
    tcp_port: int
    last_seen: float = field(default_factory=time.time)
    online: bool = True

    def seconds_since_seen(self) -> float:
        return time.time() - self.last_seen


class _DiscoveryProtocol(asyncio.DatagramProtocol):
    """
    Low-level asyncio UDP protocol handler. Kept separate from
    DiscoveryService so the "how asyncio delivers packets" concern is
    isolated from "what we do with the peer table" concern.
    """

    def __init__(self, on_message):
        super().__init__()
        self._on_message = on_message

    def datagram_received(self, data: bytes, addr):
        sender_ip = addr[0]
        try:
            message = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return  # ignore malformed/foreign UDP traffic on this port
        self._on_message(message, sender_ip)

    def error_received(self, exc):
        print(f"[discovery] UDP error: {exc}")


class DiscoveryService:
    def __init__(self):
        self.peers: dict[str, PeerInfo] = {}
        self._transport: asyncio.DatagramTransport | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Bind the UDP socket and start the broadcast + sweep loops."""
        loop = asyncio.get_running_loop()

        raw_sock = self._create_broadcast_socket()

        self._transport, _protocol = await loop.create_datagram_endpoint(
            lambda: _DiscoveryProtocol(self._handle_message),
            sock=raw_sock,
        )

        self._running = True
        print(f"[discovery] listening on UDP {UDP_DISCOVERY_PORT} "
              f"as '{DEVICE_NAME}' ({DEVICE_ID[:8]}...)")

        # Run broadcasting and stale-peer sweeping concurrently.
        asyncio.create_task(self._broadcast_loop())
        asyncio.create_task(self._sweep_loop())

    async def stop(self):
        """Send a GOODBYE so peers update instantly, then close the socket."""
        if self._transport:
            self._send_message({"type": "GOODBYE", "device_id": DEVICE_ID})
            self._transport.close()
        self._running = False

    # ------------------------------------------------------------------
    # Socket setup
    # ------------------------------------------------------------------

    @staticmethod
    def _create_broadcast_socket() -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # SO_REUSEPORT lets two Bridge Flow instances run on the SAME
        # machine during local testing (both bind the same port).
        # Not available on Windows - safe to skip there.
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Windows-only: without this, an ICMP "port unreachable" reply to one of
        # our broadcasts makes later reads fail with WinError 10054.
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            try:
                sock.ioctl(socket.SIO_UDP_CONNRESET, False)
            except (OSError, ValueError):
                pass
        sock.bind(("", UDP_DISCOVERY_PORT))
        sock.setblocking(False)
        return sock

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def _send_message(self, message: dict):
        if not self._transport:
            return
        payload = json.dumps(message).encode("utf-8")
        # NOTE: the string "<broadcast>" is a Python-socket-only alias. asyncio's
        # Windows transport hands the address straight to the OS, which rejects
        # it (WinError 10022). Real IPs work on every platform.
        for target in _broadcast_targets():
            try:
                self._transport.sendto(payload, (target, UDP_DISCOVERY_PORT))
            except OSError:
                pass  # e.g. no route on that interface - try the next target

    async def _broadcast_loop(self):
        while self._running:
            self._send_message({
                "type": "ANNOUNCE",
                "device_id": DEVICE_ID,
                "device_name": DEVICE_NAME,
                "tcp_port": TCP_TRANSFER_PORT,
                "timestamp": time.time(),
            })
            await asyncio.sleep(ANNOUNCE_INTERVAL_SECONDS)

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------

    def _handle_message(self, message: dict, sender_ip: str):
        msg_type = message.get("type")
        device_id = message.get("device_id")

        if not device_id or device_id == DEVICE_ID:
            return  # ignore our own broadcasts

        if msg_type == "ANNOUNCE":
            self.peers[device_id] = PeerInfo(
                device_id=device_id,
                device_name=message.get("device_name", "Unknown"),
                ip=sender_ip,
                tcp_port=message.get("tcp_port", TCP_TRANSFER_PORT),
                last_seen=time.time(),
                online=True,
            )

        elif msg_type == "GOODBYE":
            if device_id in self.peers:
                self.peers[device_id].online = False

    # ------------------------------------------------------------------
    # Stale-peer sweeping
    # ------------------------------------------------------------------

    async def _sweep_loop(self):
        while self._running:
            for peer in self.peers.values():
                if peer.online and peer.seconds_since_seen() > OFFLINE_TIMEOUT_SECONDS:
                    peer.online = False
            await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # Public read access (used by main.py now, by the API layer later)
    # ------------------------------------------------------------------

    def get_peers(self) -> list[PeerInfo]:
        return list(self.peers.values())
