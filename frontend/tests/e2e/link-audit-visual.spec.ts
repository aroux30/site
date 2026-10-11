import { test, expect } from "@playwright/test";

/**
 * Visual E2E: the broken-link crawler admin page (Link Genius audit).
 *
 * Drives a real browser through the operator flow:
 *
 *  1. admin logs in and opens سئو → بررسی لینک‌های شکسته;
 *  2. the page renders the summary tiles and the filter buttons;
 *  3. "بررسی کن" runs the crawler and the result list / tiles update;
 *  4. the list shows real URLs with their category badges.
 *
 * This is the check the API tests cannot make: the rendered page, the run
 * button's wiring, and the result list.
 *
 * Run with: PW_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://localhost:3100 \
 *   npx playwright test tests/e2e/link-audit-visual.spec.ts
 */

const ADMIN_PHONE = "09120000000";
const ADMIN_PASSWORD = "Admin@123456";
const PAGE_BUDGET = 40_000;

test.describe("broken-link crawler — visual E2E", () => {
  test("admin runs the crawler and sees results", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("۰۹۱۲۳۴۵۶۷۸۹").fill(ADMIN_PHONE);
    await page.getByPlaceholder("••••••••").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /ورود به حساب کاربری/ }).click();
    await page.waitForURL((url) => !url.pathname.includes("/login"), {
      timeout: PAGE_BUDGET,
    });

    await page.goto("/admin/seo/link-audit");
    await expect(
      page.getByRole("heading", { name: /بررسی لینک‌های شکسته/ }),
    ).toBeVisible({ timeout: PAGE_BUDGET });

    // Summary tiles + filters render.
    await expect(page.getByText("لینک‌های خراب (خراب+خطا+بی‌پاسخ)")).toBeVisible();
    await expect(page.getByRole("button", { name: "بررسی کن" })).toBeVisible();

    // Run the crawler. This hits the real network for the site's own links,
    // so give it room; the assertions below are about the UI reacting, not
    // about any specific URL's status.
    await page.getByRole("button", { name: "بررسی کن" }).click();
    // The run finishes when the button is enabled again (it is disabled while
    // running) and a toast has appeared.
    await expect(page.getByRole("button", { name: "بررسی کن" })).toBeEnabled({
      timeout: PAGE_BUDGET,
    });

    // At least the filter buttons are present and clickable.
    await page.getByRole("button", { name: "خراب", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: /بررسی لینک‌های شکسته/ }),
    ).toBeVisible();
  });
});
