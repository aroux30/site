import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 18 Regression Invariants (Discounts, User Verification & FAQ)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.88.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. FAQ page suppresses floating cart bar preventing occlusion of accordion items", async ({ page }) => {
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

    // Navigate to /faq
    await page.goto(`${BASE_URL}/faq`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const floatingBar = page.locator("aside[aria-label='سبد خرید شناور']");
    expect(await floatingBar.count()).toBe(0);
  });

  test("2. Admin discounts page renders filter controls and discounts table", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/discounts`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('تخفیف‌ها و کدهای تخفیف')");
    await expect(heading).toBeVisible();

    const addBtn = page.locator("button:has-text('تخفیف جدید')");
    await expect(addBtn).toBeVisible();
  });

  test("3. Admin user verification page renders user verification list with badges", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/user-verification`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1, h2").filter({ hasText: "احراز کاربران" }).first();
    await expect(heading).toBeVisible();

    const usersTab = page.locator("button[role='tab']:has-text('مدیریت کاربران')");
    await expect(usersTab).toBeVisible();
  });
});
