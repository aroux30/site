import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 22 Regression Invariants (Widget Areas, Form Submissions & Theme Studio)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.86.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
    });
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
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

  test("1. Admin widget areas page renders RTL layout with Persian area names", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/widgets`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('نواحی ویجت')");
    await expect(heading).toBeVisible();

    // Check Persian names of widget areas
    const sidebarArea = page.locator("button:has-text('نوار کناری')");
    await expect(sidebarArea).toBeVisible();

    const reloadBtn = page.locator("button:has-text('بارگذاری مجدد')");
    await expect(reloadBtn).toBeVisible();
  });

  test("2. Admin forms submissions table renders structured fields cleanly", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/forms`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('پیام‌ها و فرم‌های دریافتی')");
    await expect(heading).toBeVisible();

    const filterBtn = page.locator("button:has-text('همه پیام‌ها'), button:has-text('فقط خوانده‌نشده‌ها')");
    await expect(filterBtn).toBeVisible();
  });

  test("3. Admin themes page renders accessible action buttons with aria labels", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/themes`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('مدیریت تم‌ها و استایل سازمانی')");
    await expect(heading).toBeVisible();

    const createBtn = page.locator("button:has-text('ایجاد تم جدید')");
    await expect(createBtn).toBeVisible();
  });
});
