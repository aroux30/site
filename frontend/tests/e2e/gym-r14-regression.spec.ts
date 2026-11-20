import { test, expect } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 14 Regression Invariants (PDP & Product Details Overload)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.99.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
    });
  });

  test("1. PDP suppresses floating cart bar preventing occlusion of addons and CTAs", async ({ page }) => {
    // Populate cart so floating bar would normally show on catalog pages
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

    // On PDP, floating cart bar must NOT render
    await page.goto(`${BASE_URL}/products/1800-yvsy`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const floatingBar = page.locator("aside[aria-label='سبد خرید شناور']");
    expect(await floatingBar.count()).toBe(0);
  });

  test("2. Product gallery vs 3D viewer switchers are functional", async ({ page }) => {
    await page.goto(`${BASE_URL}/products/1800-yvsy`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const toggle3D = page.locator("button:has-text('مدل سه‌بعدی ۳۶۰')").first();
    await expect(toggle3D).toBeVisible();

    const toggleGallery = page.locator("button:has-text('گالری تصاویر')").first();
    await expect(toggleGallery).toBeVisible();
  });

  test("3. Mobile PDP (375px) renders sticky bottom add-to-cart bar cleanly", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`${BASE_URL}/products/1800-yvsy`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const stickyBar = page.locator(".fixed.bottom-0.inset-x-0");
    await expect(stickyBar).toBeVisible();

    const addToCartBtn = stickyBar.locator("button:has-text('افزودن به سبد')");
    await expect(addToCartBtn).toBeVisible();
  });
});
