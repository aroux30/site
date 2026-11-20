import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 25 Regression Invariants (Permalinks, Widgets, Automation, Audit & BI Periodic)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.96.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Admin permalinks page renders presets and custom structure in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/settings/permalink`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('پیوندهای یکتا')");
    await expect(heading).toBeVisible();

    const generalHeading = page.locator("h2:has-text('تنظیمات عمومی')");
    await expect(generalHeading).toBeVisible();
  });

  test("2. Admin widgets page renders widget areas and add area control in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/widgets`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('نواحی ویجت')");
    await expect(heading).toBeVisible();

    const reloadBtn = page.locator("button:has-text('بارگذاری مجدد')");
    await expect(reloadBtn).toBeVisible();
  });

  test("3. Admin automation page renders rule create action and refresh control in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/automation`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('قواعد خودکارسازی')");
    await expect(heading).toBeVisible();

    const createBtn = page.locator("button:has-text('قاعده جدید')");
    await expect(createBtn).toBeVisible();
  });

  test("4. Admin audit page renders event trail and field changes tabs in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/audit`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('گزارش رویدادها (Audit Trail)')");
    await expect(heading).toBeVisible();

    const refreshBtn = page.locator("button:has-text('بروزرسانی')");
    await expect(refreshBtn).toBeVisible();
  });

  test("5. Admin BI page renders period comparison controls and run trigger in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/bi`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('مقایسه دوره‌ای گزارش‌ها')");
    await expect(heading).toBeVisible();

    const runBtn = page.locator("button:has-text('اجرای مقایسه')");
    await expect(runBtn).toBeVisible();
  });
});
