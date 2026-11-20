import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 20 Regression Invariants (System Health, Link Genius & Calendar)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.84.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Admin system health renders diagnostic controls and history trigger", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/system-health`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('سلامت سامانه')");
    await expect(heading).toBeVisible();

    const checkBtn = page.locator("button:has-text('بررسی و ثبت')");
    await expect(checkBtn).toBeVisible();

    const infoBtn = page.locator("button:has-text('اطلاعات سیستم')");
    await expect(infoBtn).toBeVisible();
  });

  test("2. Admin link genius page renders tabbed layout with RTL text flow and post selector", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/link-genius`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('نابغهٔ لینک (Link Genius)')");
    await expect(heading).toBeVisible();

    const suggestionsTab = page.locator("button[role='tab']:has-text('پیشنهاد لینک')");
    await expect(suggestionsTab).toBeVisible();

    const mapsTab = page.locator("button[role='tab']:has-text('نقشه‌های کلیدواژه')");
    await expect(mapsTab).toBeVisible();
  });

  test("3. Admin calendar page renders operations header and filter controls", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/calendar`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('تقویم عملیاتی')");
    await expect(heading).toBeVisible();

    const refreshBtn = page.locator("button:has-text('بروزرسانی')");
    await expect(refreshBtn).toBeVisible();
  });
});
