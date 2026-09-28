"""
Bridge Flow - Centralized logging configuration.

Every module gets its own named logger (e.g. "bridgeflow.transfer") so
log lines are traceable to the module that produced them, and the
format/handlers are configured in exactly one place.
"""

import logging
import sys
from pathlib import Path

from utils.resource_path import writable_data_dir

LOG_DIR = writable_data_dir() / "storage" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "bridgeflow.log"

_configured = False


def setup_logging(level=logging.INFO):
    global _configured
    if _configured:
        return
    _configured = True

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger("bridgeflow")
    root.setLevel(level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Use as: logger = get_logger(__name__)"""
    setup_logging()
    return logging.getLogger(f"bridgeflow.{name}")
