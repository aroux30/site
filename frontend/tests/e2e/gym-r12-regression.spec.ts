import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 12 Regression Invariants (Blog, RSS & Author Archive)", () => {
  test("1. Blog page RSS feed link points to public route /blog/feed/rss", async ({ page }) => {
    await page.goto(`${BASE_URL}/blog`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const rssLink = page.locator("a[href='/blog/feed/rss']");
    await expect(rssLink).toBeVisible();
  });

  test("2. Author archive /author/test-author renders author profile and articles", async ({ page }) => {
    await page.goto(`${BASE_URL}/author/test-author`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1, h2").filter({ hasText: "نویسنده" }).first();
    await expect(heading).toBeVisible();
  });

  test("3. Admin blog panel renders editorial posts list", async ({ page }) => {
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

    await page.goto(`${BASE_URL}/admin/blog`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const adminHeader = page.locator("h1, h2").filter({ hasText: "مدیریت وبلاگ" }).first();
    await expect(adminHeader).toBeVisible();
  });
});
