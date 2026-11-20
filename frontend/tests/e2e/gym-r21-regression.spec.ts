import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 21 Regression Invariants (Visual Page Builder Controls & Inspector)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.85.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Blocks palette basic blocks render clean Persian descriptions without scrambled English parentheses", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const buttonBlock = page.locator("button:has-text('دکمه اقدام')");
    await expect(buttonBlock).toBeVisible();

    // Check description does not contain scrambled "(Call to Action)" BiDi artifact
    const descText = await buttonBlock.innerText();
    expect(descText).not.toContain("(to all");
    expect(descText).toContain("فراخوان");
  });

  test("2. Inspector panel Style tab renders clean neutral placeholder for width", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Select layer row from layers tree to activate inspector panel
    const layersBtn = page.locator("button:has-text('لایه‌ها')");
    await layersBtn.click();
    await page.waitForTimeout(500);

    const layerRow = page.locator("[data-layer-row]").first();
    await expect(layerRow).toBeVisible();
    await layerRow.click();
    await page.waitForTimeout(800);

    const styleTab = page.locator("[role='tab']:has-text('استایل')");
    await expect(styleTab).toBeVisible();
    await styleTab.click();

    // Width input placeholder
    const widthInput = page.locator("input[placeholder*='100% / 1280px']");
    await expect(widthInput).toBeVisible();
  });

  test("3. Global Styles dialog resets cleanly and syncs tokens", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const globalStylesBtn = page.locator("button:has-text('استایل سراسری')");
    await expect(globalStylesBtn).toBeVisible();
    await globalStylesBtn.click();

    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();

    const resetBtn = dialog.locator("button:has-text('بازنشانی به تم پیش‌فرض')");
    await expect(resetBtn).toBeVisible();
    await resetBtn.click();
    await expect(dialog).not.toBeVisible();
  });
});
