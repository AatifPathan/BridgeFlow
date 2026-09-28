import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Devices from "./pages/Devices";
import Send from "./pages/Send";
import Receive from "./pages/Receive";
import History from "./pages/History";
import Settings from "./pages/Settings";
import { api } from "./services/api";

const PAGES = {
  dashboard: Dashboard,
  devices: Devices,
  send: Send,
  receive: Receive,
  history: History,
  settings: Settings,
};

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [deviceName, setDeviceName] = useState("");
  const [apiOnline, setApiOnline] = useState(true);

  useEffect(() => {
    api
      .getSettings()
      .then((s) => setDeviceName(s.device_name))
      .catch(() => setApiOnline(false));
  }, []);

  const Page = PAGES[page];

  return (
    <div className="app-shell">
      <Sidebar page={page} setPage={setPage} deviceName={deviceName} />
      <main className="main">
        {!apiOnline && (
          <div className="card" style={{ borderColor: "var(--danger)", marginBottom: 20 }}>
            Can't reach the Bridge Flow backend at <span className="mono">localhost:8000</span>.
            Make sure <span className="mono">python main.py</span> is running in{" "}
            <span className="mono">backend/</span>.
          </div>
        )}
        <Page setPage={setPage} />
      </main>
    </div>
  );
}
