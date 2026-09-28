export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatSpeed(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec <= 0) return "—";
  return `${formatBytes(bytesPerSec)}/s`;
}

export function formatEta(seconds) {
  if (seconds === undefined || seconds === null || seconds < 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

export function formatTimestamp(unixSeconds) {
  if (!unixSeconds) return "—";
  const date = new Date(parseFloat(unixSeconds) * 1000);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function statusLabel(status) {
  const map = {
    pending: "Pending",
    in_progress: "In progress",
    paused: "Paused",
    interrupted: "Interrupted",
    resumed: "Resumed",
    completed: "Completed",
    failed: "Failed",
    rejected: "Rejected",
  };
  return map[status] || status;
}

export function statusBadgeClass(status) {
  if (status === "completed") return "badge-online";
  if (["failed", "rejected"].includes(status)) return "badge-danger";
  if (["interrupted", "paused"].includes(status)) return "badge-warn";
  return "badge-offline";
}
