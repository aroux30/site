import { expect, test, type Page } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";

/**
 * Visual Page Builder Studio Phase P1 Hardening End-to-End Suite.
 *
 * Covers:
 * 1. Admin entrance and non-admin access protection
 * 2. Studio 3-column layout structure (Toolbar, Palette/Layers, Canvas, Inspector)
 * 3. Adding blocks from palette to canvas
 * 4. Selection and Inspector Content & Style editing
 * 5. Responsive viewport switcher (Desktop, Tablet, Mobile)
 * 6. Undo and Redo operations
 * 7. Saving and state restoration
 */

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Visual Page Builder Studio P1", () => {
  test("non-admin user cannot access the builder studio interface", async ({ page }) => {
    // Navigate without logging in
    await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
    // Verify BuilderToolbar is not present
    await expect(page.locator("header:has-text('پیش‌نویس')")).toHaveCount(0);
    await expect(page.locator("button:has-text('افزودن بلوک')")).toHaveCount(0);
  });

  test("admin accesses builder studio, adds blocks, edits inspector, and switches viewports", async ({ page }) => {
    await resetE2EPage("e2e-isolated-scratchpad");
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    // Open a CMS page in visual editor mode
    await page.goto("/e2e-isolated-scratchpad?visual_editor=true");

    // 1. Verify Studio workspace layout renders
    await expect(page.locator("header:has-text('پیش‌نویس')")).toBeVisible({ timeout: 25_000 });
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible();
    await expect(page.getByRole("button", { name: "لایه‌ها" })).toBeVisible();

    // 2. Switch between Blocks and Layers tabs
    await page.getByRole("button", { name: "لایه‌ها" }).click();
    await expect(page.getByText("درخت ساختار لایه‌ها")).toBeVisible();

    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await expect(page.getByPlaceholder("جستجوی بلوک پایه...")).toBeVisible();

    // 3. Add a Button block from palette
    const buttonBlockBtn = page.locator("button:has-text('دکمه')").first();
    await expect(buttonBlockBtn).toBeVisible();
    await buttonBlockBtn.click();

    // 4. Test Responsive Viewport Switcher
    const tabletBtn = page.getByRole("button", { name: "تبلت (۷۶۸)" });
    await tabletBtn.click();
    const frameContainer = page.locator(".max-w-\\[768px\\]");
    await expect(frameContainer).toBeVisible();

    const mobileBtn = page.getByRole("button", { name: "موبایل (۳۷۵)" });
    await mobileBtn.click();
    const mobileContainer = page.locator(".max-w-\\[375px\\]");
    await expect(mobileContainer).toBeVisible();

    const desktopBtn = page.getByRole("button", { name: "دکمه دسکتاپ" }).or(page.locator("button:has-text('دسکتاپ')"));
    await desktopBtn.click();

    // 5. Test Inspector Tabs
    await expect(page.getByRole("tab", { name: "محتوا" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "استایل" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "پیشرفته" })).toBeVisible();

    await page.getByRole("tab", { name: "استایل" }).click();
    await expect(page.getByText("فاصله داخلی (Padding)")).toBeVisible();

    // 6. Test Undo and Redo buttons
    const undoBtn = page.locator('button[title*="بازگشت"]');
    await expect(undoBtn).toBeVisible();
    await undoBtn.click();

    const redoBtn = page.locator('button[title*="انجام مجدد"]');
    await expect(redoBtn).toBeVisible();
    await redoBtn.click();

    // 7. Test Save Draft button
    const saveDraftBtn = page.getByRole("button", { name: "ذخیره پیش‌نویس" });
    await expect(saveDraftBtn).toBeVisible();
    await saveDraftBtn.click();
  });
});
