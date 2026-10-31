import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  // dev server proxies the FastAPI backend so the UI uses relative /api URLs everywhere
  server: { proxy: { "/api": "http://127.0.0.1:8000", "/static": "http://127.0.0.1:8000", "/manifest.webmanifest": "http://127.0.0.1:8000", "/sw.js": "http://127.0.0.1:8000" } },
})
