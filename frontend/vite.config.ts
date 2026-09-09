import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const base = process.env.VITE_BASE_PATH || "/";

export default defineConfig({
  plugins: [react()],
  base: base.endsWith("/") ? base : `${base}/`,
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/be/api": {
        target: "http://127.0.0.1:8200",
        changeOrigin: true,
      },
    },
  },
});
