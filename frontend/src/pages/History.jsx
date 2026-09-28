import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import {
  formatBytes,
  formatTimestamp,
  statusBadgeClass,
  statusLabel,
} from "../services/format";

const FILTERS = ["all", "sent", "received", "interrupted", "failed"];

export default function History() {
  const [transfers, setTransfers] = useState([]);
  const [devices, setDevices] = useState([]);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [resumingId, setResumingId] = useState(null);
  const [message, setMessage] = useState(null);

  const refresh = () => api.listTransfers().then((t) => setTransfers(t.transfers));

  useEffect(() => {
    refresh();
    api.listDevices().then((d) => setDevices(d.devices));
  }, []);

  const filtered = useMemo(() => {
    return transfers.filter((t) => {
      if (filter === "sent" && t.direction !== "sent") return false;
      if (filter === "received" && t.direction !== "received") return false;
      if (filter === "interrupted" && t.status !== "interrupted") return false;
      if (filter === "failed" && t.status !== "failed") return false;
      if (search && !t.item_name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [transfers, filter, search]);

  async function handleResume(transfer) {
    const device = devices.find((d) => d.device_id === transfer.peer_device_id);
    if (!device) {
      setMessage("Can't resume — the original peer isn't in your device list anymore.");
      return;
    }
    setResumingId(transfer.transfer_id);
    setMessage(null);
    try {
      const result = await api.resumeTransfer(transfer.transfer_id, {
        transfer_id: transfer.transfer_id,
        peer_ip: device.ip,
        peer_port: device.tcp_port || 51000,
        peer_device_id: device.device_id,
      });
      setMessage(
        result.status === "completed"
          ? `Resumed and completed "${transfer.item_name}".`
          : `Resume ended with status: ${result.status}`
      );
      refresh();
    } catch (e) {
      setMessage(e.message);
    } finally {
      setResumingId(null);
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>History</h1>
          <p className="page-subtitle">Every transfer this device has sent or received.</p>
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, marginBottom: 18, alignItems: "center" }}>
        <div style={{ display: "flex", gap: 6 }}>
          {FILTERS.map((f) => (
            <button
              key={f}
              className="btn btn-small"
              style={
                filter === f
                  ? { background: "var(--accent-soft)", color: "var(--accent)", borderColor: "var(--accent)" }
                  : undefined
              }
              onClick={() => setFilter(f)}
            >
              {f[0].toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        <input
          placeholder="Search by name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 220, marginLeft: "auto" }}
        />
      </div>

      {message && (
        <p className="muted" style={{ fontSize: 13, marginBottom: 14 }}>
          {message}
        </p>
      )}

      {filtered.length === 0 ? (
        <div className="empty-state">No matching transfers.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Peer</th>
              <th>Direction</th>
              <th>Size</th>
              <th>Compression</th>
              <th>Status</th>
              <th>Started</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.transfer_id}>
                <td>{t.item_name}</td>
                <td className="muted">{t.peer_device_name}</td>
                <td className="mono muted">{t.direction}</td>
                <td className="mono">{formatBytes(t.original_size)}</td>
                <td className="muted">
                  {t.compressed_size !== null && t.compressed_size !== undefined
                    ? `${t.compression_mode} · ${formatBytes(t.compressed_size)}` +
                      (t.original_size
                        ? ` (${Math.max(0, Math.round((1 - t.compressed_size / t.original_size) * 100))}% saved)`
                        : "")
                    : t.compression_mode}
                </td>
                <td>
                  <span className={`badge ${statusBadgeClass(t.status)}`}>{statusLabel(t.status)}</span>
                </td>
                <td className="muted mono" style={{ fontSize: 11.5 }}>
                  {formatTimestamp(t.started_at)}
                </td>
                <td>
                  {t.status === "interrupted" && t.direction === "sent" && (
                    <button
                      className="btn btn-small"
                      onClick={() => handleResume(t)}
                      disabled={resumingId === t.transfer_id}
                    >
                      {resumingId === t.transfer_id ? "Resuming..." : "Resume"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
