"""
Bridge Flow - filename and path safety helpers

Windows is stricter than Linux/macOS about file names, and file names that
arrive over the network must never be trusted as paths. These helpers are
deliberately written to work the same on every OS (so they can be unit-tested
anywhere) by treating BOTH "/" and "\\" as path separators.
"""

import os
import re
from pathlib import Path

# Characters Windows forbids in file names (plus control characters).
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL",
                     *[f"COM{i}" for i in range(1, 10)],
                     *[f"LPT{i}" for i in range(1, 10)]}


def sanitize_filename(name: str, fallback: str = "received_file") -> str:
    """
    Reduce a name received from the network to a single safe file name.
    Blocks path traversal ("..\\..\\x", "/etc/x"), strips characters Windows
    rejects, trailing dots/spaces, and reserved device names like CON or NUL.
    """
    name = str(name).replace("\\", "/").split("/")[-1]      # keep last component only
    name = _INVALID_CHARS.sub("_", name).rstrip(" .")
    if not name:
        return fallback
    if name.split(".")[0].strip().upper() in _WINDOWS_RESERVED:
        name = "_" + name
    return name


def unique_path(path: Path) -> Path:
    """Return `path`, or 'name (1).ext', 'name (2).ext'... if it already
    exists, so an incoming file never silently overwrites an existing one."""
    if not path.exists():
        return path
    for i in range(1, 10000):
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not find a free name for {path}")


def clean_user_path(raw: str) -> Path:
    """
    Turn text typed/pasted into the Send page into a Path. Windows Explorer's
    'Copy as path' wraps the path in double quotes, which would otherwise make
    a perfectly valid file look like it doesn't exist.
    """
    text = raw.strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return Path(os.path.expandvars(os.path.expanduser(text)))
