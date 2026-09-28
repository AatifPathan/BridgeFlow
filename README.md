# Bridge Flow

**AirDrop-style peer-to-peer file and folder transfer over your local Wi-Fi / LAN.**
No cloud, no accounts, no internet, no subscriptions. Two computers on the same network find each other, pair with a code, and send files directly.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688) ![React](https://img.shields.io/badge/React-Vite-61dafb) ![Platform](https://img.shields.io/badge/Windows-exe%20included%20via%20build-lightgrey) ![Cost](https://img.shields.io/badge/cost-100%25%20free-brightgreen)

---

## Table of contents

1. [What it does](#what-it-does)
2. [How it is delivered (read this first)](#how-it-is-delivered-read-this-first)
3. [Part A - Build the app (one time, on ONE computer)](#part-a---build-the-app-one-time-on-one-computer)
4. [Part B - Run it on the computers that will send and receive](#part-b---run-it-on-the-computers-that-will-send-and-receive)
5. [Part C - Using Bridge Flow](#part-c---using-bridge-flow)
6. [Troubleshooting](#troubleshooting)
7. [Check that everything works (self-check)](#check-that-everything-works-self-check)
8. [Running from source (for developers)](#running-from-source-for-developers)
9. [How it works](#how-it-works)
10. [Security notes and known limitations](#security-notes-and-known-limitations)
11. [Project structure](#project-structure)
12. [Tech stack and libraries](#tech-stack-and-libraries)
13. [Roadmap](#roadmap)
14. [License](#license)

---

## What it does

| Feature | Details |
|---|---|
| **Automatic device discovery** | Devices running Bridge Flow on the same network find each other using UDP broadcast. Shows name, IP address, and online/offline status. |
| **Secure pairing** | A device is never trusted just because it is on your Wi-Fi. Pairing needs a 6-digit code shown on the other device. Only paired devices can send files. |
| **File and folder transfer** | Send any file type, or a whole folder. The receiver gets the same folder structure. |
| **Chunked transfers** | Data is sent in 4 MB chunks over TCP. |
| **Resume after interruption** | If Wi-Fi drops or the app closes, the transfer continues from the last received chunk instead of starting again. |
| **Integrity check** | Every transfer is verified with SHA-256. A mismatch is reported, never ignored. |
| **Optional compression** | None / Standard / Maximum (ZIP). Shows original size, sent size and space saved. Already-compressed files (JPG, MP4, MP3, ZIP) correctly show little or no saving. |
| **Live progress** | Percentage, speed and time remaining while a transfer runs. |
| **Transfer history** | Every transfer is stored locally in SQLite: sent/received, status, size, compression, time. Searchable and filterable. |
| **One-file app** | Packaged into a single `.exe`. The receiving computer needs **nothing** installed. |

---

## How it is delivered (read this first)

There are two different kinds of computer in this guide. Do not mix them up:

| | **The BUILD computer** | **The RUN computers** |
|---|---|---|
| What it is | The one computer where you turn this source code into `BridgeFlow.exe`. You do this **once**. | Every computer that will actually send or receive files (including the build computer itself). |
| Needs Python? | **Yes** | **No** |
| Needs Node.js? | **Yes** | **No** |
| Needs internet? | **Yes** (to download libraries once) | **No** |
| What to do | Follow **Part A** | Follow **Part B** |

Think of it like baking: the build computer is the kitchen, and `BridgeFlow.exe` is the finished cake you hand to everyone else. Nobody else needs the kitchen.

> **Important:** `BridgeFlow.exe` only works on Windows, and it must be built **on Windows**. (Building on a Mac gives a Mac app; building on Linux gives a Linux app.) You cannot create a Windows exe from a Mac or Linux computer.

---

## Part A - Build the app (one time, on ONE computer)

Follow every step in order. Takes about 20 to 30 minutes, mostly waiting for downloads.

### Step 1 - Install Python

1. Open <https://www.python.org/downloads/> in your browser.
2. Click the big yellow **Download Python 3.x.x** button. Any version from 3.10 upward is fine.
3. Open the downloaded installer.
4. **VERY IMPORTANT:** on the first screen, tick the box at the bottom that says **"Add python.exe to PATH"**. If you skip this, nothing later will work.
5. Click **Install Now**, then **Close** when it finishes.

**Check it worked:**

1. Press the **Windows key**, type `PowerShell`, and press Enter. A blue window opens.
2. Type this and press Enter:
   ```powershell
   python --version
   ```
3. You should see something like `Python 3.12.4`.

If you instead see *"Python was not found; run without arguments to install from the Microsoft Store"*, or *"python is not recognized"*, see [Troubleshooting: Python problems](#python-was-not-found-or-opens-the-microsoft-store).

### Step 2 - Install Node.js

Node.js is only used once, to prepare the web page part of the app.

1. Open <https://nodejs.org/>.
2. Click the button labelled **LTS** (recommended).
3. Open the installer and keep clicking **Next** with the default options, then **Install** and **Finish**.

**Check it worked:** close PowerShell, open a new one, and type:

```powershell
node --version
npm --version
```

You should see two version numbers (like `v22.11.0` and `10.9.0`).

If `npm` shows a red error mentioning *"running scripts is disabled"*, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Type `Y` and press Enter if it asks.

### Step 3 - Get the Bridge Flow files

**Easiest way (no extra software):**

1. On this GitHub page, click the green **Code** button, then **Download ZIP**.
2. Find the downloaded ZIP (usually in **Downloads**), right-click it, and choose **Extract All...**.
3. Move the extracted folder to your Desktop and make sure it is named `bridgeflow`. Inside it you should see `build_release.py`, `backend`, and `frontend`.

*(If you already use Git, you can instead run `git clone https://github.com/<your-username>/bridgeflow.git`.)*

### Step 4 - Open PowerShell inside the project folder

1. Open the `bridgeflow` folder in File Explorer (the one containing `build_release.py`).
2. Click on the **address bar** at the top of the window (where the folder path is shown).
3. Type `powershell` and press **Enter**.

A blue PowerShell window opens already inside the correct folder. Every command below is typed there.

### Step 5 - Create a private Python environment and install the libraries

A "virtual environment" is just a separate box for this project's libraries, so nothing gets mixed up with the rest of your computer. Type these one at a time, pressing Enter after each:

**5a. Create the environment (takes a few seconds):**
```powershell
python -m venv backend\venv
```

**5b. Switch it on:**
```powershell
backend\venv\Scripts\Activate.ps1
```
You should now see `(venv)` at the start of the line. If you get a red error saying *"running scripts is disabled on this system"*, run this and then repeat 5b:
```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

**5c. Install all the Python libraries (takes 2 to 5 minutes, needs internet):**
```powershell
pip install -r backend\requirements.txt
```
Lots of text will scroll past. Wait until you get your cursor back. The last line should say `Successfully installed ...`.

**5d. Check the libraries installed properly:**
```powershell
python -c "import fastapi, uvicorn, cryptography, websockets; print('All libraries OK')"
```
It should print `All libraries OK`. If it prints an error saying `No module named ...`, repeat step 5c.

> **Every time you open a new PowerShell window later, repeat step 5b** (switch the environment on) before running Python commands for this project.

**What was just installed (you do not need to do anything, this is for your information):**

| Library | What it is used for |
|---|---|
| `fastapi` | The web/API server that the app's screens talk to |
| `uvicorn[standard]` | Runs the FastAPI server (includes WebSocket support for live progress) |
| `pydantic` | Checks that data sent to the server is valid |
| `cryptography` | Encryption helper for the device pairing key (Fernet) |
| `python-multipart` | Lets the server accept form and file data |
| `pytest`, `pytest-asyncio` | Automated tests |
| `pyinstaller` | Turns everything into a single `.exe` |

### Step 6 (recommended) - Test everything before building

Make sure no other copy of Bridge Flow is running, then:

```powershell
python selfcheck.py
```

This starts two test copies of Bridge Flow on your computer and runs a full set of checks. Windows Firewall may pop up: click **Allow access** (tick **Private networks**). At the end you want to see:

```
=== 16 passed, 0 warnings, 0 failed ===
```

Each line shows `[PASS]`, `[WARN]` or `[FAIL]`. If anything says FAIL, see [Check that everything works](#check-that-everything-works-self-check).

### Step 7 - Build the app

```powershell
python build_release.py
```

This automatically installs the web page libraries (React, Vite), builds the web page, and packs everything into one file. It takes **3 to 10 minutes**. Lots of text will scroll past, which is normal. When finished you will see:

```
Done. Find it at: dist/BridgeFlow.exe
```

Your finished app is at `bridgeflow\dist\BridgeFlow.exe`.

> **Before you build:** watch the first lines of the output. It says `Step 0/3: Installing Python dependencies`. If it prints **"Missing Python packages"**, run `pip install -r backend\requirements.txt` again and re-run the build. (This protects you from building a broken exe.)

### Step 8 (optional) - Test the built exe

```powershell
python selfcheck.py --exe dist\BridgeFlow.exe
```

You should again see `0 failed`.

**You are done with Part A.** Copy `dist\BridgeFlow.exe` to a USB drive, a shared folder, or email/cloud it to every computer that should use Bridge Flow.

---

## Part B - Run it on the computers that will send and receive

**These computers need nothing installed. No Python, no Node.js, no internet.**

### Step 1 - Put the app in its own folder

Copy `BridgeFlow.exe` to the computer and put it in a folder of its own, for example `C:\BridgeFlow\`. The app creates a `bridgeflow_data` folder next to itself to store your paired devices, history and received files, so a dedicated folder keeps things tidy.

### Step 2 - Make sure the Wi-Fi is set to "Private"

Windows firewall is stricter on networks it labels "Public", which can silently block device discovery.

1. Open **Settings** > **Network & internet** > **Wi-Fi**.
2. Click the name of the Wi-Fi you are connected to.
3. Under **Network profile type**, choose **Private network**.

### Step 3 - Start the app

1. Double-click **BridgeFlow.exe**.
2. **Windows SmartScreen** may show *"Windows protected your PC"*. This happens because the app is not digitally signed (signing costs money). Click **More info**, then **Run anyway**.
3. **Windows Defender Firewall** will ask whether to allow the app on the network. Tick **Private networks** and click **Allow access**. If you click Cancel, discovery and transfers will not work; see [Troubleshooting](#devices-do-not-show-up-on-the-devices-page) to fix it.
4. A black window opens (leave it open, closing it stops the app) and your web browser opens automatically at `http://localhost:8000`.

Do this on **every** computer that should send or receive.

### Step 4 - Same network

All computers must be on the **same Wi-Fi network** (or the same wired network/router). Guest Wi-Fi, some college and office networks, and phone hotspots with "client isolation" block computers from talking to each other.

---

## Part C - Using Bridge Flow

### First time: pair two computers

Pairing proves you trust the other device. You only do it once per pair.

1. Open Bridge Flow on both computers. Open the **Devices** page on each.
2. Within about 10 seconds each computer should list the other as **Online**.
3. On computer **A**, click **Pair** next to computer **B**.
4. Look at computer **B**'s **Devices** page. A banner shows a **6-digit code**.
5. On computer **A**, type that code into the box and click **Confirm pairing**.
6. Both computers now show each other as **Paired**. (The code expires after 2 minutes; if it does, click Pair again.)

### Send a file or folder

1. On the sender, open **Send**.
2. Choose the paired device from the list.
3. In **File or folder path**, type or paste the full path, for example `C:\Users\Aatif\Documents\report.pdf` or `C:\Users\Aatif\Pictures\Holiday`.
   - **Tip:** in File Explorer, hold **Shift**, right-click the file or folder, and choose **Copy as path**, then paste it. The quotes it adds are handled automatically.
4. Choose **Compression**:
   - **None** - sends the file as it is (fastest for photos, videos, MP3s and ZIPs).
   - **Standard** or **Maximum** - best for text, documents, spreadsheets and code. The app shows how much space was saved.
   - Folders are always zipped for transfer and unpacked again on the other side.
5. Click **Start transfer** and watch the progress bar (percentage, speed, time remaining).
6. When it says **Transfer complete**, the file has been checked with SHA-256 and matches exactly.

### Where do received files go?

In the `bridgeflow_data\storage\received\` folder next to `BridgeFlow.exe` on the receiving computer. Folders arrive with their original structure. If a file with the same name already exists, the new one is saved as `name (1).ext` and nothing is overwritten.

### The other pages

| Page | What it shows |
|---|---|
| **Dashboard** | How many devices are online/paired, transfers completed, recent activity |
| **Devices** | Discovered devices, pair/unpair, and pairing codes |
| **Send** | Send a file or folder with compression options and live progress |
| **Receive** | Incoming transfers and their status |
| **History** | Every transfer, with filters (sent/received/interrupted/failed) and search, plus a **Resume** button for interrupted sends |
| **Settings** | Device name and network ports |

### Resuming an interrupted transfer

If the connection drops or the receiving app closes, the transfer is marked **Interrupted**. Get both apps running and connected again, open **History** on the sending computer, and click **Resume**. Only the missing chunks are sent.

*(Resume needs the sender's temporary archive, which is kept until the transfer completes. It is stored in `bridgeflow_data\storage\outgoing\` on the sender.)*

### Resetting everything

Close the app and delete the `bridgeflow_data` folder. The next start creates a fresh device identity and forgets all pairings and history.

---

## Troubleshooting

### Python was not found (or opens the Microsoft Store)

Windows ships a fake `python` shortcut that opens the Microsoft Store. Two fixes:

1. **Turn off the fake shortcut:** **Settings** > **Apps** > **Advanced app settings** > **App execution aliases**, then switch **OFF** both `python.exe` and `python3.exe`. Close and reopen PowerShell.
2. **Install real Python** from python.org and tick **"Add python.exe to PATH"** (see Part A, Step 1). Restart PowerShell (or the computer) afterwards.

### Devices do not show up on the Devices page

Work through this list in order:

1. **Firewall.** This is the cause 9 times out of 10. Open **Windows Security** > **Firewall & network protection** > **Allow an app through firewall** > **Change settings**. Find **BridgeFlow** (or `python`), and tick **Private**. If it is not listed, click **Allow another app**, browse to `BridgeFlow.exe`, add it, then tick **Private**.
2. **Wi-Fi is set to Public.** Change it to Private (Part B, Step 2).
3. **Different networks.** Both computers must be on the same Wi-Fi. Guest Wi-Fi and hotspots with client isolation block this.
4. **Bridge Flow not running on both.** Each computer must have the app open.
5. **VPN running.** Turn it off; VPNs can send broadcasts out the wrong network adapter.
6. Wait up to 10 seconds, then refresh the page.

### The exe crashes immediately with "No module named 'uvicorn'"

The exe was built without its libraries. On the build computer, switch on the environment, run `pip install -r backend\requirements.txt`, then `python build_release.py` again, and give everyone the new exe.

### "Windows protected your PC" (SmartScreen) or antivirus warns about the file

The app is not code-signed, and single-file apps made with PyInstaller are sometimes wrongly flagged by antivirus. The full source is in this repository, so you can review and build it yourself. To open it: **More info** > **Run anyway**. If your antivirus quarantines it, add an exception for the file.

### The page says "Can't reach the Bridge Flow backend"

The black console window was closed, so the app stopped. Start `BridgeFlow.exe` again.

### The page will not open at localhost:8000

Something else on the computer is already using port 8000, or the app did not start. Look at the black console window for an error message. Close other copies of Bridge Flow first.

### Pairing fails

The code expires after 2 minutes. Click **Pair** again to get a new one, and check that you typed the code shown on the **other** computer.

### "Transfer failed"

Check the black console window on **both** computers for the reason. The usual causes are: the devices are no longer paired on one side (pair again), or the file changed/was corrupted during the transfer (a hash mismatch is reported in the log).

### Everything worked, but compression saved nothing

Normal for photos, videos, MP3s, and ZIP files: they are already compressed. Compression helps most with text, documents, spreadsheets, and source code.

### Ports used by Bridge Flow (for firewall or router rules)

| Port | Protocol | Purpose |
|---|---|---|
| 50999 | UDP | Device discovery (broadcast) |
| 51000 | TCP | Pairing and file transfer |
| 8000 | TCP | The app's web page (this computer only) |

---

## Check that everything works (self-check)

`selfcheck.py` starts **two** Bridge Flow instances on your computer and tests the real flow between them:

```powershell
python selfcheck.py                              # tests the source code
python selfcheck.py --exe dist\BridgeFlow.exe    # tests the built exe
```

It checks: startup, device discovery, pairing (including that a wrong code is rejected), small files, compression, folders with structure, paths pasted with quotes, a multi-chunk file, no-overwrite of existing files, history, and that sending to a device that no longer trusts you fails correctly.

- Close any running Bridge Flow first (it needs ports 8000, 8001, 51000, 51001 and 50999).
- **PASS** = works. **WARN** on the discovery step usually means the firewall blocked UDP broadcasts. **FAIL** prints the last lines of each instance's log so the problem is easy to find.

You can also run the unit tests:

```powershell
cd backend
pytest tests -v
```

---

## Running from source (for developers)

You only need this if you want to change the code. Everything below assumes you finished Part A, steps 1 to 5.

**Terminal 1 - backend:**
```powershell
cd backend
venv\Scripts\Activate.ps1
python main.py
```

**Terminal 2 - frontend (live-reloading):**
```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. In this mode the frontend and backend are two separate processes (Vite forwards `/api` and `/ws` requests to the backend on port 8000). API documentation is generated automatically at **http://localhost:8000/docs**.

### Running two copies on one computer

Useful for testing without a second PC. The second copy needs different ports and a different name:

```powershell
# Window 1
$env:BRIDGEFLOW_DEVICE_NAME="Laptop-A"
python main.py

# Window 2
$env:BRIDGEFLOW_DEVICE_NAME="Laptop-B"
$env:BRIDGEFLOW_PORT="8001"
$env:BRIDGEFLOW_TCP_PORT="51001"
$env:BRIDGEFLOW_DATA_DIR="C:\bf-test\B"
python main.py
```

| Environment variable | Meaning | Default |
|---|---|---|
| `BRIDGEFLOW_PORT` | Web page / API port | `8000` |
| `BRIDGEFLOW_TCP_PORT` | Transfer port | `51000` |
| `BRIDGEFLOW_DEVICE_NAME` | Name shown to other devices | computer name |
| `BRIDGEFLOW_DATA_DIR` | Where the database, logs and received files live | next to the app |
| `BRIDGEFLOW_NO_BROWSER` | Set to `1` to stop the browser opening automatically | off |
| `BRIDGEFLOW_TEST_SLOW_CHUNKS` | Test only: seconds the receiver waits per chunk, to make interrupting a transfer easy | off |

### Testing resume on purpose

1. Start the receiver with `$env:BRIDGEFLOW_TEST_SLOW_CHUNKS="0.5"`.
2. Send a large file (100 MB or more) with **Standard** compression.
3. While it transfers, close the receiver's window.
4. Restart the receiver **without** the slowdown, then click **Resume** in the sender's **History**.

### Rebuilding after code changes

```powershell
python build_release.py
```

---

## How it works

```
+------------------- React frontend (served by the backend) -------------------+
|  Dashboard | Devices | Send | Receive | History | Settings                    |
+----------------------------------+-------------------------------------------+
                                   |  REST + WebSocket (live progress)
+----------------------------------v-------------------------------------------+
|                          FastAPI application layer                            |
+---+-------------+---------------+---------------+---------------+-------------+
    |             |               |               |               |
 Discovery     Pairing        Transfer       Compression      Integrity
  (UDP)      (6-digit code)  (TCP, chunks,   (ZIP)           (SHA-256)
                              resume)
    |             |               |
    +-------------+---------------+---------> SQLite (devices, transfers, chunks, settings)
```

**Discovery (UDP).** Every 3 seconds each instance broadcasts a small JSON "ANNOUNCE" message (device id, name, transfer port) on UDP port 50999 and listens for the others. A device not heard from for 9 seconds is shown as offline. UDP is the right tool here: a lost packet is simply replaced by the next one, and TCP could not be used because you do not yet know who to connect to.

**Pairing.** The requester asks the peer to pair; the peer shows a random 6-digit code on its own screen; the human types it on the requester. On a match both sides store each other as trusted along with a shared key. Untrusted devices are refused before any transfer request is read.

**Transfer (TCP).** Each message is length-prefixed (4-byte length, then a JSON or binary body). The sender sends metadata (name, sizes, chunk count, SHA-256); the receiver accepts and replies with the list of chunks it still needs; the sender streams only those 4 MB chunks; the receiver writes each chunk directly at its byte offset and records it in SQLite.

**Resume.** Because chunk state is stored in SQLite (not memory), a resumed transfer just asks "which chunks are missing?" and sends only those, even after the app itself was closed.

**Integrity.** After the last chunk the receiver computes SHA-256 of the assembled file and compares it to the sender's hash. Only a match is marked complete (and unpacked, if compressed).

**Packaging.** `build_release.py` builds the React app, copies it into the backend, and runs PyInstaller. The backend then serves the web page itself, so the final app is one process on one port.

The full design document (database schema, protocol, roadmap) is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). It describes the intended design; the section below lists where the current implementation is simpler.

---

## Security notes and known limitations

Bridge Flow is a learning / final-year project. Please read this before trusting it with anything sensitive.

- **Use it on networks you trust** (your home Wi-Fi). It is designed for a local network, not the open internet.
- **Local network only.** Devices on different networks cannot find or reach each other. There is no cloud or relay.
- **Pairing uses trust-on-first-use.** The shared key is sent once, unencrypted, during pairing. Someone able to watch your network at that exact moment could read it. A stronger design would use an authenticated key exchange.
- **File data is not encrypted on the wire.** Integrity is checked (SHA-256), but the bytes travel unencrypted on your local network. The pairing key exists but is not yet used to encrypt the data stream.
- **Incoming transfers from paired devices are accepted automatically.** There is no per-file accept/reject prompt yet. Only unpair devices you do not trust.
- **File names from the network are sanitised** so a paired device cannot write outside the received folder.
- **The Send page takes a typed or pasted path**, not a file-picker dialog, because a web page cannot see real file paths.
- **Resume of a sent transfer** needs the sender's temporary archive to still exist (it is deleted after a successful transfer).
- **The app is not code-signed**, so Windows shows a SmartScreen warning the first time.
- **Windows only for the exe.** Build on the operating system you want to run on.

---

## Project structure

```
bridgeflow/
├── build_release.py            One command: builds the frontend and packages the .exe
├── selfcheck.py                End-to-end test with two instances on one computer
├── README.md
├── docs/
│   └── ARCHITECTURE.md         Full design document
├── backend/
│   ├── main.py                 Entry point: discovery + TCP server + API (+ web page)
│   ├── config.py               Device identity, ports, timing
│   ├── requirements.txt
│   ├── discovery/              UDP broadcast discovery
│   ├── transfer/               Wire protocol, chunking, resume, TCP client and server
│   ├── compression/            ZIP compression and extraction
│   ├── integrity/              SHA-256 hashing
│   ├── security/               Pairing codes, trusted devices, Fernet helper
│   ├── database/               SQLite schema and data access
│   ├── api/                    FastAPI routes and WebSocket
│   ├── models/                 Request/response schemas
│   ├── utils/                  Logging, file-name safety, resource paths
│   └── tests/                  pytest unit tests
└── frontend/
    └── src/
        ├── pages/              Dashboard, Devices, Send, Receive, History, Settings
        ├── components/         Sidebar, DeviceCard, ProgressBar
        └── services/           REST client, WebSocket hooks, formatting helpers
```

---

## Tech stack and libraries

Everything is free and open source. No paid services, cloud accounts, or API keys.

| Area | Tools |
|---|---|
| Backend | Python, FastAPI, uvicorn, `asyncio`, Python `socket` |
| Frontend | React, Vite |
| Database | SQLite (built into Python) |
| Networking | UDP broadcast (discovery), TCP sockets (transfer), WebSocket (live progress) |
| Security / integrity | `cryptography` (Fernet), `hashlib` SHA-256 |
| Compression | Python `zipfile` |
| Packaging | PyInstaller |
| Testing | pytest, pytest-asyncio, `selfcheck.py` |

**Python libraries** (installed by `pip install -r backend/requirements.txt`): `fastapi`, `uvicorn[standard]`, `pydantic`, `cryptography`, `python-multipart`, `pytest`, `pytest-asyncio`, `pyinstaller`.

**JavaScript libraries** (installed automatically by `npm install` / `build_release.py`): `react`, `react-dom`, `vite`, `@vitejs/plugin-react`.

---

## Roadmap

- Manual accept / reject prompt for incoming transfers
- Authenticated key exchange for pairing, and encryption of the data stream
- Native file / folder picker window
- Optional remote mode (rendezvous server with relay or NAT hole punching) for devices on different networks
- Windows installer that also adds the firewall rule
- Multiple simultaneous transfers and a pause button

---

## License

MIT. Add a `LICENSE` file to the repository root with the standard MIT text and your name.
