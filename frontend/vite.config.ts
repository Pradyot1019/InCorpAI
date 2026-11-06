import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    port: 5173,
    // In dev, /api is proxied to FastAPI so no CORS setup is needed.
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
