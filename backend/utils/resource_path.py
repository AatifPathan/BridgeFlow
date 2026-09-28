"""
Bridge Flow - Resource Path Resolver

Two different needs, two different functions - conflating them is a
common and nasty bug in packaged apps:

  - resource_path(): READ-ONLY files shipped WITH the app (the built
    frontend). When PyInstaller bundles this into a single executable,
    these are extracted at runtime into a temporary folder exposed as
    `sys._MEIPASS`, which is wiped after the app closes.

  - writable_data_dir(): where the app's OWN data lives (database,
    logs, received files, device identity). This must NOT be
    `sys._MEIPASS` - that folder is temporary and read-only-ish by
    convention. Instead we use the folder the .exe itself sits in, so
    a user's paired devices and transfer history survive between runs
    and are easy to find (right next to the app, in `bridgeflow_data/`).
"""

import os
import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent  # backend/
    return base_path / relative_path


def writable_data_dir() -> Path:
    override = os.environ.get("BRIDGEFLOW_DATA_DIR")
    if override:
        base = Path(override)
        base.mkdir(parents=True, exist_ok=True)
        return base
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent / "bridgeflow_data"
    else:
        base = Path(__file__).parent.parent  # backend/ - matches pre-packaging layout
    base.mkdir(parents=True, exist_ok=True)
    return base
