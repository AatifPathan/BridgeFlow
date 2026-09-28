"""
Bridge Flow - Release Builder

Produces a single double-clickable executable with NOTHING else needed
on the machine that runs it - no Python, no Node.js, no pip/npm install.

What it does, in order:
  1. `npm install` + `npm run build` in frontend/       -> frontend/dist
  2. Copies frontend/dist into backend/frontend_dist     (see api/app.py,
     which serves this folder as the UI once it exists)
  3. Runs PyInstaller in --onefile mode on backend/main.py, bundling
     frontend_dist as data so it ships inside the .exe

Run from the project root:
    python build_release.py

Output: dist/BridgeFlow(.exe) - copy this ONE file to any Windows/Mac/
Linux machine on the same Wi-Fi and double-click it. Nothing to install.

IMPORTANT: PyInstaller does NOT cross-compile. Run this script ON each
target OS to get that OS's executable (run it on Windows for a .exe, on
macOS for a Mac app, on Linux for a Linux binary).
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
FRONTEND_DIR = ROOT / "frontend"
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
BUNDLED_FRONTEND = BACKEND_DIR / "frontend_dist"


def run(cmd, cwd=None):
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"\nFAILED: {' '.join(cmd)}")
        sys.exit(result.returncode)


def install_python_requirements():
    print("=== Step 0/3: Installing Python dependencies ===")
    # PyInstaller only bundles libraries installed in THIS Python. If
    # uvicorn/fastapi are missing here, the .exe builds "successfully" but
    # crashes on launch with "No module named 'uvicorn'".
    req = BACKEND_DIR / "requirements.txt"
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req)])
    if result.returncode != 0:
        print("pip reported a problem - checking whether the needed modules exist anyway...")

    missing = []
    for module in ("fastapi", "uvicorn", "pydantic", "cryptography", "websockets"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        print(f"\nMissing Python packages: {', '.join(missing)}")
        print("Run:  pip install -r backend/requirements.txt   then re-run this script.")
        sys.exit(1)


def build_frontend():
    print("=== Step 1/3: Building frontend ===")
    npm = "npm.cmd" if platform.system() == "Windows" else "npm"
    run([npm, "install"], cwd=FRONTEND_DIR)
    run([npm, "run", "build"], cwd=FRONTEND_DIR)

    if not FRONTEND_DIST.exists():
        print("frontend/dist was not created - check the build output above.")
        sys.exit(1)


def bundle_frontend_into_backend():
    print("\n=== Step 2/3: Copying frontend build into backend/ ===")
    if BUNDLED_FRONTEND.exists():
        shutil.rmtree(BUNDLED_FRONTEND)
    shutil.copytree(FRONTEND_DIST, BUNDLED_FRONTEND)
    print(f"Copied {FRONTEND_DIST} -> {BUNDLED_FRONTEND}")


def build_executable():
    print("\n=== Step 3/3: Packaging with PyInstaller ===")
    # PyInstaller's --add-data separator differs by OS: ';' on Windows, ':' elsewhere.
    # Using an ABSOLUTE source path here (not a relative one) avoids
    # ambiguity between the subprocess's cwd and --specpath, which
    # otherwise resolve relative paths differently across PyInstaller
    # versions/platforms.
    sep = ";" if platform.system() == "Windows" else ":"
    add_data = f"{BUNDLED_FRONTEND}{sep}frontend_dist"

    run([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "BridgeFlow",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT),
        "--add-data", add_data,
        # uvicorn/websockets pick their implementation dynamically at
        # import time, which PyInstaller's static analysis can miss -
        # spelling these out avoids a "module not found" crash at
        # runtime that only shows up on a machine without dev tools
        # installed to debug it.
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan.on",
        "--collect-submodules", "uvicorn",
        "--hidden-import", "websockets",
        "main.py",
    ], cwd=BACKEND_DIR)


if __name__ == "__main__":
    install_python_requirements()
    build_frontend()
    bundle_frontend_into_backend()
    build_executable()

    exe_name = "BridgeFlow.exe" if platform.system() == "Windows" else "BridgeFlow"
    print(f"\nDone. Find it at: dist/{exe_name}")
    print("Copy that one file to any machine on the same Wi-Fi and double-click it.")
