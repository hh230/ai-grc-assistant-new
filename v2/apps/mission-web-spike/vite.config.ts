import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The frontend is same-origin with the API via this proxy — so there is no CORS, and the browser
// only ever talks to "/v1/...". The API host (grc-api dev app) runs on :8099.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5199,
    proxy: {
      "/v1": "http://localhost:8099",
      "/health": "http://localhost:8099",
    },
  },
});
