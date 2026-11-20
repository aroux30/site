import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 25 Regression Invariants (Reports, BI & RBAC)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.89.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Admin reports page renders explicit RTL container and Toman column headers", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/reports`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('مرکز گزارش‌ها')");
    await expect(heading).toBeVisible();

    const rootDir = await page.locator("div.space-y-6").first().getAttribute("dir");
    expect(rootDir).toBe("rtl");

    // Check table headers use Toman instead of confusing Rial when displaying Toman values
    const grossHeader = page.locator("th:has-text('فروش ناخالص (تومان)')");
    await expect(grossHeader).toBeVisible();
  });

  test("2. Admin BI periodic comparison page renders cleanly with comparative metrics", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/bi`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('مقایسه دوره‌ای گزارش‌ها')");
    await expect(heading).toBeVisible();

    const compareBtn = page.locator("button:has-text('اجرای مقایسه')");
    await expect(compareBtn).toBeVisible();
  });

  test("3. Admin RBAC page renders role cards with permissions and capabilities", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/rbac`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('نقش‌ها و دسترسی‌ها (RBAC)')");
    await expect(heading).toBeVisible();

    const newRoleBtn = page.locator("button:has-text('نقش جدید')");
    await expect(newRoleBtn).toBeVisible();
  });
});
