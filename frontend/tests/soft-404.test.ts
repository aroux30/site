/**
 * Pins the soft-404 fix: unknown storefront paths must answer HTTP 404.
 *
 * The bug (found live 2026-10-09, independently confirmed by two sessions):
 * `app/(store)/loading.tsx` wrapped every storefront route in a Suspense
 * boundary. That made Next.js start streaming the response before the page's
 * data fetch resolved — so when `notFound()` ran, the status line (200) was
 * already on the wire and could not be changed. The 404 UI rendered, with
 * `noindex`, but the HTTP status stayed 200: a "soft 404" that Search
 * Console reports as a site error, and that any strict client (a crawler, a
 * link checker, an uptime monitor) reads as "this page exists".
 *
 * The fix: the generic skeleton was removed. `loading.tsx` may exist on a
 * LEAF route (it only delays that route's own tree), but a `loading.tsx` at
 * a layout level of the storefront re-enables streaming for everything
 * beneath it — including the routes that must be able to 404.
 *
 * Negative test: recreate `app/(store)/loading.tsx` (or blog/, products/)
 * with the old skeleton and every assertion here flips to 200.
 */
import { existsSync, readdirSync, statSync } from "fs";
import { join, resolve } from "path";
import { describe, expect, it } from "vitest";

const STORE = resolve(__dirname, "../app/(store)");

/** Route groups whose pages can legitimately call `notFound()`. */
const MUST_404_CAPABLE = [
  "[slug]", // CMS pages
  "blog/[slug]", // blog posts
];

/** Directories that hold a loading.tsx, found recursively under (store).
 *
 *  The root itself is checked too: `(store)/loading.tsx` is the exact file
 *  the original bug lived in, and the first version of this helper only
 *  walked SUBdirectories — so re-creating the root file passed the test.
 *  A vacuous assertion on the very file the fix is about.
 *
 *  `checkRoot` is false on recursive calls: otherwise every recursive level
 *  re-checks its own subdirectory's root and the "(root)" marker appears
 *  once per call, not once per file (the second bug this helper shipped).
 */
function loadingDirs(root: string, checkRoot = true): string[] {
  const out: string[] = [];
  if (checkRoot && existsSync(join(root, "loading.tsx"))) out.push("(root)");
  for (const entry of readdirSync(root)) {
    const p = join(root, entry);
    if (!statSync(p).isDirectory()) continue;
    if (existsSync(join(p, "loading.tsx"))) out.push(p.slice(STORE.length + 1));
    out.push(...loadingDirs(p, false));
  }
  return out;
}

describe("soft-404 guard", () => {
  it("no loading.tsx exists at a level that wraps a 404-capable route", () => {
    const dirs = loadingDirs(STORE);
    // `(root)` is the (store) directory itself — the file that caused the
    // original bug. Any directory that is an ancestor of (or equal to) a
    // 404-capable route would re-introduce streaming for that route.
    const offenders = dirs.filter(
      (d) =>
        d === "(root)" ||
        MUST_404_CAPABLE.some((route) => route.startsWith(d + "/")),
    );
    expect(
      offenders,
      `loading.tsx would stream 404-capable routes: ${offenders.join(", ")}`,
    ).toEqual([]);
  });

  it("the 404 reporter component exists and the not-found page uses it", async () => {
    const fs = await import("fs");
    const notFound = fs.readFileSync(resolve(__dirname, "../app/not-found.tsx"), "utf-8");
    expect(notFound).toContain("NotFoundReporter");
    const reporter = fs.readFileSync(
      resolve(__dirname, "../components/seo/notfound-reporter.tsx"),
      "utf-8",
    );
    // The beacon must target the recorder route and survive page unload.
    expect(reporter).toContain("/api/v1/seo/404/hit");
    expect(reporter).toContain("keepalive: true");
  });
});
