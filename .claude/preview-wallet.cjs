#!/usr/bin/env node
/**
 * Isolated frontend dev server for previewing the wallet work.
 *
 * Same isolation contract as preview-frontend.cjs (own NEXT_DIST_DIR, own
 * non-3000 port) — but this one ALSO points the Next dev server's API rewrite
 * at a backend that actually has the new wallet routes.
 *
 * Why: `next.config.ts` proxies /api/v1 to `BACKEND_ORIGIN` (default
 * :8000). The canonical :8000 server belongs to another session and was
 * started before the wallet changes, so it does not serve /wallet/transfer,
 * /wallet/withdrawals or /admin/wallet. Pointing this preview at a fresh
 * backend on :8001 makes the new UI work end-to-end without touching the
 * other session's server.
 *
 * Positional args: [port] [distDir]. BACKEND_ORIGIN env overrides the target.
 */
const { spawn } = require("child_process");
const path = require("path");

const frontendDir = path.resolve(__dirname, "..", "frontend");
const port = process.argv[2] || process.env.PORT || "3500";
const distDir = process.argv[3] || process.env.PREVIEW_DIST_DIR || ".next-wallet-3500";
const backendOrigin = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8001";

if (distDir === ".next") {
  console.error(
    "[preview-wallet] refusing to start: dist dir must not be the canonical .next."
  );
  process.exit(1);
}

const nextBin = path.join(frontendDir, "node_modules", "next", "dist", "bin", "next");
const child = spawn(process.execPath, [nextBin, "dev", "--turbopack", "-p", port], {
  cwd: frontendDir,
  stdio: "inherit",
  env: { ...process.env, NEXT_DIST_DIR: distDir, BACKEND_ORIGIN: backendOrigin },
  shell: false,
});

child.on("exit", (code, signal) => {
  process.exit(signal ? 1 : code ?? 0);
});

for (const sig of ["SIGINT", "SIGTERM"]) {
  process.on(sig, () => child.kill(sig));
}
