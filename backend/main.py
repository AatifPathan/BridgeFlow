"""
Bridge Flow - Main Application Entry Point

Starts three things as concurrent asyncio tasks inside one process:
  1. UDP discovery service (broadcast + listen for peers)
  2. TCP transfer server (accepts pairing/transfer connections)
  3. FastAPI app, served by uvicorn (REST + WebSocket + the built
     frontend, all from the same port - see api/app.py)

Also opens the default browser to the app once it's up, so someone
double-clicking the packaged .exe with zero technical background
lands straight on the UI with nothing to type or configure.

Run with:
    python main.py
"""

import asyncio
import os
import sys
import threading
import webbrowser

import uvicorn

from api.app import create_app
from app_state import discovery_service
from config import DEVICE_NAME, TCP_TRANSFER_PORT
from database.db import init_db
from transfer.tcp_server import start_tcp_server
from utils.logger import get_logger

# Windows consoles default to a legacy code page; a file name or device name with
# non-English characters would otherwise raise UnicodeEncodeError while logging.
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logger = get_logger("main")

APP_PORT = int(os.environ.get("BRIDGEFLOW_PORT", 8000))


def _open_browser_when_ready():
    """Runs in a background thread so it doesn't block server startup;
    a short delay gives uvicorn time to actually be accepting connections
    before the browser tries to load the page."""
    import time

    time.sleep(1.2)
    try:
        webbrowser.open(f"http://127.0.0.1:{APP_PORT}")
    except Exception:
        # Headless environments (e.g. a server with no display) can't
        # open a browser - that's fine, the API/UI is still reachable
        # manually at the URL logged below.
        pass


async def main():
    init_db()
    logger.info(f"Starting Bridge Flow as '{DEVICE_NAME}'")

    # 1. Discovery (UDP broadcast + listen)
    await discovery_service.start()

    # 2. TCP transfer server (pairing + file transfer)
    tcp_server = await start_tcp_server()
    tcp_server_task = asyncio.create_task(tcp_server.serve_forever())

    # 3. FastAPI (REST + WebSocket + built frontend) via uvicorn
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=APP_PORT, log_level="warning")
    server = uvicorn.Server(config)
    logger.info(f"Bridge Flow running at http://localhost:{APP_PORT}  (API docs at /docs)")
    logger.info(f"TCP transfer server on port {TCP_TRANSFER_PORT}")

    if not os.environ.get("BRIDGEFLOW_NO_BROWSER"):
        threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    try:
        await server.serve()
    finally:
        tcp_server_task.cancel()
        await discovery_service.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[main] shutting down...")
