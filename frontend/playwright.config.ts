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

const parsedUrl = new URL(baseURL);
const serverPort = parsedUrl.port || "3000";
const serverCommand =
  serverPort === "3000"
    ? "npm run dev"
    : `node ../.claude/preview-frontend.cjs ${serverPort} .next-preview${serverPort === "3100" ? "" : `-${serverPort}`}`;

export default defineConfig({
  testDir: "./tests/e2e",
  // An accessibility violation is a real failure, so no retries to paper over
  // one: a flaky a11y result is a result nobody trusts.
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
    extraHTTPHeaders: {
      "X-Forwarded-For": `10.97.${Math.floor(Math.random() * 200) + 1}.${Math.floor(Math.random() * 200) + 1}, 10.0.0.1`,
    },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Long suites against the dev server run several heavy pages back to
        // back; the default renderer can OOM-crash mid-suite on this box
        // ("Target page, context or browser has been closed" with no server
        // error). A leaner renderer keeps the browser alive for the whole run.
        launchOptions: {
          args: [
            "--disable-dev-shm-usage",
            "--js-flags=--max-old-space-size=1024",
          ],
        },
      },
    },
  ],
  ...(skipWebServer
    ? {}
    : {
        webServer: {
          command: serverCommand,
          url: baseURL,
          reuseExistingServer: true,
          timeout: 120_000,
        },
      }),
});
