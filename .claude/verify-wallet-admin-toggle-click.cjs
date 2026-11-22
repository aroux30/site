#!/usr/bin/env node
/**
 * The wallet module switches, clicked in the admin panel — the same physical
 * test the owner asked for on wishlist/compare, applied to the wallet's own
 * settings tab so the two cannot drift apart.
 *
 * Usage: node .claude/verify-wallet-admin-toggle-click.cjs
 */
const { chromium } = require("../frontend/node_modules/playwright");
const fs = require("fs");

const BASE = process.env.PREVIEW_BASE || "http://127.0.0.1:3500";
const PHONE = process.env.VERIFY_PHONE || "09129998877";
const PASSWORD = "VerifyWallet1234!";
const SHOTS = ".claude/shots";
const URL = `${BASE}/admin/wallet`;

const failures = [];
const note = (m) => console.log(`  ${m}`);
const fail = (m) => {
  failures.push(m);
  console.log(`  FAIL: ${m}`);
};

async function shot(page, name) {
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: `${SHOTS}/${name}.png` });
}

/** The settings tab, opened. */
async function openSettingsTab(page) {
  await page.goto(URL, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3500);
  let tab = page.locator('button:has-text("تنظیمات")').last();
  if ((await tab.count()) === 0) {
    await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    await page.locator('input[name="phone"], input[type="tel"], #phone').first().fill(PHONE);
    await page.locator('input[type="password"]').first().fill(PASSWORD);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(4500);
    await page.goto(URL, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(3500);
    tab = page.locator('button:has-text("تنظیمات")').last();
  }
  const authed = await page.evaluate(() => {
    const raw = localStorage.getItem("auth-storage");
    if (!raw) return false;
    try {
      return Boolean(JSON.parse(raw)?.state?.isAuthenticated);
    } catch {
      return false;
    }
  });
  if (!authed) throw new Error("login failed — the run would be vacuous");
  await tab.click();
  await page.waitForTimeout(2500);
}

/** A wallet switch row's toggle, found by its Persian label. */
function switchFor(page, label) {
  return page.locator(
    `xpath=//*[normalize-space(text())="${label}"]` +
      `/ancestor::div[contains(@class,"flex")][1]//button[@role="switch"]`,
  );
}

async function storefrontHidesWallet(page) {
  await page.goto(`${BASE}/account`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  const text = await page.evaluate(() => document.body.innerText);
  return !text.includes("موجودی کیف پول:");
}

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ locale: "fa-IR" });
  const page = await ctx.newPage();

  try {
    await openSettingsTab(page);
    await shot(page, "admin-wallet-settings-initial");

    const toggle = switchFor(page, "فعال بودن ماژول کیف پول");
    const count = await toggle.count();
    if (count === 0) {
      fail("the wallet master switch row was not found on the settings tab");
      throw new Error("selector missed");
    }
    if (count > 1) {
      fail(`the wallet master switch locator matched ${count} controls, not 1`);
      throw new Error("ambiguous selector");
    }

    // Control: it starts ON and the storefront shows the wallet.
    const startOn = (await toggle.getAttribute("aria-checked")) === "true";
    if (!startOn) {
      // Normalise via the API so the run is repeatable, then reload.
      await page.evaluate(() =>
        fetch("/api/v1/admin/wallet/settings/wallet_enabled?enabled=true", {
          method: "PUT",
          credentials: "include",
        }),
      );
      await page.waitForTimeout(1200);
      await openSettingsTab(page);
    }
    const on = (await switchFor(page, "فعال بودن ماژول کیف پول").getAttribute("aria-checked")) === "true";
    if (!on) {
      fail("control: the wallet switch is not ON at the start");
      throw new Error("bad start state");
    }
    if (await storefrontHidesWallet(page)) {
      fail("CONTROL FAILED: with the wallet ON the storefront shows no balance chip");
      throw new Error("blind detector");
    }
    note("control: switch ON and the storefront shows the wallet chip");

    // The real thing: click it off.
    await openSettingsTab(page);
    await switchFor(page, "فعال بودن ماژول کیف پول").click();
    await page.waitForTimeout(2500);
    await shot(page, "admin-wallet-switch-after-click");

    const offNow = (await switchFor(page, "فعال بودن ماژول کیف پول").getAttribute("aria-checked")) === "false";
    if (!offNow) {
      fail("clicking the wallet master switch left it ON — the control is inert");
    } else {
      note("clicked: switch is now OFF");
    }

    // Persistence across a reload.
    await openSettingsTab(page);
    const afterReload = (await switchFor(page, "فعال بودن ماژول کیف پول").getAttribute("aria-checked")) === "true";
    if (afterReload) {
      fail("the wallet switch reverted to ON after a reload — the click never persisted");
    } else {
      note("persisted: still OFF after a full reload");
    }

    // The storefront honours it.
    if (await storefrontHidesWallet(page)) {
      note("storefront: the wallet chip is gone");
    } else {
      fail("the storefront still shows the wallet chip with the module off");
    }
    await shot(page, "storefront-wallet-off");

    // Restore by clicking again.
    await openSettingsTab(page);
    await switchFor(page, "فعال بودن ماژول کیف پول").click();
    await page.waitForTimeout(2500);
    await openSettingsTab(page);
    const restored = (await switchFor(page, "فعال بودن ماژول کیف پول").getAttribute("aria-checked")) === "true";
    if (!restored) {
      fail("re-clicking did not turn the wallet back ON");
      await page.evaluate(() =>
        fetch("/api/v1/admin/wallet/settings/wallet_enabled?enabled=true", {
          method: "PUT",
          credentials: "include",
        }),
      );
    } else {
      note("restored by clicking again");
    }
  } catch (e) {
    if (!failures.length) fail(`harness error: ${e.message}`);
  } finally {
    try {
      await page.evaluate(() =>
        fetch("/api/v1/admin/wallet/settings/wallet_enabled?enabled=true", {
          method: "PUT",
          credentials: "include",
        }),
      );
    } catch {
      /* page may be closed */
    }
    await browser.close();
  }

  console.log("");
  if (failures.length) {
    console.log(`FAIL: ${failures.length} problem(s):`);
    failures.forEach((f) => console.log("  -", f));
    process.exit(1);
  }
  console.log("PASS: the wallet switch in the panel really toggles, persists and hides the wallet.");
}

main();