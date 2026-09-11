import { defineConfig } from "vite";
import reactPlugin from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [reactPlugin()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:9090",
      "/healthz": "http://127.0.0.1:9090",
      "/readyz": "http://127.0.0.1:9090",
    },
  },
});