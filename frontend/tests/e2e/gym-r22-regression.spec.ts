import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 22 Regression Invariants (Local SEO, Breadcrumbs, Image SEO, Status & 404 Monitor)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.89.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
    });
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      { name: "access_token", value: token, url: "http://localhost:3000", httpOnly: false, sameSite: "Lax" },
    ]);
    await page.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user: { id: "47f274da-3abd-4d91-bc9c-83ba913fc66f", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });
  });

  test("1. Admin local SEO renders business profile form with RTL direction and schema controls", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/local`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('سئوی محلی (کسب‌وکار)')");
    await expect(heading).toBeVisible();

    const saveBtn = page.locator("button:has-text('ذخیره اطلاعات کسب‌وکار')");
    await expect(saveBtn).toBeVisible();
  });

  test("2. Admin breadcrumbs page renders trail configurations and save action", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/breadcrumbs`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('مسیر صفحه (Breadcrumbs)')");
    await expect(heading).toBeVisible();

    const homeLabelInput = page.locator("#bc-home");
    await expect(homeLabelInput).toBeVisible();

    const saveBtn = page.locator("button:has-text('ذخیره تنظیمات مسیر')");
    await expect(saveBtn).toBeVisible();
  });

  test("3. Admin image SEO page renders automatic filename metadata toggles", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/image`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('سئوی تصویر')");
    await expect(heading).toBeVisible();

    const saveBtn = page.locator("button:has-text('ذخیره تنظیمات سئوی تصویر')");
    await expect(saveBtn).toBeVisible();
  });

  test("4. Admin SEO status page renders diagnostic checks, data stats and backup buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/status`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('وضعیت و ابزارهای سئو')");
    await expect(heading).toBeVisible();

    const exportBtn = page.locator("button:has-text('خروجی JSON')");
    await expect(exportBtn).toBeVisible();

    const importBtn = page.locator("button:has-text('ایمپورت JSON')");
    await expect(importBtn).toBeVisible();
  });

  test("5. Admin 404 monitor page renders search input and refresh controls", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/404`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('مانیتور ۴۰۴')");
    await expect(heading).toBeVisible();

    const refreshBtn = page.locator("button:has-text('بازخوانی')");
    await expect(refreshBtn).toBeVisible();
  });
});
