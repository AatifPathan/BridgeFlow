import { useEffect, useState } from "react";
import ProgressBar from "../components/ProgressBar";
import { api } from "../services/api";
import { useTransferProgressWS } from "../services/ws";
import { formatBytes } from "../services/format";

const TERMINAL = ["completed", "failed", "interrupted", "rejected"];

const FINAL_MESSAGES = {
  completed: "Transfer complete",
  failed: "Transfer failed",
  interrupted: "Transfer interrupted - you can resume it from History",
  rejected: "The other device rejected the transfer",
};

export default function Send() {
  const [devices, setDevices] = useState([]);
  const [peerId, setPeerId] = useState("");
  const [sourcePath, setSourcePath] = useState("");
  const [compression, setCompression] = useState("none");

  // idle -> preparing (compress + hash) -> sending -> done
  const [phase, setPhase] = useState("idle");
  const [transfer, setTransfer] = useState(null); // API reply: id + compression stats
  const [progress, setProgress] = useState(null);
  const [finalStatus, setFinalStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listDevices().then((d) => setDevices(d.devices.filter((x) => x.is_trusted)));
  }, []);

  function finish(status) {
    setFinalStatus(status);
    setPhase("done");
  }

  // Live progress + terminal events pushed over the WebSocket.
  useTransferProgressWS(transfer?.transfer_id, (event) => {
    if (event.event === "progress") setProgress(event);
    else if (TERMINAL.includes(event.event)) finish(event.event);
  });

  // The database is the source of truth: poll it too, so the final result
  // is never missed even if the WebSocket connected after the last event.
  useEffect(() => {
    if (phase !== "sending" || !transfer) return undefined;
    const timer = setInterval(async () => {
      try {
        const t = await api.getTransfer(transfer.transfer_id);
        if (TERMINAL.includes(t.status)) finish(t.status);
      } catch {
        /* keep polling */
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [phase, transfer]);

  const selectedDevice = devices.find((d) => d.device_id === peerId);
  const busy = phase === "preparing" || phase === "sending";

  async function handleSend() {
    setError(null);
    setTransfer(null);
    setProgress(null);
    setFinalStatus(null);
    if (!selectedDevice || !sourcePath) {
      setError("Pick a paired device and enter a file or folder path.");
      return;
    }
    setPhase("preparing");
    try {
      const res = await api.sendTransfer({
        peer_device_id: selectedDevice.device_id,
        peer_ip: selectedDevice.ip,
        peer_port: selectedDevice.tcp_port || 51000,
        peer_device_name: selectedDevice.device_name,
        source_path: sourcePath,
        compression_mode: compression,
      });
      setTransfer(res);
      setPhase("sending");
    } catch (e) {
      setError(e.message);
      setPhase("idle");
    }
  }

  const hasCompressionStats = transfer && transfer.compressed_size !== null && transfer.compressed_size !== undefined;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Send</h1>
          <p className="page-subtitle">Send a file or folder directly to a paired device.</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 560 }}>
        <div className="field">
          <label>Destination device</label>
          <select value={peerId} onChange={(e) => setPeerId(e.target.value)} disabled={busy}>
            <option value="">Select a paired device...</option>
            {devices.map((d) => (
              <option key={d.device_id} value={d.device_id}>
                {d.device_name} {d.online ? "" : "(offline)"}
              </option>
            ))}
          </select>
          {devices.length === 0 && (
            <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
              No paired devices yet - pair with someone on the Devices page first.
            </p>
          )}
        </div>

        <div className="field">
          <label>File or folder path</label>
          <input
            placeholder="C:\Users\you\Documents\report.pdf"
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
            disabled={busy}
          />
          <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            Bridge Flow runs on this computer, so it reads straight from this disk - type or
            paste the full path to the file or folder.
          </p>
        </div>

        <div className="field">
          <label>Compression</label>
          <select value={compression} onChange={(e) => setCompression(e.target.value)} disabled={busy}>
            <option value="none">None - send as-is</option>
            <option value="standard">Standard</option>
            <option value="max">Maximum</option>
          </select>
          <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            Folders are always zipped for transfer. Photos, videos, MP3s and ZIPs are already
            compressed, so compressing them saves little or nothing.
          </p>
        </div>

        <button className="btn btn-primary" onClick={handleSend} disabled={busy}>
          {phase === "preparing" ? "Compressing & hashing..." : phase === "sending" ? "Sending..." : "Start transfer"}
        </button>

        {error && <p style={{ color: "var(--danger)", fontSize: 13, marginTop: 14 }}>{error}</p>}
      </div>

      {hasCompressionStats && (
        <div className="card" style={{ maxWidth: 560, marginTop: 16 }}>
          <p className="stat-label" style={{ marginBottom: 10 }}>Compression</p>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span className="muted">Original size</span>
            <span className="mono">{formatBytes(transfer.original_size)}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span className="muted">Sent as</span>
            <span className="mono">{formatBytes(transfer.compressed_size)}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="muted">Space saved</span>
            <span className="mono">
              {formatBytes(transfer.space_saved_bytes)} ({transfer.space_saved_percent}%)
            </span>
          </div>
          {transfer.space_saved_bytes === 0 && (
            <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
              No space saved - this content is probably already compressed (or too small to benefit).
            </p>
          )}
        </div>
      )}

      {phase !== "idle" && phase !== "preparing" && (
        <div className="card" style={{ maxWidth: 560, marginTop: 16 }}>
          <p className="stat-label" style={{ marginBottom: 12 }}>
            {phase === "done" ? FINAL_MESSAGES[finalStatus] || finalStatus : "Transferring..."}
          </p>
          {phase === "sending" && (
            progress ? (
              <ProgressBar
                percent={progress.percent}
                speed={progress.speed_bytes_per_sec}
                eta={progress.eta_seconds}
                bytesDone={progress.bytes_done}
                totalBytes={progress.total_bytes}
              />
            ) : (
              <p className="muted" style={{ fontSize: 13 }}>Connecting to the other device...</p>
            )
          )}
          {phase === "done" && finalStatus === "completed" && (
            <p className="muted" style={{ fontSize: 13 }}>
              SHA-256 verified - the file matches exactly on the receiving end.
            </p>
          )}
          {phase === "done" && finalStatus === "failed" && (
            <p className="muted" style={{ fontSize: 13 }}>
              Check the console window on both computers for the reason (a hash mismatch, or the
              devices are no longer paired, are the usual causes).
            </p>
          )}
        </div>
      )}
    </>
  );
}
