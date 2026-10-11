/**
 * Real-browser verification sweep — the missing half of the 2026-10-03 acceptance.
 *
 * WHY THIS EXISTS
 * The CMS-gap program closed with two recorded limitations; the first was
 * "UI changes were never seen in a browser — the preview tool was unavailable,
 * so verification stopped at source + type-level." That gap is what let the
 * media edit chain ship with four independent breaks: every layer "existed"
 * and every static check was green (see the memory note `media-edit-chain-
 * never-worked`). A source-level pass cannot see a page that renders an error
 * boundary, a client that 404s its API, or a session that bounces to /login.
 *
 * This script opens the pages in a real Chromium, with a real admin session
 * created by really logging in — no forged token, because a forged one keeps
 * working after the signing scheme changes and would keep passing while the
 * real gate was untested (the lesson from verify-editor-toolbar.mjs).
 *
 * WHAT IT RECORDS, per page:
 *   - render exceptions (pageerror, uncaught promise rejections)
 *   - console errors
 *   - API responses the page itself issued: any 4xx/5xx is a finding, except a
 *     documented allowlist of shapes where "an error status" IS the correct
 *     answer for this fixture (e.g. an analytics window with no rows yet).
 *   - auth bounces: navigation that lands on /login while holding a live
 *     session — the classic silent expiry that reads as "empty page".
 *   - an empty-render heuristic: <body> with almost no text and no visible
 *     error — the "swallowed error reads as no orders" failure class.
 *
 * It writes screenshots for a curated set of pages to scripts/artifacts/sweep/
 * so a human can LOOK at the three surfaces the program touched most, and a
 * full JSON report so a later session can diff against it.
 *
 * RUN
 *   node scripts/verify-ui-live.mjs            # all admin routes
 *   node scripts/verify-ui-live.mjs --quick    # curated subset + screenshots
 *
 * Requirements: dev server on :3000, backend on :8000, admin credentials in
 * PROBE_ADMIN_PHONE / PROBE_ADMIN_PASSWORD (or ADMIN_PHONE / ADMIN_PASSWORD).
 * The local dev credentials used by every prior session are the fallback so
 * this runs out of the box on this machine only — never commit real ones.
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = join(HERE, "..");
const APP_DIR = join(FRONTEND, "app", "admin");
const SHOTS = join(FRONTEND, "scripts", "artifacts", "sweep");

const BASE = process.env.SWEEP_BASE ?? "http://localhost:3000";
const API = process.env.SWEEP_API ?? "http://127.0.0.1:8000/api/v1";
const PHONE = process.env.PROBE_ADMIN_PHONE ?? process.env.ADMIN_PHONE ?? "09120000000";
const PASSWORD = process.env.PROBE_ADMIN_PASSWORD ?? process.env.ADMIN_PASSWORD ?? "Admin@123456";
const QUICK = process.argv.includes("--quick");

/** Pages to screenshot even in a full run — the surfaces under heaviest change. */
const SCREENSHOT_PAGES = new Set([
  "/admin/dashboard",
  "/admin/media",
  "/admin/blog", // comments moderation is a tab INSIDE this page — /admin/comments is not a route (a first draft of this list said it was, and the sweep reported a 404 that was the list's fault, not the app's)
  "/admin/orders",
  "/admin/settings",
  "/admin/system-health",
  "/admin/editor-probe",
]);

/**
 * 4xx/5xx URL patterns where the error status is the CORRECT answer for this
 * fixture, so counting them would be a false positive. Each entry states why;
 * an unexplained allowlist entry is how a real break gets buried.
 */
const EXPECTED_ERROR_PATTERNS = [
  // Analytics/session pings when the session store has no rows yet.
  { re: /\/analytics\/.*(no-data|empty)/, why: "empty window is a valid answer" },
];

/** Discover every admin route from the filesystem — the same source the
 *  build uses, so a route that exists on disk can never be silently skipped. */
function discoverAdminRoutes() {
  const routes = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) {
        // Skip dynamic segments ([id]) from the automatic sweep — a made-up id
        // would 404 by design and prove nothing; those need real ids and are
        // handled explicitly below.
        if (/^\[.+\]$/.test(entry)) continue;
        walk(full);
      } else if (entry === "page.tsx") {
        const rel = relative(APP_DIR, dir).replace(/\\/g, "/");
        routes.push(rel === "" || rel === "." ? "/admin" : `/admin/${rel}`);
      }
    }
  };
  walk(APP_DIR);
  return routes.sort();
}

/** Curated quick subset: one page per major area, chosen to cover the domains
 *  the gap program closed (content, media, comments, users, settings,
 *  widgets, menus). */
const QUICK_ROUTES = [
  "/admin/dashboard",
  "/admin/blog",
  "/admin/pages",
  "/admin/media",
  "/admin/orders",
  "/admin/products",
  "/admin/users",
  "/admin/settings",
  "/admin/cms",
  "/admin/system-health",
  "/admin/editor-probe",
];

const results = [];
let consoleNoise = [];

async function loginAndGetCookies(context) {
  const res = await context.request.post(`${API}/auth/login`, {
    data: { phone: PHONE, password: PASSWORD },
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok()) {
    throw new Error(`admin login failed: ${res.status()} ${await res.text()}`);
  }
  // The cookies land on the API origin (localhost:8000), but every page's API
  // calls go through the frontend's own rewrite/proxy on :3000. Add the two
  // auth cookies to BOTH origins so the browser presents them wherever the
  // request goes — mirroring what the app expects in production (same-origin).
  const cookies = [];
  for (const h of res.headersArray()) {
    if (h.name.toLowerCase() !== "set-cookie") continue;
    const m = /^([^=]+)=([^;]*)/.exec(h.value);
    if (!m) continue;
    for (const domain of ["localhost", "127.0.0.1"]) {
      cookies.push({ name: m[1], value: m[2].trim(), domain, path: "/" });
    }
  }
  await context.addCookies(cookies);
  return cookies.length;
}

function isApiRequest(url) {
  return url.includes(":8000/") || url.includes("/api/");
}

function expectedError(url) {
  return EXPECTED_ERROR_PATTERNS.find((p) => p.re.test(url));
}

async function visit(context, route, { screenshot }) {
  const page = await context.newPage();
  const own = {
    route,
    finalUrl: null,
    status: null,
    pageErrors: [],
    consoleErrors: [],
    apiErrors: [],
    apiCount: 0,
    rateLimited: 0,
    authBounce: false,
    emptyish: false,
    bodyText: 0,
  };
  page.on("pageerror", (e) => own.pageErrors.push(String(e).slice(0, 300)));
  page.on("console", (m) => {
    if (m.type() === "error") own.consoleErrors.push(m.text().slice(0, 300));
  });
  page.on("response", async (r) => {
    const url = r.url();
    if (!isApiRequest(url)) return;
    own.apiCount += 1;
    // 429 is the sweep's own load, not a finding: 70+ pages visited back to
    // back trip the API's rate limiter, and counting those as page errors
    // buries the pages that are actually broken. They are counted separately
    // so the report can still say "this page was not fully assessed".
    if (r.status() === 429) {
      own.rateLimited += 1;
      return;
    }
    if (r.status() >= 400) {
      const allow = expectedError(url);
      own.apiErrors.push({
        status: r.status(),
        url: url.slice(0, 200),
        expected: allow ? allow.why : null,
      });
    }
  });

  try {
    const resp = await page.goto(`${BASE}${route}`, {
      waitUntil: "networkidle",
      timeout: 45000,
    });
    own.status = resp?.status() ?? null;
    own.finalUrl = page.url();
    own.authBounce = /\/login/.test(own.finalUrl) && !/\/login/.test(route);

    const body = await page.locator("body").innerText().catch(() => "");
    own.bodyText = body.trim().length;
    // "Empty" = a rendered shell with almost nothing in it, no error text, and
    // a live session — exactly how a swallowed fetch failure reads on screen.
    const hasErrorSurface = /خطا|error|مشکلی|دوباره|بازخوانی/i.test(body);
    own.emptyish = own.bodyText < 120 && !hasErrorSurface && !own.authBounce;
  } catch (e) {
    own.pageErrors.push(`goto: ${String(e).slice(0, 200)}`);
  }

  // If the page was throttled, give the limiter a window and look ONE more
  // time. Still throttled after that → the page is reported as not assessed,
  // never as broken.
  if (own.rateLimited > 0 && own.apiErrors.length === 0) {
    await new Promise((r) => setTimeout(r, 5000));
    own.rateLimited = 0;
    own.pageErrors.length = 0;
    own.consoleErrors.length = 0;
    try {
      await page.reload({ waitUntil: "networkidle", timeout: 45000 });
      const body = await page.locator("body").innerText().catch(() => "");
      own.bodyText = body.trim().length;
    } catch (e) {
      own.pageErrors.push(`reload: ${String(e).slice(0, 200)}`);
    }
  }

  if (screenshot) {
    mkdirSync(SHOTS, { recursive: true });
    const name = route.replace(/[/\\]/g, "_").replace(/^_/, "") || "root";
    await page
      .screenshot({ path: join(SHOTS, `${name}.png`), fullPage: false })
      .catch(() => {});
  }

  await page.close();
  return own;
}

function verdict(r) {
  const unexpectedApi = r.apiErrors.filter((e) => !e.expected);
  if (r.authBounce) return "AUTH-BOUNCE";
  if (r.pageErrors.length) return "RENDER-EXCEPTION";
  if (unexpectedApi.length) return "API-ERROR";
  if (r.rateLimited > 0) return "RATE-LIMITED"; // the sweep's own load; not a verdict on the page
  if (r.consoleErrors.length) return "CONSOLE-ERROR";
  if (r.emptyish) return "EMPTY-RENDER?";
  return "ok";
}

const routes = QUICK ? QUICK_ROUTES : discoverAdminRoutes();
console.log(`UI sweep: ${routes.length} admin routes on ${BASE}`);
console.log(`  screenshots: ${QUICK ? "every visited page" : [...SCREENSHOT_PAGES].join(", ")}`);
console.log("");

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });

const cookieCount = await loginAndGetCookies(context);
console.log(`admin session: ${cookieCount} cookies installed after real login`);

for (const route of routes) {
  const shot = QUICK || SCREENSHOT_PAGES.has(route);
  // Space the visits: each page fires its own burst of API calls (auth/me,
  // notices, branding), and the API's rate limiter counts per client. Back to
  // back with no gap, page ~20 onward reads 429 on everything and the sweep
  // grades the limiter instead of the pages.
  await new Promise((r) => setTimeout(r, 1200));
  const r = await visit(context, route, { screenshot: shot });
  r.verdict = verdict(r);
  results.push(r);
  const extras = [];
  if (r.apiErrors.length) extras.push(`${r.apiErrors.length} api-error(s)`);
  if (r.consoleErrors.length) extras.push(`${r.consoleErrors.length} console`);
  if (r.pageErrors.length) extras.push(`${r.pageErrors.length} render`);
  console.log(
    `  ${r.verdict.padEnd(17)} ${route}` +
      (extras.length ? `  [${extras.join(", ")}]` : "") +
      (r.bodyText < 120 && r.verdict === "ok" ? `  (thin body: ${r.bodyText} chars)` : ""),
  );
}

await browser.close();

const byVerdict = {};
for (const r of results) byVerdict[r.verdict] = (byVerdict[r.verdict] ?? 0) + 1;
const bad = results.filter((r) => r.verdict !== "ok" && r.verdict !== "EMPTY-RENDER?");

mkdirSync(SHOTS, { recursive: true });
const reportPath = join(SHOTS, "ui-sweep-report.json");
writeFileSync(
  reportPath,
  JSON.stringify(
    {
      at: new Date().toISOString(),
      base: BASE,
      routes: results.length,
      byVerdict,
      findings: bad,
      all: results,
    },
    null,
    2,
  ),
);

console.log("");
console.log("summary:", byVerdict);
console.log(`report:   ${reportPath}`);
if (bad.length) {
  console.log("");
  console.log("FINDINGS:");
  for (const r of bad) {
    console.log(`  ${r.verdict}  ${r.route}`);
    for (const e of r.pageErrors.slice(0, 3)) console.log(`      render: ${e}`);
    for (const e of r.consoleErrors.slice(0, 3)) console.log(`      console: ${e}`);
    for (const e of r.apiErrors.filter((x) => !x.expected).slice(0, 3))
      console.log(`      api ${e.status}: ${e.url}`);
  }
}
process.exit(bad.length ? 1 : 0);
