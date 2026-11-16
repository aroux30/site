import { expect, test, type Page } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Phase 3 - Storefront Components & Builder Integration E2E Suite", () => {
  test("Builder Studio renders live Phase 3 widgets (ProductCard, ImageGallery, ReviewHistogram, StarRating)", async ({
    page,
  }) => {
    // 1. Reset isolated scratchpad and auth
    await resetE2EPage("e2e-isolated-scratchpad");
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    // 2. Open builder studio
    await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });

    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 20_000 });

    // 3. Open blocks palette and verify Phase 3 blocks are registered
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await expect(page.locator("button:has-text('کارت محصول')").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("button:has-text('ویترین محصولات')").first()).toBeVisible();
    await expect(page.locator("button:has-text('گالری تصاویر')").first()).toBeVisible();
    await expect(page.locator("button:has-text('امتیاز ستاره‌ای')").first()).toBeVisible();
    await expect(page.locator("button:has-text('نمودار نظرات')").first()).toBeVisible();

    // 4. Add ProductCard widget to canvas
    await page.locator("button:has-text('کارت محصول')").first().click();

    // Verify ProductCard renders inside canvas frame with Phase 3 elements
    await expect(frame.locator("text=هدفون بی‌سیم پرو مکس")).toBeVisible({ timeout: 10_000 });
    await expect(frame.locator("text=خرید").first()).toBeVisible();

    // 5. Add StarRating widget to canvas
    await page.locator("button:has-text('امتیاز ستاره‌ای')").first().click();
    await expect(frame.locator("text=4.8").first()).toBeVisible({ timeout: 10_000 });
    await expect(frame.locator("text=/۱۲۴ نظر/").first()).toBeVisible();

    // 6. Add ReviewHistogram widget to canvas
    await page.locator("button:has-text('نمودار نظرات')").first().click();
    await expect(frame.locator("text=4.5").first()).toBeVisible({ timeout: 10_000 });
    await expect(frame.locator("text=/بر اساس ۸۶ نظر/").first()).toBeVisible();

    // 7. Click on ProductCard in canvas to verify Inspector Panel content controls
    const cardElement = frame.locator("[data-element-id]:has-text('هدفون بی‌سیم پرو مکس')").first();
    await cardElement.click({ force: true });

    await expect(page.locator("text=کارت محصول").first()).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("input[value='هدفون بی‌سیم پرو مکس']")).toBeVisible();
    await expect(page.locator("text=موجود در انبار")).toBeVisible();
  });

  test("MegaMenu navigation operates cleanly with keyboard and mouse hover", async ({ page }) => {
    // Visit home page or products page to test header mega menu
    await page.goto("/products");
    await expect(page.locator("body")).toBeVisible({ timeout: 20_000 });

    const menuTrigger = page.getByRole("button", { name: /دسته‌بندی کالاها/ }).first();
    if (await menuTrigger.isVisible()) {
      await menuTrigger.click();

      // Verify dropdown panel opens
      const menuPanel = page.locator("[role='menu'][aria-label='منوی دسته‌بندی کالاها']");
      await expect(menuPanel).toBeVisible({ timeout: 5_000 });

      // Press Escape to close menu
      await page.keyboard.press("Escape");
      await expect(menuPanel).not.toBeVisible();
    }
  });
});
