import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During local development / Playwright the browser talks to the API
// service through this same-origin proxy; in Docker the nginx image
// provides the equivalent /api and /health routes.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
