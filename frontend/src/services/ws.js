/**
 * Bridge Flow - WebSocket client
 *
 * Two small React hooks wrapping the backend's /ws/devices and
 * /ws/transfers/{id} endpoints, so components get live updates
 * without polling. Builds the WebSocket URL from the CURRENT page's
 * host/protocol rather than a hardcoded one, so it works unchanged
 * whether the page is served by Vite's dev proxy or by the packaged
 * app serving itself on one port.
 */

import { useEffect, useRef, useState } from "react";

function wsUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

export function useDeviceStatusWS() {
  const [devices, setDevices] = useState([]);
  const socketRef = useRef(null);

  useEffect(() => {
    const socket = new WebSocket(wsUrl("/ws/devices"));
    socketRef.current = socket;

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setDevices(data.devices || []);
    };
    socket.onerror = () => {
      /* REST polling in the Devices page still covers this if the
         socket fails to connect - WS is a live-update enhancement,
         not the only data source. */
    };

    return () => socket.close();
  }, []);

  return devices;
}

export function useTransferProgressWS(transferId, onEvent) {
  useEffect(() => {
    if (!transferId) return undefined;

    const socket = new WebSocket(wsUrl(`/ws/transfers/${transferId}`));
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onEvent(data);
    };

    return () => socket.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transferId]);
}
