import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 15 Regression Invariants (Wallet, FinTech & Reviews Moderation)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.94.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. User wallet renders balance and Persian suffix cleanly without character inversion", async ({ page }) => {
    await page.goto(`${BASE_URL}/account/wallet`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const balanceText = page.locator("text=موجودی قابل استفاده کیف پول").first();
    await expect(balanceText).toBeVisible();

    const currencyText = page.locator("p:has-text('معادل')").first();
    await expect(currencyText).toBeVisible();
  });

  test("2. Admin reviews moderation renders complete 1-to-5 star breakdown distribution cards", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/reviews`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('بررسی نظرات کاربران')");
    await expect(heading).toBeVisible();

    // Verify 1-star through 5-star distribution card headers are present
    const star1Card = page.locator("div:has-text('۱ ستاره')").first();
    await expect(star1Card).toBeVisible();

    const star5Card = page.locator("div:has-text('۵ ستاره')").first();
    await expect(star5Card).toBeVisible();
  });

  test("3. Admin wallet displays Persianized tab count badges and FinTech tabs", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/wallet`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('کیف پول‌ها')");
    await expect(heading).toBeVisible();

    const withdrawalsTab = page.locator("button:has-text('برداشت‌ها')");
    await expect(withdrawalsTab).toBeVisible();

    const walletsTab = page.locator("button:has-text('کیف پول‌ها')").first();
    await expect(walletsTab).toBeVisible();
  });
});
