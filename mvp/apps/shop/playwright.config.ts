import { defineConfig, devices } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };

const PORT = Number(process.env.SHOP_PORT ?? 5173);

/**
 * a11y.spec.ts runs against the static shop (no backend needed).
 * e2e.spec.ts needs the session server + demo store running with SEARCH_MODE=seeded and TTB_E2E=1.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.SHOP_URL ?? `http://localhost:${PORT}`,
    trace: "retain-on-failure",
    locale: "hi-IN",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        permissions: ["microphone", "camera"],
        launchOptions: {
          args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"],
        },
      },
    },
  ],
  webServer: process.env.SHOP_URL
    ? undefined
    : {
        command: `npx vite --port ${PORT} --strictPort`,
        port: PORT,
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
