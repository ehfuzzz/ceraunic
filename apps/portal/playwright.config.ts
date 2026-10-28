// Smoke test config. Pattern from the Mile Buy Club repo (apps/web/playwright.marketing-render.config.ts):
// defineConfig + reuseExistingServer webServers, installed Chrome via channel "chrome" (no browser download).
// Default ports are Phase 10's: engine fixture API on :8787, portal on :3010. Start both yourself, or let the
// webServer entries do it (the portal one needs `pnpm build` first).
//   pnpm smoke                                   against http://localhost:3010
//   PORTAL_URL=https://<alias> pnpm smoke        against a hosted portal (webServers skipped)
import { defineConfig, devices } from "@playwright/test";

// localhost, not 127.0.0.1: next dev blocks its dev resources for other hostnames (allowedDevOrigins).
const portal = process.env.PORTAL_URL ?? "http://localhost:3010";
const local = !process.env.PORTAL_URL;
const port = new URL(portal).port || "3010";
const engine = process.env.ENGINE_ORIGIN ?? "http://127.0.0.1:8787";

export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.ts/,
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  reporter: [["list"]],
  webServer: local
    ? [
        {
          command: `uv run uvicorn wi.api.app:app --port ${new URL(engine).port || "8787"}`,
          cwd: "../..",
          url: `${engine}/api/v1/health`,
          reuseExistingServer: true,
          timeout: 60_000,
        },
        {
          command: `pnpm exec next start -p ${port}`,
          url: `${portal}/app/onboard`,
          reuseExistingServer: true,
          timeout: 120_000,
          env: { ENGINE_ORIGIN: engine },
        },
      ]
    : undefined,
  use: {
    baseURL: portal,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chrome",
      use: { ...devices["Desktop Chrome"], channel: "chrome", viewport: { width: 1440, height: 900 }, colorScheme: "light" },
    },
  ],
});
