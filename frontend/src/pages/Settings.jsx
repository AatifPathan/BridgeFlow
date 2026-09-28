import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function Settings() {
  const [settings, setSettings] = useState({ device_name: "" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getSettings().then(setSettings);
  }, []);

  async function handleSave() {
    await api.updateSettings({ device_name: settings.device_name });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Settings</h1>
          <p className="page-subtitle">Device identity and network configuration.</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <div className="field">
          <label>Device name</label>
          <input
            value={settings.device_name || ""}
            onChange={(e) => setSettings({ ...settings, device_name: e.target.value })}
          />
          <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            This is the name other devices see when they discover you. Takes effect
            after restarting Bridge Flow.
          </p>
        </div>

        <button className="btn btn-primary" onClick={handleSave}>
          {saved ? "Saved" : "Save changes"}
        </button>
      </div>

      <div className="card" style={{ maxWidth: 480, marginTop: 16 }}>
        <p className="stat-label" style={{ marginBottom: 10 }}>
          Network
        </p>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <span className="muted">Discovery port (UDP)</span>
          <span className="mono">50999</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span className="muted">Transfer port (TCP)</span>
          <span className="mono">51000</span>
        </div>
      </div>
    </>
  );
}
