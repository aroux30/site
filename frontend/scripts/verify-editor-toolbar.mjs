/**
 * Browser test for the content editor's toolbar.
 *
 * Written as a plain Playwright script rather than a spec file: the project's
 * test suites were removed on request, and this is a one-off verification of a
 * specific change, not a suite to keep running. It mounts the real
 * RichBodyEditor and drives the real toolbar buttons, so a button that exists
 * but does nothing fails here.
 *
 *   node scripts/verify-editor-toolbar.mjs
 *
 * Requires the frontend dev server on :3000 and this probe page:
 *   frontend/app/editor-probe/page.tsx
 */
import { chromium } from "@playwright/test";
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

// The probe lives under /admin so the staff guard in middleware.ts covers it —
// at its original /editor-probe path the middleware passes the route straight
// through, which is why it moved. That guard means the browser test now has to
// carry a real session, so it logs in the way a person does rather than
// forging a token: a forged one would keep working after the signing scheme
// changed and would keep passing while the real gate was untested.
const BASE = process.env.PROBE_BASE ?? "http://localhost:3000";
const URL = process.env.PROBE_URL ?? `${BASE}/admin/editor-probe`;
const API = process.env.PROBE_API ?? "http://127.0.0.1:8000/api/v1";
const PHONE = process.env.PROBE_ADMIN_PHONE ?? process.env.ADMIN_PHONE;
const PASSWORD = process.env.PROBE_ADMIN_PASSWORD ?? process.env.ADMIN_PASSWORD;
const SHOTS = join(process.cwd(), "scripts", "artifacts");

const results = [];
const record = (name, pass, detail = "") => {
  results.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });

const consoleErrors = [];
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
page.on("pageerror", (e) => consoleErrors.push(String(e)));

if (!PHONE || !PASSWORD) {
  console.error(
    "Set PROBE_ADMIN_PHONE and PROBE_ADMIN_PASSWORD (an account with an admin " +
      "role). The probe is under /admin, so an unauthenticated request is " +
      "redirected to /login and every check below would fail for the wrong reason.",
  );
  process.exit(2);
}

const login = await page.request.post(`${API}/auth/login`, {
  data: { phone: PHONE, password: PASSWORD },
});
if (!login.ok()) {
  console.error(`admin login failed: ${login.status()} ${await login.text()}`);
  process.exit(2);
}
const authCookies = await login.headersArray();
for (const h of authCookies) {
  const m = /set-cookie:\s*([^=]+)=([^;]*)/i.exec(h.value);
  if (m) await page.context().addCookies([
    { name: m[1], value: m[2].trim(), domain: "localhost", path: "/" },
  ]);
}

await page.goto(URL, { waitUntil: "networkidle" });

const surface = page.locator('[role="textbox"][aria-label="متن نوشته"]');
await surface.waitFor({ state: "visible", timeout: 30000 });
record("editor surface mounts", true);

const html = () => surface.innerHTML();

/** Put a selection in the body the way an author does: click into it and type.
 *  A synthetic execCommand on an un-focused surface silently no-ops, which
 *  would make a working button look broken. */
async function selectAllBody() {
  await surface.click();
  await page.keyboard.press("Control+a");
}

/* ---- each toolbar button, clicked for real ---- */
const cases = [
  ["پررنگ (bold)", "پررنگ", "b"],
  ["کج (italic)", "کج", "i"],
  ["زیرخط (underline)", "زیرخط", "u"],
  ["خط‌خورده (strike)", "خط‌خورده", "s|strike"],
  ["نقل‌قول (blockquote)", "نقل‌قول", "blockquote"],
  ["کد (pre)", "کد", "pre"],
  ["جدول (table)", "جدول", "table"],
  ["خط جداکننده (hr)", "خط جداکننده", "hr"],
];

for (const [label, title, tag] of cases) {
  await page.goto(URL, { waitUntil: "networkidle" });
  await surface.waitFor({ state: "visible" });
  await selectAllBody();
  const before = await html();
  await page.locator(`button[title="${title}"]`).first().click();
  await page.waitForTimeout(200);
  const after = await html();
  record(
    `toolbar: ${label}`,
    after !== before && new RegExp(`<${tag}[\\s>]`).test(after),
    `added <${tag}>`,
  );
}

/* ---- alignment: justifFull is the one with no visual tag, so check the
       inline style the browser writes. ---- */
await page.goto(URL, { waitUntil: "networkidle" });
await surface.waitFor({ state: "visible" });
await selectAllBody();
await page.locator('button[title="وسط‌چین"]').first().click();
await page.waitForTimeout(200);
record("toolbar: تراز (center)", /text-align:\s*center/i.test(await html()), "text-align:center");

/* ---- word / character counter ---- */
await page.goto(URL, { waitUntil: "networkidle" });
await surface.waitFor({ state: "visible" });
const counter = page.locator("text=/واژه/").first();
await counter.waitFor({ timeout: 10000 });
const counterText = (await counter.textContent()) ?? "";
record(
  "word counter shows a number",
  /\d/.test(counterText.replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))) || /[۰-۹]/.test(counterText),
  counterText.trim().slice(0, 40),
);

/* ---- fullscreen toggle ---- */
await page.locator('button[title="تمام‌صفحه"]').first().click();
await page.waitForTimeout(300);
// The toggle swaps the toolbar button's own title, so its presence is the
// signal that state changed; then assert the wrapper actually went fixed.
const exitButton = await page.locator('button[title="خروج از تمام‌صفحه"]').count();
const overlay = page.locator("div.fixed.inset-0.z-50").first();
const overlayClass = (await overlay.count()) ? await overlay.getAttribute("class") : null;
record(
  "fullscreen applies a fixed overlay",
  exitButton === 1 && (overlayClass ?? "").includes("inset-0"),
  overlayClass ?? "(no overlay)",
);

await mkdirSync(SHOTS, { recursive: true });
await page.screenshot({ path: join(SHOTS, "editor-fullscreen.png"), fullPage: false });

await browser.close();

const failed = results.filter((r) => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
if (consoleErrors.length) {
  console.log("\nconsole errors:");
  for (const e of [...new Set(consoleErrors)].slice(0, 10)) console.log("  " + e);
}
writeFileSync(join(SHOTS, "editor-toolbar-results.json"), JSON.stringify({ results, consoleErrors }, null, 2));
process.exit(failed.length ? 1 : 0);
