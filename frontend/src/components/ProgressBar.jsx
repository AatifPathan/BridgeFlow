import { formatBytes, formatEta, formatSpeed } from "../services/format";

export default function ProgressBar({ percent = 0, speed, eta, bytesDone, totalBytes }) {
  return (
    <div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${Math.min(100, percent)}%` }} />
      </div>
      <div className="progress-meta">
        <span>
          {formatBytes(bytesDone)} / {formatBytes(totalBytes)}
        </span>
        <span>{percent.toFixed(1)}%</span>
        <span>{formatSpeed(speed)}</span>
        <span>ETA {formatEta(eta)}</span>
      </div>
    </div>
  );
}
