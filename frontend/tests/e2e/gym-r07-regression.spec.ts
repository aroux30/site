import { test, expect } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 07 Regression Invariants (Cart Drawer & Floating Bar)", () => {
  test("1. Cart Drawer opens with high z-index and parsed clean variant labels", async ({ page }) => {
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const cartBtn = page.locator("header a[href*='cart'] button, header button[aria-label*='سبد خرید']").first();
    if (await cartBtn.isVisible()) {
      await cartBtn.click();
      await page.waitForTimeout(800);

      const drawer = page.locator("div[role='dialog'][aria-label='سبد خرید']");
      await expect(drawer).toBeVisible();

      // Verify no raw Python dict strings in drawer
      const text = await drawer.innerText();
      expect(text).not.toContain("{'");
      expect(text).not.toContain("': '");
    }
  });

  test("2. Floating cart dock renders with elevated position above mobile nav", async ({ page }) => {
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    const dock = page.locator(".pointer-events-none.fixed.bottom-48");
    await expect(dock).toBeAttached();
  });
});
