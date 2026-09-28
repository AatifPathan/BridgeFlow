# Bridge Flow

**AirDrop-style peer-to-peer file transfer over your local network.**
No cloud, no accounts, no internet required — just two devices on the same Wi-Fi.

Final-year B.Tech CSE project. See `docs/ARCHITECTURE.md` for the full system design.

---

## Two ways to run this

### Option 1 (recommended for demos): one packaged executable, nothing to install

Build a **single file** that bundles the entire app — backend, frontend, Python
interpreter, everything. Copy that one file to any laptop on the same Wi-Fi and
double-click it. The other person needs **zero** technical setup: no Python, no
Node.js, no terminal, no "tech guy."

```bash
python build_release.py
```

This runs `npm install` + `npm run build` for you, bundles the result into the
backend, and produces `dist/BridgeFlow` (or `dist/BridgeFlow.exe` on Windows).
Double-clicking it:
1. Starts the backend (discovery + TCP transfer server + API) on port 8000
2. Opens your default browser straight to the app automatically
3. Stores its database/logs/received files in a `bridgeflow_data/` folder created
   right next to the executable — easy to find, easy to delete/reset

**Important — build this ON each target OS.** PyInstaller doesn't cross-compile:
running `python build_release.py` on Windows produces a `.exe`; running it on
macOS produces a Mac app; running it on Linux produces a Linux binary. If your
final-year demo is on Windows laptops, run the build script on a Windows
machine (with Python + Node installed just for that one build step) and then
hand out the resulting `.exe` — the *other* laptop needs nothing installed.

**You (the developer) still need Python + Node installed to run the build.**
It's the machine that just *runs the finished .exe* that needs nothing.

### Option 2: run from source (for active development)

Two terminals, both machines need Python + Node installed. See "Developer setup"
below — this is what you want while you're still writing code, since it gives
you hot-reload on the frontend instead of a slow rebuild-and-repackage cycle.

---

## What's implemented

| Feature | Status |
|---|---|
| UDP peer discovery | Working, tested with two live instances |
| TCP file/folder transfer | Working |
| Chunked transfer (4MB chunks) | Working |
| Resumable transfers | Working — tested by force-killing a receiver mid-transfer and resuming |
| SHA-256 integrity verification | Working — tested against deliberate corruption |
| ZIP compression (none/standard/max) | Working |
| Secure pairing (code-based trust) | Working — tested end-to-end through the real HTTP API |
| SQLite transfer history | Working |
| FastAPI REST + WebSocket API | Working, all routes tested |
| React frontend (all 6 screens) | Builds cleanly, served by the backend in packaged mode |
| Single-executable packaging | Built and verified — runs with zero installed dependencies |
| Automated tests | 10/10 passing (`pytest tests/`) |

**Known simplifications** (good material for your report's "Challenges" /
"Future Scope" sections):
- Pairing uses trust-on-first-use: the shared encryption key is sent once,
  unencrypted, over the same TCP connection used for code confirmation. A
  stronger design would derive the key from a Diffie-Hellman exchange
  authenticated by the pairing code.
- Incoming transfers currently auto-accept (`AUTO_ACCEPT_TRANSFERS` in
  `tcp_server.py`). A manual Accept/Reject queue is a natural next step.
- The Send page takes a filesystem path as text, not a native file picker —
  the browser UI can't see real OS paths. The packaged app still runs on the
  user's own machine with full disk access, so this is a UI convenience gap,
  not a security one.
- Resuming a sent transfer needs the original archive still present in
  `bridgeflow_data/storage/outgoing/` (packaged mode) or `backend/storage/outgoing/`
  (dev mode).

---

## Project structure

```
bridgeflow/
├── build_release.py           ONE command: builds frontend + packages the .exe
├── backend/
│   ├── main.py                 entry point - discovery + TCP server + API (+ UI once built)
│   ├── config.py                device identity, ports, timing
│   ├── discovery/                 Phase 1: UDP broadcast discovery
│   ├── transfer/                    Phases 2,5,6: protocol, chunking, resume, TCP client/server
│   ├── compression/                  Phase 8: ZIP compression
│   ├── integrity/                     Phase 7: SHA-256
│   ├── security/                       Phase 9: pairing + Fernet encryption
│   ├── database/                        Phase 10: SQLite schema + DAO
│   ├── api/                              FastAPI routers + WebSocket + serves the built UI
│   ├── models/                            Pydantic request/response schemas
│   ├── utils/
│   │   ├── logger.py                       logging
│   │   └── resource_path.py                read-only bundle path vs. writable data path
│   └── tests/                              Phase 12: pytest unit tests
└── frontend/
    └── src/
        ├── pages/                  Dashboard, Devices, Send, Receive, History, Settings
        ├── components/             Sidebar, DeviceCard, ProgressBar
        └── services/                api.js (REST), ws.js (WebSocket), format.js
```

---

## Developer setup (Option 2 — running from source)

You need two devices on the same Wi-Fi to see real peer-to-peer transfer.

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. In dev mode the frontend and backend are two
separate processes (Vite proxies `/api` and `/ws` calls to the backend on
:8000 — see `vite.config.js`) — this is different from the packaged build,
where they're one process on one port.

Do both of the above on both laptops.

### Try it

1. Devices page — wait a few seconds, the other laptop should appear Online.
2. Click Pair. The other laptop's Devices page shows a 6-digit code.
3. Type that code into the confirmation box on your laptop. Both are now trusted.
4. Send — pick the paired device, type a file/folder path, choose compression,
   hit Start transfer.
5. Watch live progress. Check Receive on the other laptop, and History on both.

### Testing resume yourself

Kill the receiving laptop's backend mid-transfer (Ctrl+C or close the terminal/exe).
Restart it, go to History on the sending side, click Resume — it picks up
from the missing chunks instead of starting over.

---

## Verify everything on your own computer (one command)

`selfcheck.py` starts two Bridge Flow instances on your PC and tests the real
flow between them - discovery, pairing, file/folder/compressed transfers,
pasted Windows paths, no-overwrite, and the failure path - printing PASS /
WARN / FAIL for each step. Close any running Bridge Flow first, then:

```powershell
python selfcheck.py                              # tests the source code
python selfcheck.py --exe dist\BridgeFlow.exe     # tests the built exe
```

Click Allow if Windows Firewall asks. A WARN on the discovery step usually
means the firewall blocked UDP broadcasts; everything else still runs.

Settings for running two copies on one PC (used by the script): the environment
variables `BRIDGEFLOW_PORT`, `BRIDGEFLOW_TCP_PORT`, `BRIDGEFLOW_DEVICE_NAME`
and `BRIDGEFLOW_DATA_DIR`.

---

## Running the automated tests

```bash
cd backend
pytest tests/ -v
```

Covers: chunk math (including uneven remainders), out-of-order chunk writes
(proving resume correctness), SHA-256 corruption detection, and ZIP
compress/extract round-trips.

---

## Free/open-source stack used

Python, FastAPI, uvicorn, asyncio/socket (stdlib), SQLite (stdlib sqlite3),
cryptography (Fernet), hashlib (stdlib SHA-256), zipfile (stdlib), React,
Vite, PyInstaller. Nothing here has a paid tier, a usage cap, or a cloud
dependency.
