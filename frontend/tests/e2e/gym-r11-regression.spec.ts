import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 11 Regression Invariants (Checkout & Card Transfer)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.96.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Checkout page suppresses floating cart bar to prevent UI duplication", async ({ page }) => {
    await page.goto(`${BASE_URL}/checkout`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const floatingBar = page.locator("aside[aria-label='سبد خرید شناور']");
    expect(await floatingBar.count()).toBe(0);
  });

  test("2. Card transfer page without orderId renders clean guidance card rather than error box", async ({ page }) => {
    await page.goto(`${BASE_URL}/checkout/card-transfer`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const heading = page.locator("h1:has-text('شناسه سفارش مشخص نشده است')");
    await expect(heading).toBeVisible();

    const viewOrdersBtn = page.locator("a[href='/account/orders'] button");
    await expect(viewOrdersBtn).toBeVisible();
  });
});
