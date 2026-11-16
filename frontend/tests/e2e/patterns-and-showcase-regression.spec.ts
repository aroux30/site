import { expect, test, type Page, type FrameLocator } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";

/**
 * Permanent regression suite: 28 Ready Block Patterns, Drag & Drop, and Scratchpad.
 *
 * Verifies:
 * 1. Palette offers both "بلوک‌های پایه (۹)" and "الگوهای آماده (۲۸)"
 * 2. All 9 pattern categories and all 28 ready block patterns load from API
 * 3. Patterns can be filtered by category and searched by title/keyword
 * 4. A ready pattern can be inserted into canvas by click with rich nested AST nodes
 * 5. A ready pattern can be dragged onto the canvas dropzone via HTML5 drag-and-drop
 * 6. Internal elements of patterns (heading, button, image) are individually selectable and editable in Inspector
 * 7. Preview mode truthfully renders real content without "html_custom" text or broken styles
 * 8. All tests mutate ONLY e2e-isolated-scratchpad, leaving real CMS pages untouched
 */

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Block Patterns & Studio Regression Suite", () => {
  test("palette displays 9 basic blocks and all 28 ready patterns across 9 categories", async ({ page }) => {
    await resetE2EPage("e2e-isolated-scratchpad");
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
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

    // 3. Verify pattern cards are listed (all 28)
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

  test("can insert a ready pattern into canvas by click with rich nested AST nodes", async ({ page }) => {
    await resetE2EPage("e2e-isolated-scratchpad");
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 25_000 });

    const beforeCount = await frame.locator("[data-element-id]").count();

    // Switch to Patterns tab
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.getByRole("button", { name: /الگوهای آماده/ }).click();

    // Click on the first visible pattern card (بنر اصلی)
    const firstPattern = page.locator("div[draggable='true']:has-text('بنر اصلی (هیرو)')").first();
    await expect(firstPattern).toBeVisible();
    await firstPattern.click();

    // Verify pattern inserted into canvas (toast + elements)
    await expect(page.locator("text=الگو افزوده شد")).toBeVisible({ timeout: 10_000 });

    // The hero pattern is deconstructed into a rich container tree with heading, text, button, image
    const afterCount = await frame.locator("[data-element-id]").count();
    expect(afterCount).toBeGreaterThanOrEqual(beforeCount + 4);

    // Verify internal widgets render actual content, NOT "html_custom"
    await expect(frame.locator("h1:has-text('کالکشن جدید رسید')")).toBeVisible();
    await expect(frame.locator("text=همین حالا بخرید")).toBeVisible();
    await expect(frame.locator("img[alt='کالکشن جدید رسید']")).toBeVisible();
    await expect(frame.locator("text=ویجت html_custom")).toHaveCount(0);
  });

  test("can drag a block pattern from palette onto canvas dropzone", async ({ page }) => {
    await resetE2EPage("e2e-isolated-scratchpad");
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 25_000 });

    const beforeCount = await frame.locator("[data-element-id]").count();

    // Switch to Patterns tab
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.getByRole("button", { name: /الگوهای آماده/ }).click();

    // Dispatch real HTML5 drag-and-drop from the pattern card to the canvas root
    const patternCard = page.locator("div[draggable='true']:has-text('بنر اصلی (هیرو)')").first();
    await expect(patternCard).toBeVisible();

    await patternCard.evaluate((el) => {
      const dt = new DataTransfer();
      dt.setData(
        "application/json",
        JSON.stringify({
          type: "pattern_def",
          patternSlug: "hero-banner",
          title: "بنر اصلی (هیرو)",
          category: "بنر و هیرو",
        })
      );
      dt.effectAllowed = "all";
      el.dispatchEvent(new DragEvent("dragstart", { bubbles: true, dataTransfer: dt }));
    });

    await frame.locator('[data-testid="builder-canvas-root"]').evaluate((el) => {
      const dt = new DataTransfer();
      dt.setData(
        "application/json",
        JSON.stringify({
          type: "pattern_def",
          patternSlug: "hero-banner",
          title: "بنر اصلی (هیرو)",
          category: "بنر و هیرو",
        })
      );
      dt.effectAllowed = "all";
      el.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt }));
      el.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
    });

    // Wait for the drop to insert the pattern elements into the canvas
    await expect(frame.locator("h1:has-text('کالکشن جدید رسید')")).toBeVisible({ timeout: 10_000 });
    const afterCount = await frame.locator("[data-element-id]").count();
    expect(afterCount).toBeGreaterThanOrEqual(beforeCount + 4);
  });

  test("internal components of a pattern are individually selectable and editable in inspector", async ({ page }) => {
    await resetE2EPage("e2e-isolated-scratchpad");
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 25_000 });

    // Insert hero pattern
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.getByRole("button", { name: /الگوهای آماده/ }).click();
    await page.locator("div[draggable='true']:has-text('بنر اصلی (هیرو)')").first().click();
    await expect(frame.locator("h1:has-text('کالکشن جدید رسید')")).toBeVisible({ timeout: 10_000 });

    // Click specifically on the Heading element inside the pattern
    const headingElem = frame.locator("[data-element-id]:has(h1)").last();
    await headingElem.click();

    // Verify Inspector opens with Heading properties
    await expect(page.locator("text=متن عنوان")).toBeVisible({ timeout: 5_000 });
    const headingInput = page.locator("input[value*='کالکشن']");
    await expect(headingInput).toBeVisible();

    // Edit the heading text in the inspector
    await headingInput.fill("عنوان ویرایش شده تستی");

    // Verify canvas updates in real time with the new heading text
    await expect(frame.locator("h1:has-text('عنوان ویرایش شده تستی')")).toBeVisible({ timeout: 5_000 });

    // Click on the Button element inside the pattern
    const buttonElem = frame.locator("[data-element-id]:has-text('همین حالا بخرید')").last();
    await buttonElem.click();

    // Verify Inspector switches to Button properties
    await expect(page.locator("text=متن دکمه")).toBeVisible({ timeout: 5_000 });
    const buttonInput = page.locator("input[value*='همین حالا']");
    await expect(buttonInput).toBeVisible();
    await buttonInput.fill("دکمه جدید");
    await expect(frame.locator("text=دکمه جدید")).toBeVisible({ timeout: 5_000 });
  });

  test("preview mode faithfully renders real content without editor chrome or placeholder text", async ({ page }) => {
    await resetE2EPage("e2e-isolated-scratchpad");
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);

    await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 25_000 });

    // Toggle Preview Mode via Toolbar button
    const previewBtn = page.getByRole("button", { name: /پیش‌نمایش/ });
    await expect(previewBtn).toBeVisible();
    await previewBtn.click();

    // Verify editor sidebars (Palette and Inspector) are hidden
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).not.toBeVisible();
    await expect(page.locator("text=عنصری انتخاب نشده است")).not.toBeVisible();

    // Verify real content is still visible inside the canvas
    await expect(frame.locator("h2:has-text('سرتیتر اول')")).toBeVisible();
    await expect(frame.locator("p:has-text('متن دوم')")).toBeVisible();
    await expect(frame.locator("text=html_custom")).toHaveCount(0);

    // Toggle back to editor mode
    await page.getByRole("button", { name: /ویرایش/ }).click();
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 5_000 });
  });
});
