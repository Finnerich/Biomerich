import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND = process.env.VITE_BACKEND || "http://127.0.0.1:8000";
const BACKEND_WS = BACKEND.replace(/^http/, "ws");

export default defineConfig({
  plugins: [react()],
  define: {
    __RELEASE__: JSON.stringify(process.env.SOLRICH_RELEASE === "1"),
  },
  base: "./",
  server: {
    proxy: {
      "/ws": { target: BACKEND_WS, ws: true },
      "/eel.js": { target: BACKEND },
    },
  },
  build: {
    outDir: "../web-react-dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
          vendor: ["zustand", "qrcode.react"],
        },
      },
    },
  },
});
