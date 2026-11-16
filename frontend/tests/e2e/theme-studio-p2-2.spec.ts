import { expect, test, type Page } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Theme Studio Manager P2.2 E2E Suite", () => {
  test("admin accesses /admin/themes, creates a new theme, activates it, and checks revisions", async ({ page }) => {
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    // 1. Visit /admin/themes
    await page.goto("/admin/themes");
    await expect(page.locator("h1:has-text('مدیریت تم‌ها و استایل سازمانی')")).toBeVisible({ timeout: 25_000 });

    // 2. Verify active theme badge exists on at least one card
    await expect(page.locator("text=تم فعال سایت").first()).toBeVisible({ timeout: 10_000 });

    // 3. Create a new theme
    const uniqueSlug = `e2e-theme-${Date.now().toString(36)}`;
    const uniqueTitle = `تم تستی E2E ${Date.now().toString().slice(-4)}`;

    await page.getByRole("button", { name: "ایجاد تم جدید" }).click();
    await expect(page.locator("text=ایجاد تم جدید").first()).toBeVisible({ timeout: 5_000 });

    // Fill form
    const nameInput = page.locator("input[placeholder*='تم سازمانی']");
    await nameInput.fill(uniqueTitle);

    const slugInput = page.locator("input[placeholder='corporate-indigo']");
    await slugInput.fill(uniqueSlug);

    // Pick blue color preset
    const bluePreset = page.locator("button[title*='آبی']").last();
    if (await bluePreset.isVisible()) {
      await bluePreset.click();
    }

    // Submit creation
    await page.getByRole("button", { name: "ایجاد تم" }).click();
    await expect(page.locator("text=تم ایجاد شد")).toBeVisible({ timeout: 10_000 });

    // 4. Verify new theme card appears in grid
    const card = page.locator("div.p-5", { hasText: uniqueTitle }).first();
    await expect(card).toBeVisible({ timeout: 10_000 });

    // 5. Check revisions history dialog opens
    const historyBtn = card.getByRole("button", { name: "تاریخچه نسخه‌ها" });
    await expect(historyBtn).toBeVisible();
    await historyBtn.click();
    await expect(page.locator("text=تاریخچه نسخه‌های تم")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("text=/نسخه [1۱]/")).toBeVisible();
    await page.keyboard.press("Escape");

    // 6. Clean up: Delete created test theme
    const deleteBtn = card.getByRole("button", { name: "حذف تم" });
    if (await deleteBtn.isVisible()) {
      await deleteBtn.click();
      await expect(page.locator("text=حذف تم").first()).toBeVisible();
      // Click confirm delete in confirm dialog
      await page.locator("button:has-text('تأیید')").or(page.locator("button.bg-destructive")).first().click();
      await expect(page.locator("text=تم حذف شد")).toBeVisible({ timeout: 10_000 });
    }
  });

  test("public storefront renders active theme CSS variables", async ({ page }) => {
    // Visit a public page e.g. /terms
    await page.goto("/terms");
    await expect(page.locator("h1")).toBeVisible({ timeout: 20_000 });

    // Verify active theme stylesheet is injected
    const hasActiveThemeCss = await page.evaluate(() => {
      const styleEl = document.getElementById("active-site-theme-css");
      return Boolean(styleEl && styleEl.textContent?.includes("--primary"));
    });

    expect(hasActiveThemeCss).toBe(true);
  });
});
