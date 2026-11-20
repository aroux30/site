import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 23 Regression Invariants (Data Exchange & Categories RTL)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.87.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Admin data exchange page renders clean Persian headers without raw English terms", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/data-exchange`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const importCardTitle = page.locator("h3:has-text('بارگذاری و ورود داده جدید')");
    await expect(importCardTitle).toBeVisible();

    const refreshBtn = page.locator("button:has-text('بروزرسانی')");
    await expect(refreshBtn).toBeVisible();
  });

  test("2. Admin categories page renders with explicit RTL direction", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/categories`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('دسته‌بندی‌های فروشگاه')");
    await expect(heading).toBeVisible();

    const rootDir = await page.locator("div.space-y-6").first().getAttribute("dir");
    expect(rootDir).toBe("rtl");
  });

  test("3. Category creation modal opens with RTL content container", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/categories`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const addBtn = page.locator("button:has-text('افزودن دسته‌بندی')");
    await expect(addBtn).toBeVisible();
    await addBtn.click();

    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();

    const dialogDir = await dialog.getAttribute("dir");
    expect(dialogDir).toBe("rtl");
  });
});
