#!/usr/bin/env node
/**
 * E2E for the ADMIN PANEL TOGGLES — driven by real clicks, not API calls.
 *
 * The earlier verification flipped the switches with `page.evaluate(fetch(...))`.
 * That proved the endpoint works and the storefront honours it, but it never
 * touched the thing the owner actually uses: the checkbox in
 * Admin → Settings → قابلیت‌های فروشگاه. The owner reports that clicking it
 * there does nothing, and this harness would not have caught it.
 *
 * So this clicks the real control and watches what happens:
 *   - the checkbox toggles,
 *   - the value PERSISTS across a full page reload (the admin form has its own
 *     save button and an optimistic local update — a toggle that only changes
 *     React state would look right here and vanish on refresh),
 *   - the storefront then hides the feature,
 *   - and it all comes back when re-enabled.
 *
 * A screenshot is taken at every step so the result can be seen, not just
 * asserted.
 *
 * Usage: node .claude/verify-admin-toggle-click.cjs
 */
const { chromium } = require("../frontend/node_modules/playwright");
const fs = require("fs");

const BASE = process.env.PREVIEW_BASE || "http://127.0.0.1:3500";
const PHONE = process.env.VERIFY_PHONE || "09129998877";
const PASSWORD = "VerifyWallet1234!";

const SHOTS = ".claude/shots";
const ADMIN_URL = `${BASE}/admin/settings`;
const FEATURES_TAB = "قابلیت‌های فروشگاه";

/** The row label -> the storefront link it should remove. */
const FEATURES = {
  "علاقه‌مندی‌ها": { key: "wishlist_enabled", href: "/account/favorites" },
  "مقایسه کالاها": { key: "compare_enabled", href: "/compare" },
};

const failures = [];
const notes = [];

function note(msg) {
  notes.push(msg);
  console.log(`  ${msg}`);
}

function fail(msg) {
  failures.push(msg);
  console.log(`  FAIL: ${msg}`);
}

async function shot(page, name) {
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false });
}

/**
 * Pause between steps.
 *
 * RATE_LIMIT_GLOBAL is 200/minute applied to EVERY route, and a Playwright run
 * that navigates, reloads and asserts on both pages easily crosses that — the
 * first version of this harness got a burst of 429s and reported the toggle as
 * "inert", which was the HARNESS hitting a ceiling, not the product failing.
 * A real operator clicks twice; this waits between the handful of requests a
 * step actually makes so the budget is not the thing under test.
 */
const STEP_PAUSE_MS = 1200;

async function settle(page) {
  await page.waitForTimeout(STEP_PAUSE_MS);
}

/** Reload the admin page and re-open the features tab. */
async function backToTab(page) {
  await page.goto(ADMIN_URL, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);
  await page.locator(`button[role="tab"]:has-text("${FEATURES_TAB}")`).first().click();
  await settle(page);
}

/** Log in (if not already) and land on the features tab of admin settings. */
async function openAdminFeaturesTab(page) {
  // The context persists across a run, but a previous run may have left a
  // session — in which case /login redirects away and there is no form to fill.
  // Go straight to the admin page and only fall back to the login form if the
  // tab never appears.
  await page.goto(ADMIN_URL, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3500);

  let tab = page.locator(`button[role="tab"]:has-text("${FEATURES_TAB}")`).first();
  if ((await tab.count()) === 0) {
    await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    const phone = page.locator('input[name="phone"], input[type="tel"], #phone').first();
    await phone.waitFor({ state: "visible", timeout: 20000 });
    await phone.fill(PHONE);
    await page.locator('input[type="password"]').first().fill(PASSWORD);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(4500);

    await page.goto(ADMIN_URL, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(3500);
    tab = page.locator(`button[role="tab"]:has-text("${FEATURES_TAB}")`).first();
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

  await tab.waitFor({ state: "visible", timeout: 20000 });
  await tab.click();
  await page.waitForTimeout(2500);
}

/**
 * The checkbox belonging to a row, found by the row's own label text.
 *
 * Scoping to the row matters: the page has several checkboxes and clicking the
 * wrong one would still "toggle" something, which is exactly the kind of
 * false PASS this harness exists to avoid.
 *
 * The locator is an XPath from the label ELEMENT up to its nearest rounded row
 * and then down to that row's checkbox. A CSS `div.rounded-lg:has-text(...)`
 * would also match any ANCESTOR that happens to contain the label — and with
 * two rows on the page the shared parent matches both strings, so `.first()`
 * could resolve to the wrong row's checkbox. Walking up from the exact label
 * to the NEAREST row cannot do that.
 */
function rowCheckbox(page, label) {
  return page.locator(
    `xpath=//div[contains(@class,"font-medium") and normalize-space(.)="${label}"]` +
      `/ancestor::div[contains(@class,"rounded-lg")][1]//input[@type="checkbox"]`,
  );
}

/** What the admin API reports — read straight from the DB-backed endpoint. */
async function serverState(page) {
  return page.evaluate(async () => {
    const res = await fetch("/api/v1/shop-features", { credentials: "include" });
    return res.json();
  });
}

/** Is the storefront link present in the rendered header? */
async function storefrontHasLink(page, href) {
  await page.goto(`${BASE}/products`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  const html = await page.evaluate(() => document.body.innerHTML);
  return html.includes(`href="${href}"`);
}

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ locale: "fa-IR" });
  const page = await ctx.newPage();

  // Surface any failed network call loudly — a toggle that 403s would still
  // leave the checkbox looking toggled.
  const failedRequests = [];
  page.on("response", (r) => {
    if (r.url().includes("shop-features") && r.status() >= 400) {
      failedRequests.push(`${r.request().method()} ${r.url()} -> ${r.status()}`);
    }
  });

  try {
    await openAdminFeaturesTab(page);
    // Normalise to "everything on" before asserting anything. A previous failed
    // run can leave a switch off, and starting from that state would make the
    // control below report "not ON at the start" instead of testing the click.
    for (const { key } of Object.values(FEATURES)) {
      await page.evaluate(
        ([k]) =>
          fetch(`/api/v1/admin/shop-features/${k}?enabled=true`, {
            method: "PUT",
            credentials: "include",
          }),
        [key],
      );
    }
    await page.waitForTimeout(1500);
    await openAdminFeaturesTab(page);
    await shot(page, "admin-features-tab-initial");

    for (const [label, { key, href }] of Object.entries(FEATURES)) {
      console.log(`\n${label}:`);

      // --- control: both switches start ON and the link is present ---
      const box = rowCheckbox(page, label);
      const boxCount = await box.count();
      if (boxCount === 0) {
        fail(`${label}: no checkbox found on the ${FEATURES_TAB} tab`);
        continue;
      }
      if (boxCount > 1) {
        // Two matches means the locator is not scoped to a single row, so
        // "which control did I click" is undefined. Refuse rather than pick one.
        fail(`${label}: the row locator matched ${boxCount} checkboxes, not 1`);
        continue;
      }
      const initial = await box.isChecked();
      if (!initial) {
        fail(`${label}: checkbox is not ON at the start — cannot test the off path`);
        continue;
      }
      if (!(await storefrontHasLink(page, href))) {
        fail(
          `CONTROL FAILED: with the switch on, the storefront has no ${href} link, ` +
            `so an "off" result below would prove nothing`,
        );
        continue;
      }
      note(`control: checkbox ON and ${href} present in the storefront`);

      // --- the real thing: CLICK the checkbox ---
      await backToTab(page);

      const target = rowCheckbox(page, label);
      await target.scrollIntoViewIfNeeded();
      await target.click();
      await settle(page);
      await shot(page, `admin-${key}-after-click`);

      const afterClick = await target.isChecked();
      if (afterClick) {
        fail(`${label}: clicking the checkbox left it ON — the control is inert`);
        continue;
      }
      note(`clicked: checkbox is now OFF`);

      // --- persistence across a reload (the real test of "it worked") ---
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.waitForTimeout(3000);
      await page.locator(`button[role="tab"]:has-text("${FEATURES_TAB}")`).first().click();
      await settle(page);
      const afterReload = await rowCheckbox(page, label).isChecked();
      if (afterReload) {
        fail(
          `${label}: the checkbox went back to ON after a reload — the click ` +
            `never reached the server, it only changed local state`,
        );
        // Put it back before continuing.
        await page.evaluate(
          ([k]) =>
            fetch(`/api/v1/admin/shop-features/${k}?enabled=true`, {
              method: "PUT",
              credentials: "include",
            }),
          [key],
        );
        continue;
      }
      note(`persisted: still OFF after a full reload`);
      await shot(page, `admin-${key}-after-reload`);

      // --- the server agrees, and the storefront hides it ---
      await settle(page);
      const state = await serverState(page);
      if (state[key] !== false) {
        fail(`${label}: server still reports ${key}=${JSON.stringify(state[key])}`);
      } else {
        note(`server reports ${key}=false`);
      }
      if (await storefrontHasLink(page, href)) {
        fail(`${label}: the storefront still shows ${href} with the switch off`);
      } else {
        note(`storefront: ${href} is gone`);
      }
      await shot(page, `storefront-${key}-off`);

      // --- restore by clicking again, not by API ---
      await backToTab(page);
      await rowCheckbox(page, label).click();
      await settle(page);
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.waitForTimeout(3000);
      await page.locator(`button[role="tab"]:has-text("${FEATURES_TAB}")`).first().click();
      await settle(page);
      const restored = await rowCheckbox(page, label).isChecked();
      if (!restored) {
        fail(`${label}: re-clicking did not turn it back ON`);
        // Force it back so the store is left in a sane state.
        await page.evaluate(
          ([k]) =>
            fetch(`/api/v1/admin/shop-features/${k}?enabled=true`, {
              method: "PUT",
              credentials: "include",
            }),
          [key],
        );
      } else {
        note(`restored by clicking again: checkbox is ON after reload`);
      }
    }

    if (failedRequests.length) {
      fail(`shop-features requests failed: ${failedRequests.join("; ")}`);
    }
  } catch (e) {
    fail(`harness error: ${e.message}`);
  } finally {
    // Leave every switch on regardless of how the run ended.
    try {
      for (const { key } of Object.values(FEATURES)) {
        await page.evaluate(
          ([k]) =>
            fetch(`/api/v1/admin/shop-features/${k}?enabled=true`, {
              method: "PUT",
              credentials: "include",
            }),
          [key],
        );
      }
    } catch {
      /* the page may already be closed */
    }
    await browser.close();
  }

  console.log("");
  if (failures.length) {
    console.log(`FAIL: ${failures.length} problem(s):`);
    failures.forEach((f) => console.log("  -", f));
    process.exit(1);
  }
  console.log("PASS: clicking the panel checkbox really toggles, persists and hides the feature.");
}

main();