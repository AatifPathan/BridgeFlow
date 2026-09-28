# Bridge Flow — System Architecture & Design Document

**AirDrop-Style Peer-to-Peer LAN File Transfer Platform**
Final-Year B.Tech CSE Project — Architecture Phase (Pre-Implementation)

---

## 1. Final Architecture

Bridge Flow is a **three-tier modular application** running entirely on the local network, with no cloud dependency.

```
┌─────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND (Vite)                    │
│   Dashboard | Devices | Send | Receive | Active | History    │
│                    Settings | Pairing UI                     │
└───────────────────────────┬────────────────────────────────┘
                             │ REST (HTTP) + WebSocket (live progress)
┌───────────────────────────▼────────────────────────────────┐
│                  FASTAPI APPLICATION LAYER                   │
│   Routers: /devices /transfers /pairing /history /settings   │
└───┬───────────┬───────────┬───────────┬───────────┬─────────┘
    │           │           │           │           │
┌───▼───┐   ┌───▼────┐  ┌───▼─────┐ ┌───▼──────┐ ┌──▼──────┐
│Discov- │   │Peer    │  │Transfer │ │Compression│ │Security/│
│ery Mgr │   │Manager │  │Manager  │ │Manager    │ │Pairing  │
│(UDP)   │   │        │  │(TCP)    │ │(ZIP)      │ │Manager  │
└───┬───┘   └───┬────┘  └───┬─────┘ └───┬──────┘ └──┬──────┘
    │           │           │           │            │
    │      ┌────▼───────────▼───────────▼────────────▼───┐
    │      │         Integrity Manager (SHA-256)          │
    │      └────────────────────┬──────────────────────────┘
    │                           │
┌───▼───────────────────────────▼──────────────────────────┐
│                    File Manager (I/O layer)                │
└───────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  SQLite Database   │
                    │ (peers, transfers, │
                    │  history, config)  │
                    └────────────────────┘
```

**Two network channels, deliberately separated:**
- **UDP** — lightweight, connectionless, used *only* for discovery/heartbeat (broadcast doesn't need reliability).
- **TCP** — connection-oriented, ordered, reliable — used for everything that must arrive intact: pairing handshake, transfer metadata, and chunked file data.

This separation is itself a talking point for interviews: you're choosing the right transport per use case rather than defaulting to one protocol everywhere.

---

## 2. Detailed Module Breakdown

### Backend (`backend/`)

| Module | Responsibility |
|---|---|
| `discovery/` | UDP broadcast sender + listener, maintains live peer table, marks devices online/offline via heartbeat timeout |
| `security/` | Pairing handshake, trusted-device store, session token issuance, TLS context setup |
| `transfer/` | Transfer session state machine, chunk scheduler, resume logic, progress/speed calculation |
| `compression/` | Wraps `zipfile`, computes before/after size stats, decides skip-if-already-compressed heuristic |
| `integrity/` | SHA-256 hashing (streamed, not loaded fully into memory), hash comparison |
| `database/` | SQLite connection, schema migrations, DAO/repository functions |
| `models/` | Pydantic schemas (API) + dataclasses (internal domain objects) |
| `api/` | FastAPI routers, WebSocket endpoint for live progress push |
| `utils/` | Logging setup, config loader, path/file-name sanitization |
| `main.py` | App bootstrap: starts FastAPI, starts discovery UDP loop, starts TCP transfer server as background asyncio tasks |

### Frontend (`frontend/src/`)

| Module | Responsibility |
|---|---|
| `pages/` | Dashboard, Devices, Send, Receive, ActiveTransfer, History, Settings |
| `components/` | DeviceCard, ProgressBar, PairingModal, FilePicker, TransferRow |
| `services/` | `api.ts` (REST calls), `ws.ts` (WebSocket client for progress events) |
| `state/` | Lightweight global state (React Context or Zustand) for device list + active transfers |

**Why this separation matters:** each module has one reason to change — discovery logic changing doesn't touch transfer logic, compression swap-out (ZIP → something else later) doesn't touch integrity checking. This is a direct, demonstrable application of the Single Responsibility Principle, worth a slide in your report.

---

## 3. Database Schema (SQLite)

```sql
-- Known/paired devices
CREATE TABLE devices (
    device_id       TEXT PRIMARY KEY,      -- UUID generated on first install
    device_name     TEXT NOT NULL,
    last_known_ip   TEXT,
    is_trusted      INTEGER DEFAULT 0,     -- 0/1
    public_key      TEXT,                  -- for pairing/encryption (see §8)
    first_paired_at TEXT,
    last_seen_at    TEXT
);

-- Transfer sessions (one row per file/folder transfer)
CREATE TABLE transfers (
    transfer_id       TEXT PRIMARY KEY,     -- UUID
    direction         TEXT CHECK(direction IN ('sent','received')),
    peer_device_id    TEXT REFERENCES devices(device_id),
    item_name         TEXT NOT NULL,        -- file or folder name
    item_type         TEXT CHECK(item_type IN ('file','folder')),
    original_size     INTEGER,
    compressed_size   INTEGER,
    compression_mode  TEXT CHECK(compression_mode IN ('none','standard','max')),
    total_chunks      INTEGER,
    chunk_size        INTEGER,
    sha256_expected   TEXT,
    sha256_actual     TEXT,
    status            TEXT CHECK(status IN
                        ('pending','in_progress','paused',
                         'interrupted','resumed','completed','failed')),
    started_at        TEXT,
    completed_at      TEXT,
    duration_seconds  REAL
);

-- Per-chunk tracking, enables resume
CREATE TABLE transfer_chunks (
    transfer_id   TEXT REFERENCES transfers(transfer_id),
    chunk_index   INTEGER,
    is_received   INTEGER DEFAULT 0,      -- 0/1
    chunk_hash    TEXT,                    -- optional per-chunk checksum
    PRIMARY KEY (transfer_id, chunk_index)
);

-- App configuration (single-row or key/value table)
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
```

**Design notes:**
- `transfer_chunks` is the backbone of resumability — on reconnect, the receiver queries `SELECT chunk_index FROM transfer_chunks WHERE transfer_id=? AND is_received=0` and only those chunks are re-requested.
- Storing `sha256_expected` (sender-computed, sent in metadata) vs `sha256_actual` (receiver-computed after reassembly) directly in the row makes integrity verification auditable from history.
- Using `TEXT` for timestamps (ISO-8601 strings) keeps SQLite simple and human-readable in a DB browser during demos.

---

## 4. UDP Discovery Protocol

**Port:** UDP `50999` (configurable)
**Mechanism:** Broadcast on the LAN subnet (`255.255.255.255` or subnet-directed broadcast), every device both sends announcements and listens.

**Message format (JSON, kept small — UDP has a practical payload limit):**

```json
{
  "type": "ANNOUNCE",
  "device_id": "b3f1-...-uuid",
  "device_name": "Aryan-Laptop",
  "tcp_port": 51000,
  "timestamp": 1732500000
}
```

**Protocol flow:**
1. On startup, each instance sends an `ANNOUNCE` broadcast every **3 seconds**.
2. Every instance also listens on the same UDP port; on receiving an `ANNOUNCE` from an unknown/known device, it updates an in-memory peer table `{device_id: {ip, name, tcp_port, last_seen}}`.
3. A background task sweeps the peer table every 2 seconds; any device whose `last_seen` is older than **9 seconds** (3 missed beats) is marked **offline** in the UI (not deleted — history should still show it).
4. Optional `GOODBYE` message sent on graceful shutdown so peers update instantly instead of waiting for timeout.

**Why UDP here:** discovery doesn't need guaranteed delivery — if one broadcast is dropped, the next one (3s later) fixes it. Using TCP for this would mean either connecting to every device you don't know about yet (chicken-and-egg problem) or building your own broadcast mechanism anyway. UDP broadcast is the textbook-correct tool.

---

## 5. TCP Transfer Protocol

**Port:** TCP `51000` (configurable per device, exchanged in the UDP announce so peers with custom ports still connect correctly).

Every TCP session begins with a small **length-prefixed JSON control message**, then switches to raw binary chunk streaming. This avoids ambiguity between control and data.

**Wire framing:** `[4-byte big-endian length][JSON or binary payload]`

**Session sequence:**

```
SENDER                                      RECEIVER
  │──── TCP connect (paired peers only) ───────▶│
  │──── AUTH { session_token } ─────────────────▶│
  │◀─── AUTH_OK / AUTH_REJECT ────────────────────│
  │──── TRANSFER_REQUEST (metadata, see §6) ────▶│
  │                                               │ shows Accept/Reject UI
  │◀─── TRANSFER_ACCEPT / TRANSFER_REJECT ────────│
  │──── CHUNK[0], CHUNK[1], ... CHUNK[n] ────────▶│  (or only missing ones on resume)
  │◀─── CHUNK_ACK[i] (per chunk or batched) ──────│
  │──── TRANSFER_COMPLETE ───────────────────────▶│
  │◀─── VERIFY_RESULT { match: true/false } ──────│
```

- `AUTH` uses the session token issued during pairing (§8) — this is what stops an untrusted device on the same Wi-Fi from ever reaching `TRANSFER_REQUEST`.
- `CHUNK_ACK` lets the sender know which chunks are safely written to disk, so if the connection dies mid-stream, the sender's last confirmed index is known without guessing.

---

## 6. Chunk Format & Transfer Metadata

**`TRANSFER_REQUEST` metadata (JSON):**

```json
{
  "transfer_id": "uuid",
  "item_name": "Project.zip",
  "item_type": "file",
  "original_size": 2576980377,
  "compressed_size": 2210000000,
  "chunk_size": 4194304,
  "total_chunks": 527,
  "sha256_expected": "e3b0c44298fc1c149afbf4c8996fb924...",
  "compression_mode": "standard"
}
```

**Each binary chunk frame:**

```
[4 bytes] chunk_index   (uint32, big-endian)
[4 bytes] chunk_length  (uint32, big-endian, ≤ chunk_size)
[N bytes] raw chunk data
```

- **Chunk size default: 4 MB** — large enough to keep per-chunk overhead low, small enough that a resume only re-sends a few seconds of data, and light on an 8GB-RAM/Celeron machine (no need to hold the whole file in memory — stream chunk-by-chunk with Python file `seek()`/`read()`).
- Receiver writes each chunk directly to `chunk_index * chunk_size` offset in a pre-allocated file (using `file.seek()` then `write()`), so chunks can arrive and be written independently of order if you later want parallel chunk requests.

---

## 7. Resumable-Transfer Mechanism

1. Before sending, sender inserts one row per chunk into `transfer_chunks` (`is_received = 0`).
2. Receiver marks `is_received = 1` for a chunk **only after it's flushed to disk**, not just received into memory — this makes resume safe even if the app itself crashes, not just the network.
3. On reconnect for an existing `transfer_id`:
   - Receiver queries missing chunk indices and sends a `RESUME_REQUEST { transfer_id, missing_chunks: [12, 13, 45, ...] }`.
   - Sender seeks to those specific offsets in the (already-compressed/hashed) source file and re-sends only those chunks.
4. Transfer state (`transfers.status`) transitions: `pending → in_progress → (interrupted on failure) → resumed → completed`.
5. A local **checkpoint file is not needed** since SQLite already persists this — this is a good design talking point (no ad-hoc `.tmp` state files, the database *is* the source of truth).

**Failure detection:** a `socket.timeout` or `ConnectionResetError` on either side triggers marking the transfer `interrupted` rather than `failed`; the UI shows a "Resume" button that re-attempts connection to the same peer.

---

## 8. Secure Pairing Design

**Goal:** presence on the same Wi-Fi ≠ trust. Only paired devices may open a `TRANSFER_REQUEST`.

**Pairing flow:**
1. User A clicks "Pair" on device B in the Devices screen → sends `PAIR_REQUEST` over TCP.
2. Device B generates a random 6-digit pairing code, displays it on B's screen.
3. Device A's UI prompts "Enter the code shown on Laptop B" (classic Bluetooth-style out-of-band confirmation — prevents blind auto-trust).
4. On correct code entry, both devices exchange and store each other's public keys and generate a long-lived shared **session token**, saved in the `devices` table (`is_trusted = 1`).
5. All future `AUTH` steps use this stored token instead of repeating the pairing dance.

**Cryptography — use established libraries only:**
- **TLS for the TCP channel itself**, via Python's built-in `ssl` module wrapping the socket with self-signed certs generated once per device (`cryptography` library). This gets you encryption-in-transit for free without hand-rolling anything.
- Alternative/simpler for a student project: use `cryptography`'s `Fernet` (AES-128-CBC + HMAC, authenticated symmetric encryption) to encrypt the control messages and derive a per-session key from the paired shared secret.
- **Never implement your own cipher, key exchange, or hashing** — SHA-256 for integrity comes from `hashlib` (standard library), all encryption from `cryptography` (PyPI, free, audited, actively maintained).

This gives you three separate, correctly-scoped security properties to discuss in a viva: **authentication** (pairing), **confidentiality** (TLS/Fernet), **integrity** (SHA-256) — examiners like seeing these named separately since conflating them is a common student mistake.

---

## 9. API Design (FastAPI)

```
GET    /api/devices                     → list discovered + paired devices
POST   /api/devices/{id}/pair           → initiate pairing
POST   /api/devices/{id}/pair/confirm   → confirm pairing code
DELETE /api/devices/{id}                → unpair/forget device

POST   /api/transfers                   → start a new send (multipart or path-based)
GET    /api/transfers                   → list all transfers (history)
GET    /api/transfers/{id}              → get single transfer detail
POST   /api/transfers/{id}/accept       → receiver accepts incoming request
POST   /api/transfers/{id}/reject       → receiver rejects
POST   /api/transfers/{id}/pause        → pause active transfer
POST   /api/transfers/{id}/resume       → resume interrupted/paused transfer
DELETE /api/transfers/{id}              → cancel

GET    /api/settings                    → get current config
PUT    /api/settings                    → update device name, port, download dir, etc.

WS     /ws/transfers/{id}               → live progress stream (percent, speed, ETA, chunk count)
WS     /ws/devices                      → live device online/offline stream
```

REST handles request/response actions; WebSocket is used specifically for the two things that need continuous push updates (transfer progress, device presence) rather than polling — another deliberate protocol choice worth explaining in your report.

---

## 10. Frontend Page / Component Structure

```
pages/
  Dashboard.tsx        → summary cards, quick-send, recent activity
  Devices.tsx          → device grid, pair/unpair actions
  Send.tsx             → file/folder picker, compression choice, target device, start
  Receive.tsx          → incoming request modal/panel, accept/reject
  ActiveTransfer.tsx   → progress bar, speed, ETA, chunk counter, pause/cancel
  History.tsx          → filterable/sortable table of past transfers
  Settings.tsx         → device name, port, download folder, pairing list

components/
  DeviceCard.tsx        (name, IP, status dot, pair button)
  PairingModal.tsx       (code entry)
  FilePicker.tsx          (native file/folder input wrapper)
  CompressionSelector.tsx
  ProgressBar.tsx          (percent + speed + ETA)
  TransferHistoryRow.tsx
  ToastNotifications.tsx  (incoming transfer alerts)

services/
  api.ts     (typed fetch wrappers for every REST endpoint above)
  ws.ts      (WebSocket hook: useTransferProgress(id), useDeviceStatus())

state/
  DeviceContext.tsx
  TransferContext.tsx
```

---

## 11. Development Roadmap (Testable Phases)

| Phase | Deliverable | "Done" criteria |
|---|---|---|
| 1 | UDP discovery | Two instances on same Wi-Fi see each other's name/IP in a console log |
| 2 | Basic TCP transfer | One file sent A→B, no chunking, no UI |
| 3 | React UI shell | Dashboard + Devices page hitting real `/api/devices` |
| 4 | Multi-file + folder transfer | Folder structure preserved on receive |
| 5 | Chunked transfer | Large file split/reassembled correctly, hash matches |
| 6 | Resumable transfers | Kill Wi-Fi mid-transfer, reconnect, transfer completes without restarting |
| 7 | SHA-256 verification | Deliberately corrupt a chunk, confirm mismatch is detected |
| 8 | Compression | ZIP step wired into pipeline with size-saved stats in UI |
| 9 | Pairing/security | Unpaired device's transfer attempt is rejected; TLS/Fernet verified with packet capture (Wireshark) showing encrypted payload |
| 10 | SQLite history | Full transfer history populated and viewable |
| 11 | Error handling/logging/retries | Structured logs, retry-on-timeout logic, graceful error toasts in UI |
| 12 | Testing + polish | Unit tests for chunking/hashing/resume logic, integration test for a full transfer, UI cleanup |

Recommended pace: treat Phases 1–2 as a single "networking core" milestone, 3–4 as "usable MVP," 5–9 as "advanced engineering" (this is where most of your differentiation and viva material comes from), 10–12 as "production polish."

---

## 12. Recommended Free Libraries

**Backend (Python):**
- `fastapi`, `uvicorn[standard]` — API + ASGI server (uvicorn's standard extras include the WebSocket support you need)
- `asyncio`, `socket` — standard library, core networking
- `sqlite3` — standard library, or `sqlalchemy` (core, not ORM) if you want a lighter abstraction
- `hashlib` — standard library, SHA-256
- `zipfile`, `shutil` — standard library, compression/archiving
- `cryptography` — TLS certs / Fernet encryption
- `pydantic` — request/response validation (ships with FastAPI)
- `python-multipart` — needed for file upload endpoints in FastAPI
- `pytest`, `pytest-asyncio` — testing

**Frontend:**
- `react`, `vite` — app shell
- `axios` or native `fetch` — REST calls
- native `WebSocket` API — no extra library needed
- `zustand` (optional, lighter than Redux) — global state for device/transfer lists
- `tailwindcss` — styling (optional but speeds up a clean UI)
- `lucide-react` — icons

All of the above are free/open-source with no usage limits, satisfying your constraint list.

---

## 13. Potential Technical Challenges & Solutions

| Challenge | Solution |
|---|---|
| UDP broadcast blocked by some routers/firewalls | Fall back to multicast (`239.x.x.x` group) as a secondary discovery path; document both, demo on a controlled network |
| Windows Firewall prompts blocking sockets | Document a one-time firewall exception step; this is normal and expected, mention it in your report as a real deployment consideration |
| Large folder = many small files, each needing its own transfer overhead | Zip the whole folder before chunking (already in your pipeline) rather than transferring file-by-file |
| Simultaneous transfers to/from multiple peers | Run the TCP server as `asyncio` tasks — one coroutine per connection, not one thread per connection, keeps it lightweight on your Celeron N4020 |
| Two devices both press "send" to each other at once | Give each transfer a UUID and let both proceed independently — no shared lock needed since each is a distinct TCP connection |
| Resume after the *app itself* (not just network) restarts | Because chunk state lives in SQLite, not memory, this already works — verify explicitly during Phase 6 testing |
| NAT/different subnets (e.g., guest Wi-Fi isolation) | Out of scope by design — document clearly that Bridge Flow assumes same-subnet LAN, which is realistic for AirDrop-style tools |
| Large file compression using too much RAM | Use `zipfile`'s streaming write (don't load the whole file into memory) — compress in chunks read from disk |

---

## 14. How This Demonstrates Both Networking and SDE Skills

**Networking engineering:**
- Correct protocol selection (UDP vs TCP) for different needs
- Custom application-layer protocol design (message framing, control vs data separation)
- Socket programming with `asyncio`
- Connection lifecycle management, timeouts, retries
- Broadcast/multicast discovery
- Bandwidth/throughput measurement (speed, ETA calculations)
- Applied cryptography for secure communication (TLS/Fernet)

**Software engineering:**
- Layered, modular architecture with clear separation of concerns
- Database schema design normalized around a resumability requirement
- RESTful API design + WebSocket for real-time state
- State machine design for transfer lifecycle
- Error handling and structured logging
- Unit + integration testing strategy
- Clean repository structure and documentation discipline

Framing it this way in interviews lets you talk about *why* each decision was made, not just *what* was built — that's what distinguishes a strong project discussion from a "I followed a tutorial" one.

---

## 15. Suggested Final-Year Report Structure

1. **Abstract**
2. **Introduction** — problem statement (cloud dependency for same-LAN transfers)
3. **Literature Review** — brief comparison: AirDrop, traditional FTP, cloud-based sharing (Google Drive/WeTransfer), Bluetooth transfer, and why LAN P2P fills a gap
4. **System Requirements** — functional + non-functional (performance on low-spec hardware, security, resumability)
5. **System Design**
   - Architecture diagram (§1)
   - Module breakdown (§2)
   - Database ER diagram (§3)
   - Network protocol design (§4, §5, §6)
6. **Implementation**
   - Technology justification
   - Key algorithms: chunking, resume, hashing, pairing
   - Screenshots of each screen
7. **Testing**
   - Unit test results
   - Integration test scenarios (including simulated Wi-Fi drop)
   - Performance data (transfer speed vs file size, compression ratio results)
8. **Results and Discussion**
9. **Challenges Faced** (pull from §13, written in first person once you've actually hit them)
10. **Conclusion and Future Scope** (e.g., mobile client, multicast fallback, parallel chunk streaming)
11. **References**
12. **Appendix** — full API reference, DB schema, sample logs

---

## Next Step

This document is the architecture baseline. Once you review and approve it (or ask for changes to any section), we start **Phase 1: UDP discovery** — a runnable console-based proof of concept before any UI exists, so the networking core is verified first.
