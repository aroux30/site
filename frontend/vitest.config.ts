import { defineConfig } from "vitest/config";
import path from "node:path";

/**
 * Vitest config.
 *
 * The suite was removed once and `npm test` then passed with zero tests, which
 * reads exactly like a passing suite. This config exists so a test file under
 * tests/ is always discovered and the path alias resolves, and so
 * `--passWithNoTests` cannot hide an empty run: a suite with no files is an
 * error here on purpose.
 */
export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    globals: true,
    // Fail rather than pass on an empty run. `npm test` reporting success with
    // nothing executed is the failure mode this guards.
    passWithNoTests: false,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
  },
});
