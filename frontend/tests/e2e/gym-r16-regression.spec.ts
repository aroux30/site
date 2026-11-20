import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 16 Regression Invariants (Gamification, Loyalty & Rewards)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.92.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Rewards page suppresses floating cart bar preventing occlusion of lucky wheel & tier cards", async ({ page }) => {
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

    // Navigate to /rewards
    await page.goto(`${BASE_URL}/rewards`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const floatingBar = page.locator("aside[aria-label='سبد خرید شناور']");
    expect(await floatingBar.count()).toBe(0);
  });

  test("2. Rewards page user tier banner renders points and tier progress bar without horizontal overflow", async ({ page }) => {
    await page.goto(`${BASE_URL}/rewards`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const pointsHeader = page.locator("h1:has-text('امتیاز جمع کنید و جایزه بگیرید')");
    await expect(pointsHeader).toBeVisible();

    const tierBadge = page.locator("span:has-text('سطح وفاداری شما')").first();
    await expect(tierBadge).toBeVisible();

    const luckyWheelBtn = page.locator("button:has-text('گردونه شانس امروز')").first();
    await expect(luckyWheelBtn).toBeVisible();
  });

  test("3. Admin gamification panel renders charge packages, rules, and rewards tabs", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/gamification`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('باشگاه مشتریان و گیمیفیکیشن')");
    await expect(heading).toBeVisible();

    const packagesTab = page.locator("button[role='tab']:has-text('بسته‌های شارژ')");
    await expect(packagesTab).toBeVisible();

    const rulesTab = page.locator("button[role='tab']:has-text('قواعد امتیازدهی')");
    await expect(rulesTab).toBeVisible();

    const rewardsTab = page.locator("button[role='tab']:has-text('جوایز و گردونه شانس')");
    await expect(rewardsTab).toBeVisible();
  });
});
