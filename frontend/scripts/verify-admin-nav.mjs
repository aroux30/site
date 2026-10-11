/**
 * Live verification of the rebuilt admin sidebar (grouped, collapsible).
 * Moved into the repo by the monitor (2026-10-06) on the same pattern as
 * verify-ui-live.mjs / verify-editor-toolbar.mjs: a live-UI check that was
 * worth running once is worth keeping runnable. Run with the dev server up:
 *   node scripts/verify-admin-nav.mjs            (defaults to :3100)
 *   NAV_BASE=http://localhost:3000 node scripts/verify-admin-nav.mjs
 */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.env.NAV_BASE ?? "http://localhost:3100";
const API = "http://127.0.0.1:8000/api/v1";
const PHONE = "09120000000";
const PASSWORD = "Admin@123456";
// Anchored to this file (the verify-ui-live.mjs pattern), not to an absolute
// machine path — the script must run from a fresh checkout, not just here.
const HERE = fileURLToPath(new URL(".", import.meta.url));
const SHOTS = join(HERE, "artifacts", "admin-nav");
mkdirSync(SHOTS, { recursive: true });

const findings = [];
const ok = (msg) => console.log(`  PASS ${msg}`);
const bad = (msg) => {
  findings.push(msg);
  console.log(`  FAIL ${msg}`);
};

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

// Real login, cookies on both origins (same as verify-ui-live.mjs).
const res = await context.request.post(`${API}/auth/login`, {
  data: { phone: PHONE, password: PASSWORD },
  headers: { "Content-Type": "application/json" },
});
if (!res.ok()) throw new Error(`login failed: ${res.status()}`);
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
console.log(`admin session installed (${cookies.length} cookies)`);

const page = await context.newPage();
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(String(e)));

// ── 1. Dashboard: groups render, active group none, dashboard highlighted ──
console.log("\n[1] /admin/dashboard");
await page.goto(`${BASE}/admin/dashboard`, { waitUntil: "networkidle", timeout: 60000 });
// Fresh-state check: clear any persisted open-group from a previous run.
await page.evaluate(() => localStorage.removeItem("admin-nav-open-group"));
await page.reload({ waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(1500);

const groupButtons = page.locator('nav[aria-label="ناوبری اصلی پنل مدیریت"] button[aria-expanded]');
const groupCount = await groupButtons.count();
groupCount === 7
  ? ok(`7 collapsible groups rendered (got ${groupCount})`)
  : bad(`expected 7 groups, got ${groupCount}`);

const dashboardLink = page.locator('nav[aria-label="ناوبری اصلی پنل مدیریت"] a[href="/admin/dashboard"]').first();
(await dashboardLink.getAttribute("aria-current")) === "page"
  ? ok("dashboard link has aria-current=page")
  : bad("dashboard link missing aria-current=page");

// All groups should be collapsed on dashboard (no stored pref).
const expandedOnDash = await page.locator('nav[aria-label="ناوبری اصلی پنل مدیریت"] button[aria-expanded="true"]').count();
expandedOnDash === 0
  ? ok("all groups collapsed on dashboard (fresh)")
  : bad(`expected 0 expanded groups on dashboard, got ${expandedOnDash}`);

// Flat 44-link dump should be gone: sidebar links should be few when collapsed.
// The collapsed panels keep their links in the DOM (grid-rows animation +
// inert), and getBoundingClientRect reports their intrinsic size even when
// clipped by an ancestor's overflow-hidden. So measure against the collapsed
// panel: a link counts only if its rect intersects its panel's visible box.
const visibleLinks = await page.evaluate(() => {
  const nav = document.querySelector('nav[aria-label="ناوبری اصلی پنل مدیریت"]');
  if (!nav) return -1;
  return [...nav.querySelectorAll("a")].filter((a) => {
    // Walk up: if any ancestor has zero height, the link is clipped away.
    for (let n = a; n && n !== nav; n = n.parentElement) {
      if (n.getBoundingClientRect().height === 0) return false;
    }
    const r = a.getBoundingClientRect();
    return r.height > 0 && r.width > 0;
  }).length;
});
visibleLinks >= 1 && visibleLinks <= 3
  ? ok(`only ${visibleLinks} visible link(s) when collapsed (was 44 flat)`)
  : bad(`expected 1..3 visible links collapsed, got ${visibleLinks}`);

await page.screenshot({ path: join(SHOTS, "01-dashboard-collapsed.png") });

// ── 2. Expand a group manually ──
console.log("\n[2] expand گروه فروشگاه");
const storeBtn = page.locator('button[aria-controls="admin-nav-group-store"]');
await storeBtn.click();
await page.waitForTimeout(400);
const storeExpanded = await storeBtn.getAttribute("aria-expanded");
storeExpanded === "true" ? ok("store group expands on click") : bad(`store aria-expanded=${storeExpanded}`);

const productsVisible = await page.locator('a[href="/admin/products"]').first().isVisible();
productsVisible ? ok("محصولات visible after expand") : bad("محصولات not visible after expand");

// ── 3. One-at-a-time accordion ──
const systemBtn = page.locator('button[aria-controls="admin-nav-group-system"]');
await systemBtn.click();
await page.waitForTimeout(400);
const storeNow = await storeBtn.getAttribute("aria-expanded");
const systemNow = await systemBtn.getAttribute("aria-expanded");
storeNow === "false" && systemNow === "true"
  ? ok("one-group-at-a-time: opening سیستم closed فروشگاه")
  : bad(`accordion wrong: store=${storeNow} system=${systemNow}`);

await page.screenshot({ path: join(SHOTS, "02-system-expanded.png") });

// ── 4. Navigate to /admin/products: فروشگاه auto-opens, محصولات highlighted ──
console.log("\n[4] navigate to /admin/products");
await page.goto(`${BASE}/admin/products`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(1500);
const storeAuto = await page.locator('button[aria-controls="admin-nav-group-store"]').getAttribute("aria-expanded");
storeAuto === "true" ? ok("فروشگاه auto-expands on /admin/products") : bad(`store aria-expanded=${storeAuto} on products page`);

const productsCurrent = await page.locator('a[href="/admin/products"]').first().getAttribute("aria-current");
productsCurrent === "page" ? ok("محصولات highlighted (aria-current=page)") : bad(`products aria-current=${productsCurrent}`);

await page.screenshot({ path: join(SHOTS, "03-products-active-group.png") });

// ── 5. data-exchange parent/child: exactly one highlighted ──
console.log("\n[5] /admin/data-exchange/export parent/child");
await page.goto(`${BASE}/admin/data-exchange/export`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(1500);
const parentCurrent = await page.locator('a[href="/admin/data-exchange"]').first().getAttribute("aria-current");
const childCurrent = await page.locator('a[href="/admin/data-exchange/export"]').first().getAttribute("aria-current");
parentCurrent === null && childCurrent === "page"
  ? ok("only child (خروجی داده) highlighted; parent not")
  : bad(`parent aria-current=${parentCurrent}, child aria-current=${childCurrent}`);

// Contrast of active child
const contrast = await page.evaluate(() => {
  const el = document.querySelector('a[href="/admin/data-exchange/export"][aria-current="page"]');
  if (!el) return null;
  const cs = getComputedStyle(el);
  const parse = (c) => c.match(/[\d.]+/g)?.map(Number) ?? null;
  const fg = parse(cs.color);
  const bgLayer = parse(cs.backgroundColor);
  if (!fg || !bgLayer) return null;
  // Composite the translucent active tint over the sidebar's opaque card
  // background, walking ancestors until an opaque bg is found.
  let base = null;
  for (let n = el.parentElement; n; n = n.parentElement) {
    const c = parse(getComputedStyle(n).backgroundColor);
    if (c && (c[3] === undefined || c[3] >= 0.99)) {
      base = c.slice(0, 3);
      break;
    }
  }
  base ??= [255, 255, 255];
  const alpha = bgLayer[3] ?? 1;
  const bg = [0, 1, 2].map((i) => bgLayer[i] * alpha + base[i] * (1 - alpha));
  const lum = ([r, g, b]) => {
    const a = [r, g, b].map((v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
  };
  const l1 = lum(fg.slice(0, 3));
  const l2 = lum(bg);
  const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  return {
    fg: cs.color,
    compositedBg: `rgb(${bg.map(Math.round).join(", ")})`,
    ratio: Math.round(ratio * 100) / 100,
  };
});
contrast
  ? ok(`active item contrast ${contrast.ratio}:1 (${contrast.fg} on ${contrast.compositedBg})`)
  : bad("could not read active item contrast");

await page.screenshot({ path: join(SHOTS, "04-data-exchange-child-active.png") });

// ── 6. Persistence: reload keeps the manually opened group ──
console.log("\n[6] persistence across reload");
await page.goto(`${BASE}/admin/dashboard`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(1200);
const analyticsBtn = page.locator('button[aria-controls="admin-nav-group-analytics"]');
await analyticsBtn.click();
await page.waitForTimeout(300);
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const analyticsAfter = await page.locator('button[aria-controls="admin-nav-group-analytics"]').getAttribute("aria-expanded");
analyticsAfter === "true"
  ? ok("manually opened group (گزارشها) stays open after reload")
  : bad(`persistence lost: analytics aria-expanded=${analyticsAfter} after reload`);

// ── 7. Mobile drawer ──
console.log("\n[7] mobile drawer");
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${BASE}/admin/dashboard`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(1500);

const sidebarVisible = await page.locator("aside").isVisible().catch(() => false);
!sidebarVisible ? ok("desktop sidebar hidden on mobile") : bad("desktop sidebar visible on mobile");

const oldStrip = await page.locator('nav.flex.gap-1.overflow-x-auto').count();
oldStrip === 0 ? ok("old horizontal 44-link strip is gone") : bad("old horizontal strip still present");

const menuBtn = page.locator('button[aria-label="باز کردن منوی مدیریت"]');
(await menuBtn.count()) === 1 ? ok("mobile menu button present") : bad("mobile menu button missing");

await menuBtn.click();
await page.waitForTimeout(600);
const drawerNav = page.locator('[role="dialog"] nav[aria-label="ناوبری اصلی پنل مدیریت"]');
(await drawerNav.isVisible()) ? ok("drawer opens with grouped nav") : bad("drawer did not open");

await page.screenshot({ path: join(SHOTS, "05-mobile-drawer.png") });

// Click a group then a link; drawer must close on navigation.
const drawerStoreBtn = page.locator('[role="dialog"] button[aria-controls="admin-nav-group-store"]');
await drawerStoreBtn.click();
await page.waitForTimeout(400);
await page.locator('[role="dialog"] a[href="/admin/products"]').first().click();
await page.waitForTimeout(2500);
const drawerGone = (await page.locator('[role="dialog"] nav[aria-label="ناوبری اصلی پنل مدیریت"]').count()) === 0;
drawerGone ? ok("drawer closes after navigating") : bad("drawer stayed open after navigation");
/\/admin\/products/.test(page.url()) ? ok(`navigated to ${page.url()}`) : bad(`unexpected url ${page.url()}`);

// ── 8. Page errors ──
console.log("\n[8] console/page errors");
pageErrors.length === 0 ? ok("no page errors") : bad(`page errors: ${pageErrors.join(" | ")}`);

console.log(`\n==== ${findings.length === 0 ? "ALL CHECKS PASSED" : `${findings.length} FINDINGS`} ====`);
for (const f of findings) console.log(` - ${f}`);
await browser.close();
process.exit(findings.length ? 1 : 0);
