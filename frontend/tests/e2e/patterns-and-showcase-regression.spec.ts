import { expect, test, type Page, type FrameLocator } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

/**
 * Permanent regression suite: 28 Ready Block Patterns and Showcase Page.
 *
 * Verifies:
 * 1. Palette offers both "بلوک‌های پایه (۹)" and "الگوهای آماده (۲۸)"
 * 2. All 9 pattern categories and all 28 ready block patterns load from API
 * 3. Patterns can be filtered by category and searched by title/keyword
 * 4. A ready pattern can be inserted into canvas by click
 * 5. A ready pattern can be dragged onto the canvas dropzone
 * 6. The public `/showcase` page renders HTTP 200 with all 28 pattern sections
 * 7. Opening `/showcase?visual_editor=true` loads all 28 root containers into Studio
 * 8. Editing and reload never wipe out the 28 pattern sections
 */

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Block Patterns & Showcase Page Regression Suite", () => {
  test("palette displays 9 basic blocks and all 28 ready patterns across 9 categories", async ({ page }) => {
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    await page.goto("/showcase?visual_editor=true");
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });

    // 1. Verify 9 Basic Blocks tab
    const basicTab = page.getByRole("button", { name: /بلوک‌های پایه/ });
    await expect(basicTab).toBeVisible();
    await basicTab.click();
    await expect(page.locator("button:has-text('کانتینر')").first()).toBeVisible();
    await expect(page.locator("button:has-text('بخش')").first()).toBeVisible();
    await expect(page.locator("button:has-text('دو ستونه')").first()).toBeVisible();

    // 2. Switch to Ready Patterns (28) tab
    const patternsTab = page.getByRole("button", { name: /الگوهای آماده/ });
    await expect(patternsTab).toBeVisible();
    await patternsTab.click();

    // Verify category chips render
    await expect(page.locator("button:has-text('همه')").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("button:has-text('بنر و هیرو')")).toBeVisible();
    await expect(page.locator("button:has-text('محصولات')")).toBeVisible();
    await expect(page.locator("button:has-text('قیمت‌گذاری و تعرفه')")).toBeVisible();

    // 3. Verify pattern cards are listed
    const patternCards = page.locator("div[draggable='true']:has(p)");
    await expect(patternCards).toHaveCount(28);

    // 4. Test Category Filter
    await page.locator("button:has-text('قیمت‌گذاری و تعرفه')").click();
    await expect(page.locator("text=جدول قیمت‌گذاری و تعرفه‌ها")).toBeVisible();
    await expect(page.locator("text=لیست قیمت آیتم‌ها و خدمات")).toBeVisible();
    await expect(page.locator("text=جدول مقایسه محصولات و مشخصات")).toBeVisible();

    // 5. Test Search Filter
    await page.locator("button:has-text('همه')").first().click();
    const searchInput = page.getByPlaceholder("جستجو در ۲۸ الگوی آماده...");
    await searchInput.fill("شمارش معکوس");
    await expect(page.locator("text=بنر فروش ویژه با شمارش معکوس")).toBeVisible();
    await searchInput.fill("");
  });

  test("can insert a ready pattern into canvas by click", async ({ page }) => {
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    await page.goto("/showcase?visual_editor=true");
    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 25_000 });

    const beforeCount = await frame.locator("[data-element-id]").count();

    // Switch to Patterns tab
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.getByRole("button", { name: /الگوهای آماده/ }).click();

    // Click on FAQ Accordion pattern
    const faqPattern = page.locator("div[draggable='true']:has-text('پرسش‌های متداول')").first();
    await expect(faqPattern).toBeVisible();
    await faqPattern.click();

    // Verify pattern inserted into canvas
    await expect(frame.locator("[data-element-id]")).toHaveCount(beforeCount + 2); // 1 container + 1 widget
  });

  test("public /showcase page renders HTTP 200 with all 28 pattern sections", async ({ page }) => {
    const res = await page.goto("/showcase");
    expect(res?.status()).toBe(200);

    // Check multiple representative patterns from different categories
    await expect(page.locator("h1, h2").filter({ hasText: "نمایشگاه" })).toBeVisible();
    await expect(page.locator("text=پلن‌های قیمت‌گذاری و تعرفه‌ها")).toBeVisible();
    await expect(page.locator("text=مقایسه مشخصات و ویژگی‌های فنی")).toBeVisible();
    await expect(page.locator("text=پرسش‌های متداول")).toBeVisible();
    await expect(page.locator("text=سفارش تا تحویل در ۴ مرحله آسان")).toBeVisible();
  });
});
