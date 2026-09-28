const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: "◧" },
  { key: "devices", label: "Devices", icon: "◎" },
  { key: "send", label: "Send", icon: "↑" },
  { key: "receive", label: "Receive", icon: "↓" },
  { key: "history", label: "History", icon: "▤" },
  { key: "settings", label: "Settings", icon: "⚙" },
];

export default function Sidebar({ page, setPage, deviceName }) {
  return (
    <aside className="sidebar">
      <div className="wordmark">
        Bridge<span className="dot">Flow</span>
      </div>
      <div className="device-tag">{deviceName || "this device"}</div>

      <nav className="nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            className={`nav-item ${page === item.key ? "active" : ""}`}
            onClick={() => setPage(item.key)}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">LAN peer-to-peer · no cloud</div>
    </aside>
  );
}
