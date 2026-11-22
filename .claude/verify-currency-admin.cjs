#!/usr/bin/env node
/**
 * Admin USD→Toman updater page, in a real browser with a real admin login.
 *
 * Why a browser check on top of the unit tests: the panel is a client
 * component with tabs and switches; an API test cannot see a broken tab
 * switch or a switch that renders but never fires (the project has hit
 * "presence is not wiring" before). This drives the REAL page:
 *
 *   1. logs in as the real admin and opens /admin/currency,
 *   2. asserts the status card and both tabs render,
 *   3. toggles the master switch OFF then ON via the real switch control,
 *      reloading to prove the value persisted server-side each time,
 *   4. opens the history tab and asserts the table/filters render,
 *   5. restores the master switch to ON,
 *   6. fails on any uncaught page error.
 *
 * Run: node .claude/verify-currency-admin.cjs
 * Env: PREVIEW_BASE (default http://127.0.0.1:3200)
 */
const { chromium } = require("../frontend/node_modules/playwright");

const BASE = process.env.PREVIEW_BASE || "http://127.0.0.1:3200";
const PHONE = process.env.VERIFY_PHONE || "09120000000";
const PASSWORD = process.env.VERIFY_PASSWORD || "Admin@123456";

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);
  await page.locator('input[name="phone"], input[type="tel"], #phone').first().fill(PHONE);
  await page.locator('input[type="password"]').first().fill(PASSWORD);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(4500);
  const authed = await page.evaluate(() => {
    try {
      return Boolean(JSON.parse(localStorage.getItem("auth-storage") || "{}")?.state?.isAuthenticated);
    } catch {
      return false;
    }
  });
  return authed;
}

/** Read the master switch state as ARIA (works for any switch implementation). */
async function masterSwitchState(page) {
  const el = page.locator('[aria-label="فعال/غیرفعال کردن به‌روزرسانی خودکار قیمت"]').first();
  return await el.getAttribute("aria-checked");
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));
  page.on("console", (m) => {
    if (m.type() === "error") pageErrors.push(m.text());
  });

  try {
    const authed = await login(page);
    check("real admin login", authed);
    if (!authed) throw new Error("cannot continue without a real login");

    await page.goto(`${BASE}/admin/currency`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(5000);

    // 1. Page shell + status card render.
    const bodyText = await page.evaluate(() => document.body.innerText);
    check("page heading renders", bodyText.includes("به‌روزرسانی خودکار قیمت دلاری"));
    check("status card renders", bodyText.includes("وضعیت فعلی"));
    check("managed-variant counter renders", bodyText.includes("کالاهای دلاری"));
    check("tabs render", bodyText.includes("تنظیمات") && bodyText.includes("تاریخچهٔ اجراها"));
    check("update-now button renders", bodyText.includes("به‌روزرسانی قیمت‌ها الآن"));

    // 2. The master switch exists and is wired — toggle it and see the
    //    server accept the change (reload proves persistence, not just state).
    const before = await masterSwitchState(page);
    check("master switch renders with aria-checked", before === "true" || before === "false", before);

    await page.locator('[aria-label="فعال/غیرفعال کردن به‌روزرسانی خودکار قیمت"]').first().click();
    await page.waitForTimeout(800);
    await page.locator('button:has-text("ذخیرهٔ تنظیمات")').first().click();
    await page.waitForTimeout(2500);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);
    const afterToggle = await masterSwitchState(page);
    check(
      "switch persisted the toggle to the server",
      afterToggle !== before,
      `${before} -> ${afterToggle}`,
    );

    // Restore: toggle back + save.
    await page.locator('[aria-label="فعال/غیرفعال کردن به‌روزرسانی خودکار قیمت"]').first().click();
    await page.waitForTimeout(800);
    await page.locator('button:has-text("ذخیرهٔ تنظیمات")').first().click();
    await page.waitForTimeout(2500);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);
    const restored = await masterSwitchState(page);
    check("switch restored to original", restored === before, `${restored}`);

    // 3. History tab renders with its filter set.
    await page.locator('[role="tab"]:has-text("تاریخچهٔ اجراها")').first().click();
    await page.waitForTimeout(2500);
    const historyText = await page.evaluate(() => document.body.innerText);
    check("history tab renders kind filter", historyText.includes("وضعیت اجرا"));
    check("history tab renders search box", historyText.includes("جستجو (کد SKU، نام محصول)"));
    check("history tab renders export button", historyText.includes("خروجی CSV"));

    // 4. No uncaught page errors along the way.
    check("no uncaught page errors", pageErrors.length === 0, pageErrors.slice(0, 2).join(" | "));
  } catch (err) {
    check("run completed", false, String(err).slice(0, 200));
  } finally {
    await browser.close();
  }

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
})();
