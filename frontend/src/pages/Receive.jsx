import { useEffect, useState } from "react";
import ProgressBar from "../components/ProgressBar";
import { api } from "../services/api";
import { useTransferProgressWS } from "../services/ws";
import { formatBytes, statusBadgeClass, statusLabel } from "../services/format";

export default function Receive() {
  const [received, setReceived] = useState([]);
  const [progress, setProgress] = useState(null);

  const refresh = () =>
    api.listTransfers().then((t) => setReceived(t.transfers.filter((x) => x.direction === "received")));

  useEffect(() => {
    refresh();
    const poll = setInterval(refresh, 2500);
    return () => clearInterval(poll);
  }, []);

  const activeTransfer = received.find((t) => t.status === "in_progress");

  useTransferProgressWS(activeTransfer?.transfer_id, (event) => {
    if (event.event === "progress") setProgress(event);
    else {
      setProgress(null);
      refresh();
    }
  });

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Receive</h1>
          <p className="page-subtitle">
            Incoming transfers from paired devices are accepted automatically and saved to{" "}
            <span className="mono">storage/received/</span>.
          </p>
        </div>
      </div>

      {activeTransfer && progress && (
        <div className="card" style={{ marginBottom: 20 }}>
          <p className="stat-label" style={{ marginBottom: 12 }}>
            Receiving "{activeTransfer.item_name}" from {activeTransfer.peer_device_name}
          </p>
          <ProgressBar
            percent={progress.percent}
            speed={progress.speed_bytes_per_sec}
            eta={progress.eta_seconds}
            bytesDone={progress.bytes_done}
            totalBytes={progress.total_bytes}
          />
        </div>
      )}

      {received.length === 0 ? (
        <div className="empty-state">
          Nothing received yet. Once a paired device sends you something, it'll show up here.
        </div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>From</th>
              <th>Size</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {received.map((t) => (
              <tr key={t.transfer_id}>
                <td>{t.item_name}</td>
                <td className="muted">{t.peer_device_name}</td>
                <td className="mono">{formatBytes(t.original_size)}</td>
                <td>
                  <span className={`badge ${statusBadgeClass(t.status)}`}>{statusLabel(t.status)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
