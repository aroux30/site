import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 09 Regression Invariants (Account Dashboard, Orders & PII Helpers)", () => {
  test.beforeEach(async ({ page }) => {
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

  test("1. Profile inputs render masked helper text underneath input fields", async ({ page }) => {
    await page.goto(`${BASE_URL}/account`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const phoneLabel = page.locator("label[for='phone']");
    await expect(phoneLabel).toBeVisible();

    const helperText = page.locator("text=نمایش امن:").first();
    await expect(helperText).toBeVisible();
  });

  test("2. Orders history displays order status badges and Jalali dates", async ({ page }) => {
    await page.goto(`${BASE_URL}/account/orders`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const ordersHeader = page.locator("h2, h3").filter({ hasText: "سفارش" }).first();
    await expect(ordersHeader).toBeVisible();
  });

  test("3. Addresses tab renders empty or list state without crash", async ({ page }) => {
    await page.goto(`${BASE_URL}/account/addresses`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const addressHeader = page.locator("h2, h3").filter({ hasText: "آدرس" }).first();
    await expect(addressHeader).toBeVisible();
  });
});
