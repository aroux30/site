import { test, expect } from "@playwright/test";

/**
 * Visual E2E: the single tax rate (owner review 2026-10-09/10).
 *
 * Before the removal there were four VAT rates (12 dead settings field, 9
 * engine, 10 quote fallback, hard-coded «۱۰٪» labels). This suite drives a
 * real browser through the exact flow the owner reviewed:
 *
 *  1. admin logs in and opens تنظیمات → مالی و پرداخت;
 *  2. the tax field shows the single configured rate (9) and the honest help
 *     text — not the old «طبق قانون ... (۱۰٪)» line;
 *  3. the «موتور مالیات» sidebar item is gone;
 *  4. a customer adds an in-stock product to the cart and the cart summary
 *     shows the VAT row labelled with the SAME rate (۹٪), not ۱۰٪;
 *  5. checkout renders without an error shell.
 *
 * Timing note: with Elasticsearch down the faceted search falls back to
 * Postgres and takes ~8s per request on this dev stack, so the suite gives
 * the grid a generous first-render budget instead of fighting it.
 *
 * Run with: PW_SKIP_WEBSERVER=1 npx playwright test tests/e2e/tax-rate-visual.spec.ts
 */

const ADMIN_PHONE = "09120000000";
const ADMIN_PASSWORD = "Admin@123456";
const EXPECTED_RATE_FA = "۹"; // the configured rate (9%) in Persian digits
const SLOW_GRID = 45_000; // Postgres fallback + dev compile

test.describe("single tax rate — visual E2E", () => {
  test("admin settings shows the one rate; the tax engine is gone", async ({
    page,
  }) => {
    // ── 1. Login ─────────────────────────────────────────────────────────
    await page.goto("/login");
    await page.getByPlaceholder("۰۹۱۲۳۴۵۶۷۸۹").fill(ADMIN_PHONE);
    await page.getByPlaceholder("••••••••").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /ورود به حساب کاربری/ }).click();

    // Redirected away from /login once the cookie session is set.
    await page.waitForURL((url) => !url.pathname.includes("/login"), {
      timeout: 30_000,
    });

    // ── 2. Admin settings → financial tab ────────────────────────────────
    await page.goto("/admin/settings");
    await page.getByRole("tab", { name: /مالی و پرداخت/ }).click();

    // The one rate field: value 9 + honest help text. The Label has no
    // htmlFor, so scope by the containing field block.
    const taxField = page
      .locator("div.space-y-2")
      .filter({ hasText: "نرخ مالیات بر ارزش افزوده (درصد)" });
    await expect(taxField.locator("input")).toHaveValue("9", { timeout: 20_000 });
    await expect(
      page.getByText(
        "نرخ واحد مالیات — در سبد خرید، چک‌اوت و سفارش‌های جدید همین نرخ اعمال می‌شود",
      ),
    ).toBeVisible();

    // The old hard-coded help line must NOT be present anywhere on the page.
    await expect(
      page.getByText("طبق قانون مالیات بر ارزش افزوده ایران (۱۰٪)"),
    ).toHaveCount(0);

    // ── 3. The removed engine has no sidebar entry ───────────────────────
    await expect(page.getByRole("link", { name: /موتور مالیات/ })).toHaveCount(0);
  });

  test("storefront cart + checkout show the same configured rate", async ({
    page,
  }) => {
    // ── 4. Add an in-stock product to the cart as a guest ────────────────
    // The grid is slow (Postgres fallback) and not every seeded product has
    // stock («در حال حاضر ناموجود است» renders instead of the button), so:
    // wait once for the grid, collect hrefs, then walk them.
    await page.goto("/products");
    const links = page.locator('a[href^="/products/"]');
    await expect(links.first()).toBeVisible({ timeout: SLOW_GRID });
    const hrefs = (
      await links.evaluateAll((els) =>
        els.map((el) => el.getAttribute("href")).filter((h): h is string => !!h),
      )
    ).slice(0, 10);
    expect(hrefs.length).toBeGreaterThan(0);

    let added = false;
    for (const href of hrefs) {
      await page.goto(href);
      const addToCart = page
        .getByRole("button", { name: /افزودن به سبد خرید/ })
        .first();
      try {
        await addToCart.waitFor({ state: "visible", timeout: 15_000 });
        await addToCart.click();
        added = true;
        break;
      } catch {
        // out of stock — try the next product
      }
    }
    expect(added, "no in-stock product found among the first 10").toBe(true);

    // ── 5. Cart summary: the VAT row is labelled with the configured rate ─
    await page.goto("/cart");
    const vatRow = page.getByText(
      new RegExp(`مالیات بر ارزش افزوده \\(${EXPECTED_RATE_FA}٪\\)`),
    );
    await expect(vatRow).toBeVisible({ timeout: 20_000 });

    // The hard-coded ۱۰٪ label must be gone from the whole page.
    await expect(page.getByText("مالیات بر ارزش افزوده (۱۰٪)")).toHaveCount(0);

    // The free-shipping promise must also be gone (previous wave).
    await expect(page.getByText(/ارسال رایگان/)).toHaveCount(0);

    // ── 6. Checkout renders without an error shell ────────────────────────
    await page.goto("/checkout");
    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByText(/خطایی رخ داد|Something went wrong/)).toHaveCount(0);
  });
});
