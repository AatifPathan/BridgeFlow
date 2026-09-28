"""
Bridge Flow - FastAPI Application

Kept as a factory function (create_app) rather than a bare module-level
`app = FastAPI()` so tests can spin up fresh instances if needed later.

In production (packaged .exe or `python main.py` after `npm run build`),
this same FastAPI app also serves the built React frontend as static
files, so the whole thing is ONE process on ONE port - no separate
frontend server, no Node.js needed on the machine that runs it.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import routes_devices, routes_pairing, routes_settings, routes_transfers, ws
from utils.resource_path import resource_path


def create_app() -> FastAPI:
    app = FastAPI(title="Bridge Flow API", version="1.0.0")

    # Still allowed for `npm run dev` (Vite on :5173) during active
    # frontend development. Harmless in production since the packaged
    # build talks to itself on the same origin and never hits this path.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_devices.router)
    app.include_router(routes_pairing.router)
    app.include_router(routes_transfers.router)
    app.include_router(routes_settings.router)
    app.include_router(ws.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # Serve the built frontend (frontend/dist, copied to backend/frontend_dist
    # by build_release.py) at "/". Registered LAST so it never shadows an
    # /api or /ws route above - StaticFiles only handles what's left over.
    # If the build hasn't been run yet (plain `python main.py` during
    # backend-only development), this folder won't exist and Bridge Flow
    # simply runs API-only, exactly like before this feature was added.
    frontend_dir = resource_path("frontend_dist")
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app

