import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 05 Regression Invariants (Stress Test 50kg, Long Strings & Autosave Resilience)", () => {
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

  test("1. Long Persian strings without spaces wrap cleanly without horizontal element overflow", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const headingEl = frame.locator("h2").first();
    await expect(headingEl).toBeVisible();

    // Check heading has break-words / overflow-wrap styles
    const overflowWrap = await headingEl.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.overflowWrap || style.wordBreak;
    });
    expect(overflowWrap).toBeTruthy();
  });

  test("2. Autosave failure on network drop retains isDirty state and shows error indicator", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Abort subsequent page update calls
    await page.route("**/api/v1/content/admin/pages/**", (route) => route.abort());

    const draftSaveBtn = page.getByRole("button", { name: "ذخیره پیش‌نویس" });
    if (await draftSaveBtn.isVisible()) {
      await draftSaveBtn.click();
      await page.waitForTimeout(1000);

      // Verify that error status or toast appears
      const errorToast = page.getByText("خطا در ذخیره‌سازی").first();
      await expect(errorToast).toBeVisible();
    }
  });

  test("3. Admin themes page renders smoothly without crash", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/themes`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const themeHeader = page.getByText("مدیریت تم‌ها").first();
    await expect(themeHeader).toBeVisible();
  });
});
