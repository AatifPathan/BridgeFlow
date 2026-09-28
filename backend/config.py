"""
Bridge Flow - Configuration
Phase 1: Discovery

Handles device identity (a UUID that persists across restarts) and
the network settings used by the discovery service.
"""

import json
import os
import socket
import uuid
from pathlib import Path

from utils.resource_path import writable_data_dir

# --- Network settings ---------------------------------------------------

UDP_DISCOVERY_PORT = 50999      # port used for broadcast ANNOUNCE/GOODBYE messages
# BRIDGEFLOW_TCP_PORT lets a second copy run on the SAME PC for testing.
TCP_TRANSFER_PORT = int(os.environ.get("BRIDGEFLOW_TCP_PORT", 51000))

ANNOUNCE_INTERVAL_SECONDS = 3   # how often we broadcast our presence
OFFLINE_TIMEOUT_SECONDS = 9     # mark a peer offline if not heard from in this long
                                 # (roughly 3 missed announcements)

# --- Config file location ------------------------------------------------

CONFIG_DIR = writable_data_dir() / "config"
CONFIG_DIR.mkdir(exist_ok=True)
DEVICE_FILE = CONFIG_DIR / "device_identity.json"


def _generate_default_name() -> str:
    """Use the OS hostname as a sensible default device name."""
    try:
        return socket.gethostname()
    except Exception:
        return "BridgeFlow-Device"


def load_or_create_device_identity() -> dict:
    """
    Load this machine's persistent device_id/device_name, or create one
    on first run. This ID must stay the same across restarts so that
    other peers recognize this device consistently (important later for
    pairing/trust in Phase 9).
    """
    if DEVICE_FILE.exists():
        with open(DEVICE_FILE, "r") as f:
            return json.load(f)

    identity = {
        "device_id": str(uuid.uuid4()),
        "device_name": _generate_default_name(),
    }
    with open(DEVICE_FILE, "w") as f:
        json.dump(identity, f, indent=2)

    return identity


# Loaded once at import time and reused everywhere else in the app.
DEVICE_IDENTITY = load_or_create_device_identity()
DEVICE_ID = DEVICE_IDENTITY["device_id"]
# BRIDGEFLOW_DEVICE_NAME overrides the hostname so two test copies on one PC
# show up under different names.
DEVICE_NAME = os.environ.get("BRIDGEFLOW_DEVICE_NAME", DEVICE_IDENTITY["device_name"])
