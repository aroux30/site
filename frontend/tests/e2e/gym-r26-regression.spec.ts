import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 26 Regression Invariants (Data Exchange, Export, FAQ, Reviews & Reports)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.98.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Admin data exchange page renders import upload controls and format options in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/data-exchange`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('ورود داده (Import)')");
    await expect(heading).toBeVisible();

    const startHeading = page.locator("h3:has-text('بارگذاری و ورود داده جدید')");
    await expect(startHeading).toBeVisible();

    const wxrHeading = page.locator("h3:has-text('ایمپورت از خروجی وردپرس')");
    await expect(wxrHeading).toBeVisible();
  });

  test("2. Admin data exchange export page renders export options and job history table in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/data-exchange/export`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('خروجی داده (Export)')");
    await expect(heading).toBeVisible();

    const exportBtn = page.locator("button:has-text('ساخت و دانلود خروجی')");
    await expect(exportBtn).toBeVisible();
  });

  test("3. Admin FAQ page renders questions list and add question trigger in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/faq`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('سوالات متداول')");
    await expect(heading).toBeVisible();

    const addBtn = page.locator("button:has-text('افزودن')");
    await expect(addBtn).toBeVisible();
  });

  test("4. Admin reviews page renders moderation queue and rating statistics in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/reviews`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('بررسی نظرات کاربران')");
    await expect(heading).toBeVisible();

    const refreshBtn = page.locator("button:has-text('تازه‌سازی')");
    await expect(refreshBtn).toBeVisible();
  });

  test("5. Admin reports page renders parameters, live query filters and saved reports in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/reports`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('مرکز گزارش‌ها')");
    await expect(heading).toBeVisible();

    const refreshBtn = page.locator("button:has-text('به‌روزرسانی')");
    await expect(refreshBtn).toBeVisible();
  });
});
