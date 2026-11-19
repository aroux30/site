import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 04 Regression Invariants (Responsive 35kg, RTL & Dark Mode)", () => {
  test("1. Mobile viewport (375px) has zero horizontal overflow on storefront", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const docWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(docWidth).toBeLessThanOrEqual(375);
  });

  test("2. Floating bottom cart dock on mobile is elevated to prevent collision with chat FAB", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });

    // Check dock positioning class
    const dock = page.locator(".pointer-events-none.fixed.bottom-48");
    await expect(dock).toBeAttached();
  });

  test("3. Mobile builder studio keeps canvas visible without 640px dual-sidebar crush", async ({ page }) => {
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
    await page.setViewportSize({ width: 375, height: 812 });

    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Canvas main area must be visible
    const mainCanvas = page.locator("main[class*='overflow-y-auto']");
    await expect(mainCanvas).toBeVisible();

    const docWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(docWidth).toBeLessThanOrEqual(375);
  });

  test("4. Dark mode properly shifts --background channel to dark value", async ({ page }) => {
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => document.documentElement.classList.add("dark"));

    const bgVal = await page.evaluate(() =>
      window.getComputedStyle(document.documentElement).getPropertyValue("--background").trim()
    );
    expect(bgVal).toBe("150 10% 5%");
  });
});
