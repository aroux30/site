import { test, expect } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 06 Regression Invariants (Focus, Keyboard, Toaster UX & Skip-Link)", () => {
  test("1. Skip-to-content link uses fixed positioning with high z-index", async ({ page }) => {
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    const skipLink = page.locator("a[href='#main-content']");
    await expect(skipLink).toBeAttached();

    const cls = await skipLink.getAttribute("class");
    expect(cls).toContain("focus:fixed");
    expect(cls).toContain("focus:z-[100]");
  });

  test("2. Toaster container is placed at sm:end-4 opposite to chat FAB", async ({ page }) => {
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    const toaster = page.locator("div[dir='rtl'].fixed");
    await expect(toaster).toBeAttached();

    const cls = await toaster.getAttribute("class");
    expect(cls).toContain("sm:end-4");
  });

  test("3. Toast close button does not use red background circle on default toasts", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const draftSaveBtn = page.getByRole("button", { name: "ذخیره پیش‌نویس" });
    if (await draftSaveBtn.isVisible()) {
      await draftSaveBtn.click();
      await page.waitForTimeout(1000);

      const closeBtn = page.locator("button[aria-label='بستن']").first();
      if (await closeBtn.isVisible()) {
        const btnClass = await closeBtn.getAttribute("class");
        expect(btnClass).not.toContain("bg-red-500");
      }
    }
  });
});
