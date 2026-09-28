import { useEffect, useState } from "react";
import DeviceCard from "../components/DeviceCard";
import { api } from "../services/api";
import { useDeviceStatusWS } from "../services/ws";

export default function Devices() {
  const [devices, setDevices] = useState([]);
  const [pairingTarget, setPairingTarget] = useState(null); // device we're confirming a code for
  const [codeInput, setCodeInput] = useState("");
  const [incoming, setIncoming] = useState([]);
  const [message, setMessage] = useState(null);
  const [manualIp, setManualIp] = useState("");
  const [manualPort, setManualPort] = useState("51000");

  const liveDevices = useDeviceStatusWS();

  const refresh = () => api.listDevices().then((d) => setDevices(d.devices));

  useEffect(() => {
    refresh();
    const poll = setInterval(() => {
      refresh();
      api.incomingPairingRequests().then((r) => setIncoming(r.requests));
    }, 3000);
    return () => clearInterval(poll);
  }, []);

  // Merge live WS online/offline status over the REST snapshot without losing pairing info.
  const merged = devices.map((d) => {
    const live = liveDevices.find((l) => l.device_id === d.device_id);
    return live ? { ...d, online: live.online } : d;
  });

  async function handlePairClick(device) {
    setMessage(null);
    try {
      await api.requestPairing(device.ip, device.tcp_port || 51000);
      setPairingTarget(device);
      setMessage(`Code requested. Ask the person on "${device.device_name}" for the code shown on their screen.`);
    } catch (e) {
      setMessage(e.message);
    }
  }

  async function handleConfirm() {
    if (!pairingTarget || !codeInput) return;
    try {
      await api.confirmPairing(pairingTarget.ip, pairingTarget.tcp_port || 51000, codeInput);
      setMessage(`Paired with ${pairingTarget.device_name}.`);
      setPairingTarget(null);
      setCodeInput("");
      refresh();
    } catch (e) {
      setMessage(e.message);
    }
  }

  // For devices on a DIFFERENT network: broadcast discovery can't reach them,
  // so pair by typing the IP address (and port) directly.
  async function handlePairByIp() {
    setMessage(null);
    const ip = manualIp.trim();
    const port = Number(manualPort) || 51000;
    try {
      await api.requestPairing(ip, port);
      setPairingTarget({ ip, tcp_port: port, device_name: ip });
      setMessage(`Code requested from ${ip}. Read the code shown on that device's Devices page.`);
    } catch (e) {
      setMessage(e.message);
    }
  }

  async function handleUnpair(device) {
    await api.unpairDevice(device.device_id);
    refresh();
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Devices</h1>
          <p className="page-subtitle">Everyone running Bridge Flow on this Wi-Fi shows up here.</p>
        </div>
      </div>

      {incoming.length > 0 && (
        <div className="card" style={{ marginBottom: 20, borderColor: "var(--accent)" }}>
          <p className="stat-label">Incoming pairing request</p>
          {incoming.map((req) => (
            <div key={req.requester_device_id} style={{ marginTop: 6 }}>
              A device wants to pair. Read them this code:{" "}
              <span className="mono" style={{ fontSize: 20, color: "var(--accent)", fontWeight: 700 }}>
                {req.code}
              </span>
            </div>
          ))}
        </div>
      )}

      {pairingTarget && (
        <div className="card" style={{ marginBottom: 20 }}>
          <p className="stat-label">Enter the code shown on "{pairingTarget.device_name}"</p>
          <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
            <input
              className="mono"
              placeholder="6-digit code"
              value={codeInput}
              onChange={(e) => setCodeInput(e.target.value)}
              maxLength={6}
              style={{ maxWidth: 160 }}
            />
            <button className="btn btn-primary" onClick={handleConfirm}>
              Confirm pairing
            </button>
            <button className="btn" onClick={() => setPairingTarget(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {message && (
        <p className="muted" style={{ marginBottom: 16, fontSize: 13 }}>
          {message}
        </p>
      )}

      <div className="card" style={{ marginBottom: 20 }}>
        <p className="stat-label">Device on a different network? Pair by IP address</p>
        <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
          <input
            className="mono"
            placeholder="IP address, e.g. 20.51.10.4"
            value={manualIp}
            onChange={(e) => setManualIp(e.target.value)}
            style={{ maxWidth: 240 }}
          />
          <input
            className="mono"
            placeholder="Port"
            value={manualPort}
            onChange={(e) => setManualPort(e.target.value)}
            style={{ maxWidth: 100 }}
          />
          <button className="btn" onClick={handlePairByIp} disabled={!manualIp.trim()}>
            Pair by IP
          </button>
        </div>
      </div>

      {merged.length === 0 ? (
        <div className="empty-state">
          No devices found yet. Open Bridge Flow on another laptop on the same Wi-Fi.
        </div>
      ) : (
        merged.map((device) => (
          <DeviceCard
            key={device.device_id}
            device={device}
            onPair={handlePairClick}
            onUnpair={handleUnpair}
          />
        ))
      )}
    </>
  );
}
