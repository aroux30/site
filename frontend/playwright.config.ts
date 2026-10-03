import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the accessibility suite.
 *
 * `@axe-core/playwright` was in `package.json` and no file used it, and there
 * was no Playwright config at all — so `npm run test:e2e` resolved to nothing
 * and the accessibility dependency was decoration. This config is what makes
 * the axe spec actually run.
 *
 * It points at a dev server on :3000 by default. Set `PLAYWRIGHT_BASE_URL` to
 * run against a different origin (a preview deploy), and `PW_SKIP_WEBSERVER=1`
 * to skip launching one when a server is already up.
 */
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const skipWebServer = process.env.PW_SKIP_WEBSERVER === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  // An accessibility violation is a real failure, so no retries to paper over
  // one: a flaky a11y result is a result nobody trusts.
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  ...(skipWebServer
    ? {}
    : {
        webServer: {
          command: "npm run dev",
          url: baseURL,
          reuseExistingServer: true,
          timeout: 120_000,
        },
      }),
});
