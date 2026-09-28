/**
 * Bridge Flow - REST API client
 *
 * Thin fetch wrappers around every FastAPI route in backend/api/.
 * Uses relative paths (not an absolute host:port) so this same built
 * code works both in `npm run dev` (proxied to :8000 by vite.config.js)
 * and in the packaged app, where the frontend is served BY the backend
 * on whatever port it's running on - no hardcoded origin to get wrong.
 */

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Devices
  listDevices: () => request("/api/devices"),
  unpairDevice: (deviceId) => request(`/api/devices/${deviceId}`, { method: "DELETE" }),

  // Pairing
  requestPairing: (peerIp, peerPort) =>
    request("/api/pairing/request", {
      method: "POST",
      body: JSON.stringify({ peer_ip: peerIp, peer_port: peerPort }),
    }),
  incomingPairingRequests: () => request("/api/pairing/incoming"),
  confirmPairing: (peerIp, peerPort, code) =>
    request("/api/pairing/confirm", {
      method: "POST",
      body: JSON.stringify({ peer_ip: peerIp, peer_port: peerPort, code }),
    }),

  // Transfers
  listTransfers: () => request("/api/transfers"),
  getTransfer: (transferId) => request(`/api/transfers/${transferId}`),
  sendTransfer: (payload) =>
    request("/api/transfers", { method: "POST", body: JSON.stringify(payload) }),
  resumeTransfer: (transferId, payload) =>
    request(`/api/transfers/${transferId}/resume`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Settings
  getSettings: () => request("/api/settings"),
  updateSettings: (payload) =>
    request("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),

  // Health
  health: () => request("/api/health"),
};
