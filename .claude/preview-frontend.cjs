#!/usr/bin/env node
/**
 * Isolated frontend dev server for previewing alongside another session's server.
 *
 * Why this exists: `frontend/.next` is shared by every `next dev` on this tree and
 * Next does not lock it, so two servers clobber each other's manifests and the site
 * 500s on every route. A second session therefore cannot simply take :3000 — the
 * canonical dev server there has to stay usable at all times (see COORDINATION.md
 * Rule 2, and the concurrent-dev-servers incident of 2026-09-26).
 *
 * So this wrapper varies BOTH halves of the identity:
 *   - NEXT_DIST_DIR  gives this server its own build directory, leaving .next alone
 *   - a non-3000 port keeps it off the canonical server's socket
 *
 * Written as a Node script rather than an inline env prefix because `cross-env` is
 * not a dependency and launch.json runs commands directly (no shell to prefix in).
 *
 * Env overrides: PORT (honoured first so launch.json's autoPort can hand us a free
 * port), then PREVIEW_PORT (default 3100), and PREVIEW_DIST_DIR (default .next-preview).
 * Positional args [port] [distDir] override both env vars, which is how a third
 * session gets its own launch.json entry without a copy of this script. The
 * two-arg defaults are unchanged, so the 3100 config other sessions rely on keeps
 * behaving exactly as before.
 */
const { spawn } = require("child_process");
const path = require("path");

const frontendDir = path.resolve(__dirname, "..", "frontend");
// PORT wins because that is the variable a launch.json autoPort fallback sets; if we
// ignored it the tool would advertise a port we are not listening on.
const port = process.argv[2] || process.env.PORT || process.env.PREVIEW_PORT || "3100";
const distDir = process.argv[3] || process.env.PREVIEW_DIST_DIR || ".next-preview";

// Guard the invariant this script exists to protect: the isolated dist dir must
// never be the one the canonical :3000 server is writing to.
if (distDir === ".next") {
  console.error(
    "[preview-frontend] refusing to start: PREVIEW_DIST_DIR=.next would collide " +
      "with the canonical dev server on :3000."
  );
  process.exit(1);
}

const nextBin = path.join(frontendDir, "node_modules", "next", "dist", "bin", "next");
// --turbopack matches the project's own `dev` script (next dev --turbopack);
// without it this server would compile differently from the canonical one.
const child = spawn(process.execPath, [nextBin, "dev", "--turbopack", "-p", port], {
  cwd: frontendDir,
  stdio: "inherit",
  env: { ...process.env, NEXT_DIST_DIR: distDir },
  shell: false,
});

child.on("exit", (code, signal) => {
  process.exit(signal ? 1 : code ?? 0);
});

// Forward interrupts so preview_stop shuts the whole tree down.
for (const sig of ["SIGINT", "SIGTERM"]) {
  process.on(sig, () => child.kill(sig));
}
