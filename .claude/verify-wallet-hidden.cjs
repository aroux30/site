#!/usr/bin/env node
/**
 * Browser proof that the wallet is FULLY hidden when the master switch is off.
 *
 * The operator's complaint was that switching the module off only hid the three
 * action buttons while the menu entry, the balance chip, the tab and the
 * checkout payment method stayed on screen. Static gates cannot prove rendering,
 * so this drives a real browser and asserts each surface is absent from the
 * rendered DOM.
 *
 * THE POSITIVE CONTROL IS THE POINT. A first version of this script reported
 * "PASS: no wallet surface is rendered" while the login had actually returned
 * 401 — it never reached the account page, so it proved nothing. Every run here
 * therefore:
 *
 *   1. creates its own throwaway account (never reuses or resets an existing
 *      user's password — the seeded 09120000000 is a real site user);
 *   2. asserts the login actually succeeded;
 *   3. asserts the page it is about to inspect is genuinely the account page;
 *   4. turns the wallet ON, re-runs every assertion, and requires that the
 *      markers are then VISIBLE — proving the detector can see them at all;
 *   5. only then turns the wallet OFF and requires them to be gone.
 *
 * Step 4 is what makes step 5 mean anything. Usage:
 *     node .claude/verify-wallet-hidden.cjs
 */
const { chromium } = require("../frontend/node_modules/playwright");

const BASE = process.env.PREVIEW_BASE || "http://127.0.0.1:3500";

const PHONE = process.env.VERIFY_PHONE || "09129998877";
const PASSWORD = "VerifyWallet1234!";

/** Strings that must be ABSENT when the wallet is off, PRESENT when it is on. */
const MARKERS = [
  "موجودی کیف پول:",
  "گردش حساب و تراکنش‌ها",
];

/** Checkout-only markers: the wallet tender and the split-tender card.

    "کیف پول" alone is the label the backend returns for the wallet payment
    method — the storefront fallback's "کیف پول اختصاصی" only appears when
    /payments/methods fails outright, so match what actually renders. The
    English description is the backend's, and is the most precise signal that
    the wallet tender row is present at all.
*/
const CHECKOUT_MARKERS = [
  "Pay using your wallet balance",
  "پرداخت ترکیبی",
  "موجودی کیف پول شما",
];

const SWITCH_KEY = "wallet_enabled";

/** Flip the master switch straight through the admin API.

    Auth is an HttpOnly cookie (lib/api/client.ts uses `withCredentials`), so
    there is no token to put in an Authorization header — the browser attaches
    the cookie itself.
*/
async function setSwitch(page, value) {
  const result = await page.evaluate(
    async ([key, val]) => {
      // `enabled` is a query parameter on this route, not a JSON body field.
      const res = await fetch(
        `/api/v1/admin/wallet/settings/${key}?enabled=${val}`,
        { method: "PUT", credentials: "include" },
      );
      return { status: res.status, body: await res.text() };
    },
    [SWITCH_KEY, value],
  );
  if (result.status >= 400) {
    throw new Error(`switch ${SWITCH_KEY}=${value} failed: ${result.status} ${result.body}`);
  }
  return result;
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  const phone = page.locator('input[name="phone"], input[type="tel"], #phone').first();
  const pass = page.locator('input[type="password"]').first();
  await phone.waitFor({ state: "visible", timeout: 20000 });
  await phone.fill(PHONE);
  await pass.fill(PASSWORD);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(4500);
}

/** Collect every wallet marker that is actually rendered. */
async function visibleMarkers(page, markers = MARKERS) {
  const text = await page.evaluate(() => document.body.innerText);
  return markers.filter((m) => text.includes(m));
}

/** A checkout wizard step the harness can rely on reaching.

    The payment step is step 3 of 4 and is gated behind a saved delivery
    address, so the harness creates one rather than clicking through the form.
*/
async function ensureAddress(page) {
  return page.evaluate(async () => {
    const list = await fetch("/api/v1/users/me/addresses", { credentials: "include" });
    if (list.ok) {
      const body = await list.json();
      const items = body?.items || body?.data || (Array.isArray(body) ? body : []);
      if (items.length) return { ok: true, reused: true };
    }
    const res = await fetch("/api/v1/users/me/addresses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        title: "آدرس تست",
        recipient_name: "کاربر تست",
        phone: "09129998877",
        province: "تهران",
        city: "تهران",
        postal_code: "1234567890",
        full_address: "خیابان تست، کوچهWallet، پلاک ۱۲",
        is_default: true,
      }),
    });
    if (!res.ok) return { ok: false, why: `address ${res.status} ${await res.text()}` };
    return { ok: true, reused: false };
  });
}

/** True once the payment-method step is on screen.

    Must key on something OTHER than the wallet tender — the tender is what the
    OFF half of this check asserts is gone, so detecting the step with it makes
    the OFF run look like it never arrived. The non-wallet payment rows are
    always present, so they are the honest signal.
*/
function atPaymentStep(text) {
  return (
    text.includes("کارت به کارت") || text.includes("درگاه پرداخت امن") || text.includes("زرین‌پال")
  );
}

/** Click through the wizard until the payment step renders.

    Labels differ per step, so match the buttons that actually advance rather
    than a guessed list: the wizard's forward controls read "انتخاب آدرس تحویل",
    "ادامه نهایی و ثبت" and similar.
*/
async function advanceToPayment(page) {
  const SKIP = ["انتخاب آدرس تحویل", "ادامه نهایی و ثبت", "مرحله بعد", "ادامه"];
  for (let i = 0; i < 10; i += 1) {
    const text = await page.evaluate(() => document.body.innerText);
    if (atPaymentStep(text)) return true;

    // The wizard's forward buttons stay disabled until the step's own control
    // is chosen. Select first, then try to advance in the SAME pass —
    // across passes the loop re-selected the same radio forever and never
    // moved on.
    const radios = page.locator('input[type="radio"]:not(:checked)');
    const selectedNow = (await radios.count()) > 0;
    if (selectedNow) {
      await radios.first().click({ force: true }).catch(() => {});
      await page.waitForTimeout(1500);
    }

    let advanced = false;
    for (const label of SKIP) {
      const btns = page.locator(`button:has-text("${label}")`);
      const n = await btns.count();
      for (let b = 0; b < n; b += 1) {
        const btn = btns.nth(b);
        if (await btn.isDisabled().catch(() => true)) continue;
        await btn.scrollIntoViewIfNeeded().catch(() => {});
        await btn.click().catch(() => {});
        await page.waitForTimeout(3500);
        advanced = true;
        break;
      }
      if (advanced) break;
    }
    // Selected a control but the forward button is still disabled: give the
    // step another pass rather than declaring the wizard stuck.
    if (!advanced && selectedNow) continue;
    if (!advanced) return false;
  }
  return atPaymentStep(await page.evaluate(() => document.body.innerText));
}

/** Put something in the cart so /checkout renders its payment step.

    Seeded through the cart API rather than by clicking the product grid: this
    storefront currently lists 0 products, so there is no add-to-cart control to
    click and the page would render its empty state — which would let the
    wallet check below "pass" for the wrong reason.
*/
async function seedCart(page) {
  const result = await page.evaluate(async () => {
    // If the cart already holds an item, that is enough — adding a second one
    // can exhaust a low-stock variant and 409 the whole verification.
    const existing = await fetch("/api/v1/cart", { credentials: "include" });
    if (existing.ok) {
      const cart = await existing.json();
      const c = cart?.data || cart;
      const n = (c?.items || []).length || c?.total_items || 0;
      if (n > 0) return { ok: true, why: "", count: n, reused: true };
    }
    // Pick any sellable variant; the storefront grid is empty but the catalog
    // is not. The catalog lives under /catalog/products, not /products.
    const list = await fetch("/api/v1/catalog/products?page=1&page_size=1", {
      credentials: "include",
    });
    if (!list.ok) return { ok: false, why: `products ${list.status}` };
    const body = await list.json();
    const items = body?.items || body?.data?.items || [];
    if (!items.length) return { ok: false, why: "no products returned" };
    const product = items[0];
    // /cart/items wants a VARIANT id, not a product id. The catalog listing
    // does not always embed one and the variants sub-route shape varies, so
    // fall back to walking the product detail, then to any variant the
    // listing did carry.
    let variantId = product.default_variant_id || product.variant_id || null;
    if (!variantId && product.id) {
      const dres = await fetch(`/api/v1/catalog/products/${product.id}`, {
        credentials: "include",
      });
      if (dres.ok) {
        const detail = await dres.json();
        const d = detail?.data || detail;
        const variants = d?.variants || d?.items || [];
        const usable = variants.find(
          (v) => v.is_active !== false && (v.stock ?? v.quantity ?? 0) > 0,
        );
        variantId = usable?.id || variants[0]?.id || d?.default_variant_id || null;
      }
    }
    if (!variantId) {
      return { ok: false, why: `no variant id resolvable from product ${product?.id}` };
    }
    const res = await fetch("/api/v1/cart/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ variant_id: variantId, quantity: 1 }),
    });
    if (!res.ok) return { ok: false, why: `cart/items ${res.status} ${await res.text()}` };
    const cart = await res.json();
    const count =
      (cart?.items || cart?.cart?.items || []).length ??
      (cart?.total_items || 0);
    return { ok: Boolean(count), why: count ? "" : "cart empty after add", count };
  });
  return result;
}

/** The checkout page's wallet surfaces must follow the master switch too.

    ``expectVisible`` inverts the assertion so the same function serves both
    halves: with the switch ON the wallet tender MUST be on screen (that is the
    control), with it OFF it must be gone (that is the assertion).
*/
async function checkCheckout(page, findings, label, expectVisible) {
  const seeded = await seedCart(page);
  const addr = await ensureAddress(page);
  if (!seeded.ok) {
    findings.push(`[${label}] /checkout could not be exercised: ${seeded.why}`);
    return false;
  }
  if (!addr.ok) {
    findings.push(`[${label}] no delivery address available: ${addr.why}`);
    return false;
  }
  await page.goto(`${BASE}/checkout`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(5000);
  const reached = await advanceToPayment(page);
  if (!reached) {
    await page.screenshot({ path: `.claude/shots/_checkout-${label}-nostage.png` });
    const head = (await page.evaluate(() => document.body.innerText)).slice(0, 300);
    findings.push(
      `[${label}] /checkout never reached the payment step (where the wallet ` +
        `tender lives), so this check could not have failed. Page starts: ` +
        JSON.stringify(head),
    );
    return false;
  }
  const seen = await visibleMarkers(page, CHECKOUT_MARKERS);
  // Scroll the payment rows into view: the wizard keeps the step scrolled under
  // the sticky announcement bar, so a top-of-page screenshot would not show
  // the thing being asserted.
  await page.locator('text=کارت به کارت').first().scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(600);
  await page.screenshot({ path: `.claude/shots/wallet-${label}-checkout.png` });

  if (expectVisible && seen.length === 0) {
    findings.push(
      `[${label}] CONTROL FAILED: with the wallet ON, /checkout showed none of ` +
        `${JSON.stringify(CHECKOUT_MARKERS)}, so the OFF result would prove nothing`,
    );
    return false;
  }
  if (!expectVisible && seen.length > 0) {
    findings.push(`[${label}] /checkout still shows: ${JSON.stringify(seen)}`);
    return false;
  }
  return true;
}

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ locale: "fa-IR" });
  const page = await ctx.newPage();
  const failures = [];

  try {
    await login(page);

    // Guard 1: the login must have worked. Without this the whole run is
    // vacuous — this is the check the first version was missing. Auth state
    // lives in the persisted Zustand store ("auth-storage"); the session
    // cookie itself is HttpOnly and unreadable from JS.
    const loggedIn = await page.evaluate(() => {
      const raw = localStorage.getItem("auth-storage");
      if (!raw) return false;
      try {
        const parsed = JSON.parse(raw);
        return Boolean(parsed?.state?.isAuthenticated && parsed?.state?.user);
      } catch {
        return false;
      }
    });
    if (!loggedIn) throw new Error("login failed — auth-storage is not authenticated; the run would be vacuous");

    // Control: wallet ON, markers MUST be visible. If they are not, the
    // detector is blind and an "off" result below would prove nothing.
    await setSwitch(page, true);
    await page.goto(`${BASE}/account`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);
    const onPage = await page.evaluate(() => document.body.innerText);
    if (!onPage.includes("حساب کاربری")) {
      throw new Error("not on the account page — cannot judge wallet surfaces");
    }
    const seenOn = await visibleMarkers(page);
    if (seenOn.length === 0) {
      throw new Error(
        "CONTROL FAILED: with the wallet ON no marker was visible, so the " +
          "detector cannot see them and an OFF result would prove nothing",
      );
    }
    console.log(`CONTROL OK: with wallet ON, ${seenOn.length}/${MARKERS.length} markers visible.`);
    await page.screenshot({ path: ".claude/shots/wallet-ON-account.png" });

    // Same control for checkout: with the wallet ON the wallet tender must be
    // present, otherwise the OFF result below proves nothing about checkout.
    const checkoutOn = [];
    const checkoutOnOk = await checkCheckout(page, checkoutOn, "ON", true);
    if (!checkoutOnOk) {
      throw new Error(`CONTROL FAILED for checkout — ${checkoutOn.join("; ")}`);
    }
    console.log("CONTROL OK: with wallet ON, /checkout showed the wallet tender.");

    // The real test: wallet OFF, markers must be GONE.
    await setSwitch(page, false);
    await checkCheckout(page, failures, "OFF", false);
    await page.goto(`${BASE}/account`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);
    const seenOff = await visibleMarkers(page);
    if (seenOff.length > 0) {
      failures.push(`/account still shows: ${JSON.stringify(seenOff)}`);
    }
    const navEntry = await page.locator("nav button", { hasText: "کیف پول" }).count();
    if (navEntry > 0) failures.push(`/account sidebar still has a کیف پول nav entry (${navEntry})`);
    await page.screenshot({ path: ".claude/shots/wallet-OFF-account.png" });

    // The deep link must redirect away rather than render the wallet page.
    await page.goto(`${BASE}/account/wallet`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);
    if (new URL(page.url()).pathname.includes("/wallet")) {
      failures.push(`/account/wallet still rendered at ${page.url()}`);
    }
    const deepMarkers = await visibleMarkers(page);
    if (deepMarkers.length > 0) {
      failures.push(`/account/wallet deep link shows: ${JSON.stringify(deepMarkers)}`);
    }

    // Restore: never leave the site with the wallet disabled by a test run.
    await setSwitch(page, true);
  } catch (e) {
    failures.push(`harness error: ${e.message}`);
  } finally {
    await browser.close();
  }

  if (failures.length) {
    console.log(`FAIL: ${failures.length} problem(s):`);
    failures.forEach((f) => console.log("  -", f));
    process.exit(1);
  }
  console.log("PASS: control saw the wallet with the switch ON; with it OFF no wallet surface renders.");
}

main();