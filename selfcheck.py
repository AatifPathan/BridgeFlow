"""
Bridge Flow - end-to-end self check

Starts TWO Bridge Flow instances on this computer (different ports and data
folders) and tests the real flow between them: discovery, pairing, file /
folder / compressed transfers, quoted Windows paths, no-overwrite, and the
failure path. Prints PASS / WARN / FAIL for every step.

Run from the project root, inside the backend virtual environment:

    python selfcheck.py                          # tests the source code
    python selfcheck.py --exe dist\\BridgeFlow.exe   # tests the built exe

Close any running Bridge Flow first (it needs ports 8000, 8001, 51000, 51001,
50999). If Windows shows a firewall prompt, click Allow.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
TERMINAL = ("completed", "failed", "interrupted", "rejected")
results = []


def record(name, ok, detail="", warn=False):
    status = "PASS" if ok else ("WARN" if warn else "FAIL")
    results.append((status, name))
    print(f"[{status}] {name}" + (f"  ->  {detail}" if detail else ""), flush=True)
    return ok


def call(port, method, path, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception:
        return 0, {}


def wait_until(fn, timeout, interval=0.5):
    end = time.time() + timeout
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(interval)
    return None


def start_instance(name, api_port, tcp_port, data_dir, log_dir, exe):
    env = {
        **os.environ,
        "BRIDGEFLOW_DATA_DIR": str(data_dir),
        "BRIDGEFLOW_DEVICE_NAME": name,
        "BRIDGEFLOW_PORT": str(api_port),
        "BRIDGEFLOW_TCP_PORT": str(tcp_port),
        "BRIDGEFLOW_NO_BROWSER": "1",
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
    }
    log_path = log_dir / f"{name}.log"
    log = open(log_path, "w", encoding="utf-8")
    if exe:
        exe = Path(exe).resolve()          # relative paths break once we change directory
        if not exe.exists():
            raise SystemExit(f"Executable not found: {exe}")
        cmd, cwd = [str(exe)], str(exe.parent)
    else:
        cmd, cwd = [sys.executable, "main.py"], str(BACKEND)
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
    return proc, log_path


def stop(proc):
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def send(port_from, peer_id, peer_ip, peer_port, path, mode, quoted=False):
    text = f'"{path}"' if quoted else str(path)
    status, res = call(port_from, "POST", "/api/transfers", {
        "peer_device_id": peer_id, "peer_ip": peer_ip, "peer_port": peer_port,
        "peer_device_name": "Check-B", "source_path": text, "compression_mode": mode,
    })
    if status != 200:
        return None, res
    final = wait_until(
        lambda: (lambda s, t: t["status"] if s == 200 and t.get("status") in TERMINAL else None)(
            *call(port_from, "GET", f"/api/transfers/{res['transfer_id']}")),
        timeout=90, interval=0.5)
    return final, res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", help="path to a built BridgeFlow executable to test instead of the source code")
    args = parser.parse_args()

    if call(8000, "GET", "/api/health", timeout=2)[0] == 200 or call(8001, "GET", "/api/health", timeout=2)[0] == 200:
        print("Something is already running on port 8000/8001. Close Bridge Flow first, then re-run.")
        return 2

    work = Path(tempfile.mkdtemp(prefix="bridgeflow_check_"))
    data_a, data_b, logs, src = work / "A", work / "B", work / "logs", work / "src"
    for d in (data_a, data_b, logs, src):
        d.mkdir()
    recv_b = data_b / "storage" / "received"
    print(f"Working folder: {work}\nMode: {'built exe' if args.exe else 'source code'}\n")

    proc_a = proc_b = None
    try:
        proc_a, log_a = start_instance("Check-A", 8000, 51000, data_a, logs, args.exe)
        proc_b, log_b = start_instance("Check-B", 8001, 51001, data_b, logs, args.exe)

        up = wait_until(lambda: call(8000, "GET", "/api/health")[0] == 200 and call(8001, "GET", "/api/health")[0] == 200, 40)
        if not record("Both instances start and answer HTTP", bool(up),
                      "" if up else f"see {log_a} and {log_b}"):
            return 1

        # ---- discovery (UDP broadcast) ----
        def discovered():
            _, da = call(8000, "GET", "/api/devices")
            _, db = call(8001, "GET", "/api/devices")
            b_seen = [d for d in (da or {}).get("devices", []) if d["device_name"] == "Check-B" and d["online"]]
            a_seen = [d for d in (db or {}).get("devices", []) if d["device_name"] == "Check-A" and d["online"]]
            return (b_seen[0], a_seen[0]) if b_seen and a_seen else None

        found = wait_until(discovered, 30)
        record("Discovery: each instance sees the other (UDP broadcast)", bool(found),
               f"peer address {found[0]['ip']}" if found else
               "not found in 30s - check the firewall allowed Python/BridgeFlow on Private networks. "
               "Continuing with direct connection.", warn=not found)
        peer_ip = found[0]["ip"] if found else "127.0.0.1"

        # ---- pairing ----
        status, _ = call(8000, "POST", "/api/pairing/request", {"peer_ip": peer_ip, "peer_port": 51001})
        record("Pairing: request sent to the other device", status == 200)
        _, inc = call(8001, "GET", "/api/pairing/incoming")
        reqs = (inc or {}).get("requests", [])
        code = reqs[0]["code"] if reqs else None
        record("Pairing: the other device shows a 6-digit code", bool(code) and len(code) == 6)
        if not code:
            return 1
        wrong = "111111" if code != "111111" else "222222"
        status, _ = call(8000, "POST", "/api/pairing/confirm", {"peer_ip": peer_ip, "peer_port": 51001, "code": wrong})
        record("Pairing: a wrong code is rejected", status == 400)
        status, _ = call(8000, "POST", "/api/pairing/confirm", {"peer_ip": peer_ip, "peer_port": 51001, "code": code})
        if not record("Pairing: the correct code pairs the devices", status == 200):
            return 1

        _, devs = call(8000, "GET", "/api/devices")
        trusted = [d for d in devs["devices"] if d["is_trusted"]]
        b_id = trusted[0]["device_id"] if trusted else None
        if not record("Paired device is stored as trusted", bool(b_id)):
            return 1

        def transfer_case(label, path, mode, expected_name=None, quoted=False, is_dir=False):
            final, res = send(8000, b_id, peer_ip, 51001, path, mode, quoted)
            if final is None:
                return record(label, False, f"API error: {res}"), res
            name = expected_name or path.name
            target = recv_b / name
            if is_dir:
                same = final == "completed" and all(
                    (recv_b / path.name / f.relative_to(path)).exists() and
                    (recv_b / path.name / f.relative_to(path)).read_bytes() == f.read_bytes()
                    for f in path.rglob("*") if f.is_file())
            else:
                same = final == "completed" and target.exists() and target.read_bytes() == Path(path).read_bytes()
            stats = ""
            if res.get("compressed_size") is not None:
                stats = f" (original {res['original_size']} B -> sent {res['compressed_size']} B, saved {res['space_saved_percent']}%)"
            return record(label, same, f"status={final}{stats}" if same else f"status={final}; file missing or different", ), res

        # ---- transfers ----
        small = src / "small.txt"
        small.write_text("hello from Bridge Flow\n" * 20)
        transfer_case("Transfer: small file, no compression", small, "none")

        big_text = src / "big_text.txt"
        big_text.write_text("Bridge Flow compression test line\n" * 150000)
        _, res = transfer_case("Transfer: text file with Standard compression", big_text, "standard")
        record("Compression: text file shrank", res.get("compressed_size", 10**12) < res.get("original_size", 0) / 2,
               f"saved {res.get('space_saved_percent')}%")

        project = src / "project"
        (project / "src" / "deep").mkdir(parents=True)
        (project / "README.md").write_text("readme\n" * 50)
        (project / "src" / "main.py").write_text("print('hi')\n" * 100)
        (project / "src" / "deep" / "data.bin").write_bytes(os.urandom(200_000))
        transfer_case("Transfer: folder with Maximum compression keeps its structure", project, "max", is_dir=True)

        quoted_file = src / "quoted path file.txt"
        quoted_file.write_text("pasted with quotes\n")
        transfer_case("Transfer: path pasted with quotes ('Copy as path')", quoted_file, "none", quoted=True)

        random_file = src / "random.bin"
        random_file.write_bytes(os.urandom(9 * 1024 * 1024))
        transfer_case("Transfer: 9 MB incompressible file (3 chunks) with Standard compression", random_file, "standard")

        final, _ = send(8000, b_id, peer_ip, 51001, small, "none")
        record("Safety: same file name is not overwritten (saved as 'small (1).txt')",
               final == "completed" and (recv_b / "small (1).txt").exists())

        # ---- history ----
        _, ta = call(8000, "GET", "/api/transfers")
        _, tb = call(8001, "GET", "/api/transfers")
        sent = [t for t in ta["transfers"] if t["direction"] == "sent"]
        got = [t for t in tb["transfers"] if t["direction"] == "received"]
        record("History: every transfer is recorded as completed on both sides",
               len(sent) == len(got) == 6 and all(t["status"] == "completed" for t in sent + got),
               f"sender {len(sent)}, receiver {len(got)}")

        # ---- failure path ----
        _, db = call(8001, "GET", "/api/devices")
        a_on_b = [d for d in db["devices"] if d["is_trusted"]]
        if a_on_b:
            call(8001, "DELETE", f"/api/devices/{a_on_b[0]['device_id']}")
        final, _ = send(8000, b_id, peer_ip, 51001, small, "none")
        record("Failure path: sending to a device that no longer trusts us ends as 'failed'", final == "failed", f"status={final}")

    finally:
        for p in (proc_a, proc_b):
            if p:
                stop(p)
        failed = [n for s, n in results if s == "FAIL"]
        if failed:
            for lp in (logs / "Check-A.log", logs / "Check-B.log"):
                if lp.exists():
                    print(f"\n--- last lines of {lp.name} ---")
                    print("\n".join(lp.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]))
        counts = {k: sum(1 for s, _ in results if s == k) for k in ("PASS", "WARN", "FAIL")}
        print(f"\n=== {counts['PASS']} passed, {counts['WARN']} warnings, {counts['FAIL']} failed ===")
        time.sleep(1)
        shutil.rmtree(work, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
