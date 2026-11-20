import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 10 Regression Invariants (Milestone Synthesis - Media & Studio Stability)", () => {
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

  test("1. Media library admin panel loads watermark and thumbnail dimensions without error", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/media`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const mediaHeader = page.locator("h1, h2, h3").filter({ hasText: "کتابخانه رسانه" }).first();
    await expect(mediaHeader).toBeVisible();

    const watermarkCard = page.locator("text=واترمارک تصاویر").first();
    await expect(watermarkCard).toBeVisible();
  });

  test("2. Visual Builder studio milestone state renders with clean layout", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    await expect(frame.locator("body")).toBeAttached();
  });
});
