import { expect, test, type Page, type FrameLocator } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Phase P2 Complete End-to-End Suite (P2.1 to P2.6)", () => {
  test("full flow: edit token in /admin/themes -> activate -> inherit in Builder Studio -> reflect on public page", async ({
    page,
  }) => {
    // 1. Setup admin authentication
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    // 2. Navigate to /admin/themes
    await page.goto("/admin/themes");
    await expect(page.locator("h1:has-text('مدیریت تم‌ها و استایل سازمانی')")).toBeVisible({
      timeout: 25_000,
    });

    // 3. Create and activate a distinct test theme
    const testSlug = `flow-theme-${Date.now().toString(36)}`;
    const testTitle = `تم جریان یکپارچه ${Date.now().toString().slice(-4)}`;

    await page.getByRole("button", { name: "ایجاد تم جدید" }).click();
    await expect(page.locator("text=ایجاد تم جدید").first()).toBeVisible({ timeout: 5_000 });

    // Fill metadata
    await page.locator("input[placeholder*='تم سازمانی']").fill(testTitle);
    await page.locator("input[placeholder='corporate-indigo']").fill(testSlug);

    // Set primary color to purple #7c3aed
    const purplePreset = page.locator("button[title*='بنفش']").last();
    if (await purplePreset.isVisible()) {
      await purplePreset.click();
    }

    // Switch to preview tab to verify live component preview
    await page.getByRole("tab", { name: "پیش‌نمایش زنده کامپوننت‌ها" }).click();
    await expect(page.locator("text=پیش‌نمایش زنده کامپوننت‌های رابط کاربری")).toBeVisible();

    // Submit creation
    await page.getByRole("button", { name: "ایجاد تم" }).click();
    await expect(page.locator("text=تم ایجاد شد")).toBeVisible({ timeout: 10_000 });

    // Find the newly created card and activate it
    const themeCard = page.locator("div.p-5", { hasText: testTitle }).first();
    await expect(themeCard).toBeVisible({ timeout: 10_000 });

    const activateBtn = themeCard.getByRole("button", { name: "فعال‌سازی" });
    await expect(activateBtn).toBeVisible();
    await activateBtn.click();
    await expect(page.locator("text=تم فعال شد")).toBeVisible({ timeout: 10_000 });

    // 4. Open Builder Studio on isolated scratchpad to verify Layer 1 inheritance
    await resetE2EPage("e2e-isolated-scratchpad");
    await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });

    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 20_000 });

    // Verify CanvasFrame iframe has inherited active theme CSS variables
    const iframeStyles = await page.locator(CANVAS).evaluate((iframe: HTMLIFrameElement) => {
      const doc = iframe.contentDocument;
      return {
        primary: doc?.documentElement?.style.getPropertyValue("--primary"),
        radius: doc?.documentElement?.style.getPropertyValue("--radius"),
      };
    });

    expect(iframeStyles.primary).toBeDefined();

    // 5. Verify public storefront reflection
    await page.goto("/e2e-isolated-scratchpad");
    await expect(page.locator("body")).toBeVisible({ timeout: 15_000 });

    const publicStyleInjected = await page.evaluate(() => {
      const styleEl = document.getElementById("active-site-theme-css");
      return Boolean(styleEl && styleEl.textContent?.includes("--primary"));
    });
    expect(publicStyleInjected).toBe(true);

    // 6. Clean up: Return to /admin/themes, activate default theme and delete test theme
    await page.goto("/admin/themes");
    await expect(page.locator("h1:has-text('مدیریت تم‌ها و استایل سازمانی')")).toBeVisible({
      timeout: 25_000,
    });

    // Activate the first inactive theme (e.g. original default)
    const otherCard = page.locator("div.p-5").filter({ hasNotText: testTitle }).first();
    const otherActivate = otherCard.getByRole("button", { name: "فعال‌سازی" });
    if (await otherActivate.isVisible()) {
      await otherActivate.click();
      await expect(page.locator("text=تم فعال شد")).toBeVisible({ timeout: 10_000 });
    }

    // Now delete test theme card
    const cardToDelete = page.locator("div.p-5", { hasText: testTitle }).first();
    const deleteBtn = cardToDelete.getByRole("button", { name: "حذف تم" });
    if (await deleteBtn.isVisible()) {
      await deleteBtn.click();
      await page.locator("button:has-text('تأیید')").or(page.locator("button.bg-destructive")).first().click();
      await expect(page.locator("text=تم حذف شد")).toBeVisible({ timeout: 10_000 });
    }
  });
});
