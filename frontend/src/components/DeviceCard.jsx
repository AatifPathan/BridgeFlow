export default function DeviceCard({ device, onPair, onUnpair, onSelect, selectable }) {
  return (
    <div
      className="device-card"
      style={selectable ? { cursor: "pointer" } : undefined}
      onClick={selectable ? () => onSelect(device) : undefined}
    >
      <div>
        <div className="device-name">{device.device_name}</div>
        <div className="device-ip">
          {device.ip || "unknown ip"}
          {device.tcp_port ? `:${device.tcp_port}` : ""}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span className={`badge ${device.online ? "badge-online" : "badge-offline"}`}>
          <span className="dot" />
          {device.online ? "Online" : "Offline"}
        </span>

        {device.is_trusted ? (
          <span className="badge badge-offline">Paired</span>
        ) : (
          onPair && (
            <button
              className="btn btn-small"
              onClick={(e) => {
                e.stopPropagation();
                onPair(device);
              }}
              disabled={!device.online}
            >
              Pair
            </button>
          )
        )}

        {device.is_trusted && onUnpair && (
          <button
            className="btn btn-small btn-danger"
            onClick={(e) => {
              e.stopPropagation();
              onUnpair(device);
            }}
          >
            Unpair
          </button>
        )}
      </div>
    </div>
  );
}
