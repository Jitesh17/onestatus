import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api to the FastAPI backend so the frontend code uses clean relative URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: p => p.replace(/^\/api/, "") } },
  },
});
