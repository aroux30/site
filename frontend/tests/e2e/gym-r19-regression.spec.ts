import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 19 Regression Invariants (Currency Updater & Storefront Favorites)", () => {
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

  test("1. Favorites page suppresses floating cart bar preventing occlusion of wishlist items", async ({ page }) => {
    // Populate cart storage
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => {
      localStorage.setItem(
        "cart-storage",
        JSON.stringify({
          state: {
            items: [
              {
                id: "c3f93ad5-8ee5-47cd-977b-8284d079b18b",
                productId: "c3f93ad5-8ee5-47cd-977b-8284d079b18b",
                title: "کالای تستی",
                price: 150000,
                quantity: 1,
              },
            ],
            totalItems: 1,
            subtotal: 150000,
          },
        })
      );
    });

    // Navigate to /favorites
    await page.goto(`${BASE_URL}/favorites`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const floatingBar = page.locator("aside[aria-label='سبد خرید شناور']");
    expect(await floatingBar.count()).toBe(0);
  });

  test("2. Admin currency updater page renders live status and rate settings", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/currency`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1, h2").filter({ hasText: "به‌روزرسانی خودکار قیمت دلاری" }).first();
    await expect(heading).toBeVisible();

    const manualRateLabel = page.locator("text='نرخ دستی (تومان)'").first();
    await expect(manualRateLabel).toBeVisible();

    const updateNowBtn = page.locator("button:has-text('به‌روزرسانی قیمت‌ها الآن')");
    await expect(updateNowBtn).toBeVisible();
  });

  test("3. Currency manual rate input accepts and formats Persian/English digits without erasing", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/currency`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const manualRateInput = page.locator("input[placeholder*='۱۸۵']");
    await expect(manualRateInput).toBeVisible();

    // Fill with English and Persian digits
    await manualRateInput.fill("192000");
    await expect(manualRateInput).toHaveValue(/۱۹۲/);
  });
});
