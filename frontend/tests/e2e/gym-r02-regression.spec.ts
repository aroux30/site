import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 02 Regression Invariants (Builder Controls - 10kg)", () => {
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

  test("1. Save Draft action must succeed without 500 internal server error", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const draftSaveBtn = page.getByRole("button", { name: "ذخیره پیش‌نویس" });
    await expect(draftSaveBtn).toBeVisible();

    const [patchResponse] = await Promise.all([
      page.waitForResponse((res) => res.url().includes("/content/admin/pages/") && res.request().method() === "PATCH", { timeout: 15000 }),
      draftSaveBtn.click(),
    ]);

    expect(patchResponse.status()).toBe(200);
  });

  test("2. Blocks palette tabs must all render explicit count badges", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const blocksTab = page.getByRole("button", { name: "افزودن بلوک" });
    await blocksTab.click();

    // Check all 3 tabs have counts in parentheses
    const basicTab = page.locator("button:has-text('بلوک‌ها (')");
    const patternsTab = page.locator("button:has-text('الگوها (')");
    const templatesTab = page.locator("button:has-text('قالب‌های من (')");

    await expect(basicTab).toBeVisible();
    await expect(patternsTab).toBeVisible();
    await expect(templatesTab).toBeVisible();
  });

  test("3. Global Styles dialog must open cleanly with ASCII hex values and reset affordance", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const globalStylesBtn = page.getByRole("button", { name: "استایل سراسری" });
    await globalStylesBtn.click();

    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();

    // Reset button exists
    const resetBtn = dialog.locator("button:has-text('بازنشانی به تم پیش‌فرض')");
    await expect(resetBtn).toBeVisible();

    // Color inputs are valid hex (ASCII)
    const primaryInput = dialog.locator("input[placeholder='#059669']");
    const primaryVal = await primaryInput.inputValue();
    expect(primaryVal).toMatch(/^#[0-9a-fA-F]{3,8}$/);
  });
});
