import { test, expect } from "@playwright/test";

/**
 * Visual E2E: the Link Genius admin page (Rank Math Pro parity, 2026-10-11).
 *
 * Drives a real browser through the exact flow an operator uses:
 *
 *  1. admin logs in and opens سئو → نابغهٔ لینک;
 *  2. the suggestions tab renders a post picker and the two panels
 *     (suggestions + incoming links);
 *  3. switching to the keyword-maps tab shows the manager;
 *  4. creating a map persists it (the row appears with its keyword chip);
 *  5. deleting it goes through the in-app confirm dialog and the row
 *     disappears — proving the two-segment DELETE is not shadowed by the
 *     generic metadata-delete route.
 *
 * This is the check the API tests cannot make: they exercise the endpoints,
 * not the rendered page, the tab switching, or the confirm dialog.
 *
 * Run with: PW_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://localhost:3100 \
 *   npx playwright test tests/e2e/link-genius-visual.spec.ts
 */

const ADMIN_PHONE = "09120000000";
const ADMIN_PASSWORD = "Admin@123456";
const PAGE_BUDGET = 30_000;

test.describe("link genius — visual E2E", () => {
  test("admin manages keyword maps and reads suggestions", async ({ page }) => {
    // ── 1. Login ─────────────────────────────────────────────────────────
    await page.goto("/login");
    await page.getByPlaceholder("۰۹۱۲۳۴۵۶۷۸۹").fill(ADMIN_PHONE);
    await page.getByPlaceholder("••••••••").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /ورود به حساب کاربری/ }).click();
    await page.waitForURL((url) => !url.pathname.includes("/login"), {
      timeout: PAGE_BUDGET,
    });

    // ── 2. Open the Link Genius page ─────────────────────────────────────
    await page.goto("/admin/seo/link-genius");
    await expect(
      page.getByRole("heading", { name: /نابغهٔ لینک/ }),
    ).toBeVisible({ timeout: PAGE_BUDGET });

    // Suggestions tab: the post picker and both panels render.
    await expect(page.getByText("پیشنهاد برای پیوند دادن")).toBeVisible({
      timeout: PAGE_BUDGET,
    });
    await expect(page.getByText("لینک‌های ورودی به این نوشته")).toBeVisible();
    // The post picker is populated. `<option>` is never "visible" to Playwright
    // (the OS draws it), so assert on the SELECT's value instead: the only way
    // it is empty is the "نوشته‌ای نیست" placeholder, which renders solely when
    // the post list failed to load. A non-empty value + a real option proves
    // posts arrived.
    const postSelect = page.locator("select#lg-post");
    await expect(postSelect).not.toHaveValue("", { timeout: PAGE_BUDGET });

    // ── 3. Switch to the keyword-maps tab ────────────────────────────────
    await page.getByRole("tab", { name: /نقشه‌های کلیدواژه/ }).click();
    await expect(page.getByRole("button", { name: /نقشهٔ جدید/ })).toBeVisible();

    // ── 4. Create a map ──────────────────────────────────────────────────
    const uniqueName = `E2E-${Date.now()}`;
    await page.getByRole("button", { name: /نقشهٔ جدید/ }).click();
    await page.locator("#map-name").fill(uniqueName);
    await page.locator("#map-url").fill("/products/pubg-mobile");
    await page.locator("#map-kw").fill("پابجی\nشارژ پابجی");
    await page.getByRole("button", { name: "ذخیره" }).click();

    // The new row appears with its name and both keyword chips.
    await expect(page.getByText(uniqueName)).toBeVisible({ timeout: PAGE_BUDGET });
    await expect(page.getByText("شارژ پابجی")).toBeVisible();

    // ── 5. Delete it through the in-app confirm ──────────────────────────
    const row = page.locator("div.rounded-lg.border").filter({ hasText: uniqueName });
    await row.getByRole("button", { name: "حذف" }).click();
    // The confirm dialog (not window.confirm) appears; confirm it.
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "حذف" }).last().click();

    // The row is gone.
    await expect(page.getByText(uniqueName)).toHaveCount(0, { timeout: PAGE_BUDGET });
  });
});
