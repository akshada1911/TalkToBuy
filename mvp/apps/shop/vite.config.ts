import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local dev proxies; in production Firebase Hosting rewrites the same paths (infra/firebase.json).
// No secret is ever bundled: the shop only calls the keyless /v1/demo-ticket (T034, Constitution III).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Build the widget from source (one bundle, no separate widget build needed for dev).
      "@talktobuy/assistant-widget": fileURLToPath(new URL("../../packages/assistant-widget/src/index.ts", import.meta.url)),
    },
  },
  // Only VITE_PUBLIC_* variables may reach the bundle, and only public URLs belong there.
  envPrefix: "VITE_PUBLIC_",
  server: {
    port: 5173,
    proxy: {
      "/v1": { target: "http://localhost:8080", ws: true },
      "/payment": "http://localhost:3000",
      "/demo": "http://localhost:3000",
    },
  },
});
