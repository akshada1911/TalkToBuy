import { defineConfig } from "vitest/config";

export default defineConfig({
  build: {
    lib: {
      entry: "src/index.ts",
      formats: ["es"],
      fileName: () => "talktobuy-assistant.js",
    },
    sourcemap: true,
  },
  test: {
    environment: "happy-dom",
  },
});
