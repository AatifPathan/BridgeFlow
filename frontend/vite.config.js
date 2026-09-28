import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Forwards API/WebSocket calls to the backend during `npm run dev`,
    // so the frontend code can always use relative paths ("/api/...")
    // and work unchanged once it's built and served BY the backend
    // itself in the packaged app (see build_release.py).
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
