import { useEffect, useState } from "react";
import { api } from "../services/api";
import { formatBytes, statusBadgeClass, statusLabel } from "../services/format";

export default function Dashboard({ setPage }) {
  const [devices, setDevices] = useState([]);
  const [transfers, setTransfers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listDevices(), api.listTransfers()])
      .then(([d, t]) => {
        setDevices(d.devices);
        setTransfers(t.transfers);
      })
      .finally(() => setLoading(false));
  }, []);

  const onlineCount = devices.filter((d) => d.online).length;
  const trustedCount = devices.filter((d) => d.is_trusted).length;
  const completedCount = transfers.filter((t) => t.status === "completed").length;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="page-subtitle">A quick look at your local network and recent activity.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setPage("send")}>
          Send a file
        </button>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 24 }}>
        <div className="card">
          <p className="stat-label">Devices online</p>
          <p className="stat-value">{loading ? "—" : onlineCount}</p>
        </div>
        <div className="card">
          <p className="stat-label">Paired devices</p>
          <p className="stat-value">{loading ? "—" : trustedCount}</p>
        </div>
        <div className="card">
          <p className="stat-label">Transfers completed</p>
          <p className="stat-value">{loading ? "—" : completedCount}</p>
        </div>
      </div>

      <div className="card">
        <p className="stat-label" style={{ marginBottom: 14 }}>
          Recent transfers
        </p>
        {transfers.length === 0 ? (
          <div className="empty-state">
            No transfers yet. Pair with a nearby device and send your first file.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Peer</th>
                <th>Direction</th>
                <th>Size</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {transfers.slice(0, 6).map((t) => (
                <tr key={t.transfer_id}>
                  <td>{t.item_name}</td>
                  <td className="muted">{t.peer_device_name}</td>
                  <td className="mono muted">{t.direction}</td>
                  <td className="mono">{formatBytes(t.original_size)}</td>
                  <td>
                    <span className={`badge ${statusBadgeClass(t.status)}`}>
                      {statusLabel(t.status)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
