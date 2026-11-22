#!/usr/bin/env node
/**
 * Granular switches: with the MASTER switch on, turning off one capability must
 * hide exactly that capability's button and leave the others.
 *
 * The master-switch verification covers "off hides everything"; this covers
 * "off for one hides only that one" — the failure mode where a per-capability
 * guard is dropped and every button comes back.
 *
 * Same discipline as verify-wallet-hidden.cjs: each state is asserted against
 * the expected visibility, and every switch is restored at the end.
 */
const { chromium } = require("../frontend/node_modules/playwright");

const BASE = process.env.PREVIEW_BASE || "http://127.0.0.1:3500";
const PHONE = process.env.VERIFY_PHONE || "09129998877";
const PASSWORD = "VerifyWallet1234!";

/** capability -> the button label that must disappear when it is off.

    These must match the labels the wallet tab actually renders. A wrong label
    is not a small typo here: the control below would report the button missing
    while the switch was ON, which reads like a broken guard rather than a
    broken harness.
*/
const CAPABILITIES = {
  wallet_deposit_enabled: "افزایش موجودی (شارژ)",
  wallet_transfer_enabled: "انتقال به کاربر",
  wallet_withdraw_enabled: "درخواست برداشت",
};

async function setSwitch(page, key, value) {
  const result = await page.evaluate(
    async ([k, v]) => {
      const res = await fetch(`/api/v1/admin/wallet/settings/${k}?enabled=${v}`, {
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

/** Open the wallet tab and report which capability buttons are on screen. */
async function walletButtons(page) {
  await page.goto(`${BASE}/account`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  const nav = page.locator('nav button', { hasText: "کیف پول" }).first();
  if ((await nav.count()) === 0) return null; // wallet tab not offered at all
  await nav.click();
  await page.waitForTimeout(3000);
  const text = await page.evaluate(() => document.body.innerText);
  const present = {};
  for (const [key, label] of Object.entries(CAPABILITIES)) present[key] = text.includes(label);
  return present;
}

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ locale: "fa-IR" });
  const page = await ctx.newPage();
  const failures = [];

  try {
    await login(page);
    await setSwitch(page, "wallet_enabled", true);

    // Control: everything on, so every button must be present.
    for (const key of Object.keys(CAPABILITIES)) await setSwitch(page, key, true);
    const all = await walletButtons(page);
    if (!all) throw new Error("wallet tab not offered with every switch on");
    for (const [key, seen] of Object.entries(all)) {
      if (!seen) failures.push(`control: ${key} on but its button is missing`);
    }
    if (!failures.length) console.log(`CONTROL OK: all ${Object.keys(all).length} buttons present with every switch on.`);

    // Each capability alone: off hides exactly its own button.
    for (const key of Object.keys(CAPABILITIES)) {
      await setSwitch(page, key, false);
      const state = await walletButtons(page);
      if (!state) {
        failures.push(`${key}: wallet tab vanished — a per-capability switch must not hide the module`);
        await setSwitch(page, key, true);
        continue;
      }
      if (state[key]) failures.push(`${key}: its button is still on screen while the capability is off`);
      for (const other of Object.keys(CAPABILITIES)) {
        if (other !== key && !state[other]) {
          failures.push(`${key}: off also hid ${other}'s button — the guards are not independent`);
        }
      }
      await setSwitch(page, key, true);
    }

    await page.screenshot({ path: ".claude/shots/wallet-granular-restored.png" });
  } catch (e) {
    failures.push(`harness error: ${e.message}`);
  } finally {
    // Restore every switch regardless of how the run ended.
    try {
      await setSwitch(page, "wallet_enabled", true);
      for (const key of Object.keys(CAPABILITIES)) await setSwitch(page, key, true);
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
  console.log("PASS: each capability switch hides exactly its own button; controls all saw them present.");
}

main();