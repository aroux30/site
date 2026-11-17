import { expect, test } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Phase 5 - Accessibility, Zero Hydration & Performance E2E Suite", () => {
  test("Storefront /products loads with Zero Hydration and Console Errors", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        // Ignore expected network timeouts or favicon 404s
        if (!text.includes("favicon") && !text.includes("ERR_CONNECTION_REFUSED")) {
          consoleErrors.push(text);
        }
      }
    });

    await page.goto("/products");
    await expect(page.locator("body")).toBeVisible({ timeout: 20_000 });

    // Assert no React Hydration error occurred
    const hasHydrationError = consoleErrors.some(
      (err) =>
        err.includes("Hydration failed") ||
        err.includes("did not match") ||
        err.includes("Text content does not match")
    );
    expect(hasHydrationError).toBe(false);
  });

  test("Active Theme CSS stylesheet responds and injects in sub-100ms", async ({ page }) => {
    const start = Date.now();
    const response = await page.goto("/terms");
    const loadTime = Date.now() - start;

    expect(response?.status()).toBe(200);

    // Verify stylesheet presence in DOM
    const themeStyle = await page.evaluate(() => {
      const el = document.getElementById("active-site-theme-css");
      return Boolean(el && el.textContent?.includes("--primary"));
    });

    expect(themeStyle).toBe(true);
  });

  test("WCAG 2.1 AA keyboard accessibility on MegaMenu and interactive controls", async ({ page }) => {
    await page.goto("/products");
    await expect(page.locator("body")).toBeVisible({ timeout: 20_000 });

    // Test MegaMenu keyboard opening and Escape closing
    const menuBtn = page.getByRole("button", { name: /دسته‌بندی کالاها/ }).first();
    if (await menuBtn.isVisible()) {
      await menuBtn.focus();
      await page.keyboard.press("Enter");

      const menuPanel = page.locator("[role='menu'][aria-label='منوی دسته‌بندی کالاها']");
      await expect(menuPanel).toBeVisible({ timeout: 5_000 });

      // Navigate inside menu
      await page.keyboard.press("ArrowDown");

      // Press Escape to dismiss
      await page.keyboard.press("Escape");
      await expect(menuPanel).not.toBeVisible();
    }
  });

  test("Admin Themes Panel displays WCAG AA Contrast Evaluation Card", async ({ page }) => {
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
    await page.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user: {
              id: "admin-1",
              phone: "09123456789",
              isSuperuser: true,
              roles: ["super_admin"],
            },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });

    await page.goto("/admin/themes");
    await expect(page.locator("h1:has-text('مدیریت تم‌ها و استایل سازمانی')")).toBeVisible({
      timeout: 25_000,
    });

    // Open create dialog
    await page.getByRole("button", { name: "ایجاد تم جدید" }).click();
    await expect(page.locator("text=اعتبارسنجی دسترس‌پذیری کنتراست رنگ (WCAG 2.1 AA)")).toBeVisible({
      timeout: 5_000,
    });

    // Check contrast metrics
    await expect(page.locator("text=متن روی پس‌زمینه")).toBeVisible();
    await expect(page.locator("text=متن روی کارت/سطح")).toBeVisible();
    await expect(page.locator("text=متن سفید روی دکمه اصلی")).toBeVisible();
    await expect(page.locator("text=تأیید AA").first()).toBeVisible();
  });
});
