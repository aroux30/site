#!/usr/bin/env node
/**
 * Browser proof that disabling wishlist / compare HIDES them, and that turning
 * one off does not hide the other.
 *
 * Same discipline as verify-wallet-hidden.cjs: every absence assertion is
 * preceded by a positive control that proves the detector can see the feature
 * at all. A first version of the wallet check reported PASS while the login had
 * 401'd — nothing had been rendered, so "nothing found" was trivially true.
 *
 * Usage: node .claude/verify-shop-features-hidden.cjs
 */
const { chromium } = require("../frontend/node_modules/playwright");

const BASE = process.env.PREVIEW_BASE || "http://127.0.0.1:3500";
const PHONE = process.env.VERIFY_PHONE || "09129998877";
const PASSWORD = "VerifyWallet1234!";

/** Switch key -> the header label that must disappear when it is off. */
const FEATURES = {
  wishlist_enabled: "علاقه‌مندی‌ها",
  compare_enabled: "مقایسه کالاها",
};

async function setSwitch(page, key, value) {
  const result = await page.evaluate(
    async ([k, v]) => {
      const res = await fetch(`/api/v1/admin/shop-features/${k}?enabled=${v}`, {
        method: "PUT",
        credentials: "include",
      });
      return { status: res.status, body: await res.text() };
    },
    [key, value],
  );
  if (result.status >= 400) {
    throw new Error(`switch ${key}=${value} failed: ${result.status} ${result.body}`);
  }
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await page.locator('input[name="phone"], input[type="tel"], #phone').first().fill(PHONE);
  await page.locator('input[type="password"]').first().fill(PASSWORD);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(4500);
  const ok = await page.evaluate(() => {
    const raw = localStorage.getItem("auth-storage");
    if (!raw) return false;
    try {
      return Boolean(JSON.parse(raw)?.state?.isAuthenticated);
    } catch {
      return false;
    }
  });
  if (!ok) throw new Error("login failed — the run would be vacuous");
}

/** The header link for each feature, as actually rendered. */
async function headerLinks(page) {
  await page.goto(`${BASE}/products`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4500);
  const html = await page.evaluate(() => document.body.innerHTML);
  return {
    wishlist: html.includes('href="/account/favorites"'),
    compare: html.includes('href="/compare"'),
  };
}

/** Has the deep link been redirected away from the feature's own page? */
async function deepLinkRedirected(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  return !new URL(page.url()).pathname.startsWith(path);
}

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ locale: "fa-IR" });
  const page = await ctx.newPage();
  const failures = [];

  try {
    await login(page);
    for (const key of Object.keys(FEATURES)) await setSwitch(page, key, true);

    // Control: both features on, both links present.
    const on = await headerLinks(page);
    for (const [key, label] of Object.entries(FEATURES)) {
      const short = key.split("_")[0];
      if (!on[short]) {
        throw new Error(
          `CONTROL FAILED: ${label} link absent with every switch on — the ` +
            `detector cannot see it, so an OFF result would prove nothing`,
        );
      }
    }
    console.log("CONTROL OK: both feature links present with every switch on.");

    // Each feature alone: off removes its link and redirects its page, and
    // leaves the other feature untouched.
    for (const key of Object.keys(FEATURES)) {
      const short = key.split("_")[0];
      const other = short === "wishlist" ? "compare" : "wishlist";
      await setSwitch(page, key, false);
      // Reload so the header re-reads the switch state (it is fetched per load).
      const state = await headerLinks(page);
      if (state[short]) {
        failures.push(`${key}: its header link is still on screen while off`);
      }
      if (!state[other]) {
        failures.push(
          `${key}: off also hid ${other}'s link — the switches are not independent`,
        );
      }
      const page_ = short === "wishlist" ? "/favorites" : "/compare";
      if (!(await deepLinkRedirected(page, page_))) {
        failures.push(`${key}: ${page_} still rendered with the module off`);
      }
      await setSwitch(page, key, true);
    }

    await page.screenshot({ path: ".claude/shots/shop-features-restored.png" });
  } catch (e) {
    failures.push(`harness error: ${e.message}`);
  } finally {
    try {
      for (const key of Object.keys(FEATURES)) await setSwitch(page, key, true);
    } catch {
      /* the page may already be closed */
    }
    await browser.close();
  }

  if (failures.length) {
    console.log(`FAIL: ${failures.length} problem(s):`);
    failures.forEach((f) => console.log("  -", f));
    process.exit(1);
  }
  console.log("PASS: control saw both features; with each off its link and page disappear, the other untouched.");
}

main();