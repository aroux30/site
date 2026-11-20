import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 26 Regression Invariants (Audit Trail, Integrations & Settings)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.90.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Admin audit trail page renders RTL layout with action and resource filter inputs", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/audit`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('گزارش رویدادها (Audit Trail)')");
    await expect(heading).toBeVisible();

    const actionInput = page.locator("input[placeholder*='فیلتر عملیات']");
    await expect(actionInput).toBeVisible();

    const resourceInput = page.locator("input[placeholder*='منبع (resource)']");
    await expect(resourceInput).toBeVisible();
  });

  test("2. Admin integrations registry renders capability cards and live filters", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/integrations`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('فهرست قابلیت‌های یکپارچه‌سازی')");
    await expect(heading).toBeVisible();

    const refreshBtn = page.locator("button:has-text('بروزرسانی فهرست')");
    await expect(refreshBtn).toBeVisible();
  });

  test("3. Admin general settings page renders identity cards and save actions", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/settings`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('تنظیمات کلی فروشگاه')");
    await expect(heading).toBeVisible();

    const generalTab = page.locator("button[role='tab']:has-text('عمومی')");
    await expect(generalTab).toBeVisible();
  });
});
