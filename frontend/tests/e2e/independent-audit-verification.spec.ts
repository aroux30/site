import { expect, test, type Page, type FrameLocator } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";
import fs from "node:fs";
import path from "node:path";

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const SCREENSHOTS_DIR = path.resolve(__dirname, "../../test-results/audit-screenshots");

async function openIsolatedStudio(page: Page): Promise<FrameLocator> {
  await resetE2EPage("e2e-isolated-scratchpad");
  const token = await createAccessTokenForE2E();
  await page.context().addCookies([
    { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
  ]);
  await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
  await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });
  const frame = page.frameLocator(CANVAS);
  await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 20_000 });
  return frame;
}

test.beforeAll(() => {
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }
});

test.describe("Independent Audit & Browser Verification Suite", () => {
  test("Scenario 1-3: Drag & Drop basic block and verify no forbidden cursor", async ({ page }) => {
    const frame = await openIsolatedStudio(page);
    const beforeCount = await frame.locator("[data-element-id]").count();

    // Verify draggable attributes on basic block
    const headingBtn = page.locator("button:has-text('سرتیتر')").first();
    await expect(headingBtn).toBeVisible();
    await expect(headingBtn).toHaveAttribute("draggable", "true");

    // Perform drag simulation with effectAllowed="all"
    await headingBtn.evaluate((el) => {
      const dt = new DataTransfer();
      dt.setData("application/json", JSON.stringify({ type: "block_def", blockType: "heading" }));
      dt.effectAllowed = "all";
      el.dispatchEvent(new DragEvent("dragstart", { bubbles: true, dataTransfer: dt }));
    });

    // Check dragover on workspace main and canvas root
    const dropAccepted = await frame.locator('[data-testid="builder-canvas-root"]').evaluate((el) => {
      const dt = new DataTransfer();
      dt.setData("application/json", JSON.stringify({ type: "block_def", blockType: "heading" }));
      dt.effectAllowed = "all";
      const dragOverEvent = new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt });
      el.dispatchEvent(dragOverEvent);
      el.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
      return dragOverEvent.defaultPrevented;
    });

    expect(dropAccepted).toBe(true);
    await expect(frame.locator("[data-element-id]")).toHaveCount(beforeCount + 1);
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "01-basic-block-dnd.png") });
  });

  test("Scenario 2, 4: Insert and Drag block patterns into canvas", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // Open patterns tab
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.getByRole("button", { name: /الگوهای آماده/ }).click();

    // 1. Click to insert hero-banner
    const heroCard = page.locator("div[draggable='true']:has-text('بنر اصلی (هیرو)')").first();
    await expect(heroCard).toBeVisible();
    await heroCard.click();
    await expect(page.locator("text=الگو افزوده شد")).toBeVisible({ timeout: 10_000 });
    await expect(frame.locator("h1:has-text('کالکشن جدید رسید')")).toBeVisible();

    // 2. Drag & drop feature-grid pattern
    const featureCard = page.locator("div[draggable='true']:has-text('شبکه ویژگی‌ها')").first();
    await expect(featureCard).toBeVisible();
    await featureCard.evaluate((el) => {
      const dt = new DataTransfer();
      dt.setData("application/json", JSON.stringify({
        type: "pattern_def",
        patternSlug: "feature-grid",
        title: "شبکه ویژگی‌ها",
        category: "محتوا",
      }));
      dt.effectAllowed = "all";
      el.dispatchEvent(new DragEvent("dragstart", { bubbles: true, dataTransfer: dt }));
    });

    await frame.locator('[data-testid="builder-canvas-root"]').evaluate((el) => {
      const dt = new DataTransfer();
      dt.setData("application/json", JSON.stringify({
        type: "pattern_def",
        patternSlug: "feature-grid",
        title: "شبکه ویژگی‌ها",
        category: "محتوا",
      }));
      dt.effectAllowed = "all";
      el.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt }));
      el.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
    });

    await expect(frame.locator("h2:has-text('چرا از ما بخرید؟')")).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "02-patterns-inserted.png") });
  });

  test("Scenario 5-8: Select & edit Heading, Button, Image in Inspector", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // Insert hero pattern
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.getByRole("button", { name: /الگوهای آماده/ }).click();
    await page.locator("div[draggable='true']:has-text('بنر اصلی (هیرو)')").first().click();
    await expect(frame.locator("h1:has-text('کالکشن جدید رسید')")).toBeVisible({ timeout: 10_000 });

    // 1. Select Heading & edit text
    const headingNode = frame.locator("[data-element-id]:has(h1)").last();
    await headingNode.click();
    await expect(page.locator("text=متن عنوان")).toBeVisible();
    const headingInput = page.locator("input[value*='کالکشن']");
    await headingInput.fill("تخفیف شگفت‌انگیز پاییزه");
    await expect(frame.locator("h1:has-text('تخفیف شگفت‌انگیز پاییزه')")).toBeVisible();

    // 2. Select Button & edit label & URL
    const btnNode = frame.locator("[data-element-id]:has-text('همین حالا بخرید')").last();
    await btnNode.click();
    await expect(page.locator("text=متن دکمه")).toBeVisible();
    const btnLabelInput = page.locator("input[value*='همین حالا']");
    await btnLabelInput.fill("مشاهده همه محصولات");
    const btnUrlInput = page.locator("input[placeholder='https://...']");
    await btnUrlInput.fill("/products/special");
    await expect(frame.locator("text=مشاهده همه محصولات")).toBeVisible();

    // 3. Select Image & edit URL and Alt
    const imgNode = frame.locator("[data-element-id]:has(img)").last();
    await imgNode.click();
    await expect(page.locator("text=آدرس تصویر (URL)")).toBeVisible();
    const imgAltInput = page.locator("input[value*='کالکشن']");
    await imgAltInput.fill("تصویر جدید کمپین");

    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "03-inspector-editing.png") });
  });

  test("Scenario 9-12: Container layout, element reorder, duplicate, delete, undo/redo", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // Select container via Layers tree tab
    await page.getByRole("button", { name: "لایه‌ها" }).click();
    await page.locator("text=کانتینر اصلی").first().click();
    await expect(page.locator("text=نوع چیدمان کانتینر")).toBeVisible();

    // Switch back to canvas for duplicate/delete operations
    const initialCount = await frame.locator("[data-element-id]").count();
    const targetElement = frame.locator("[data-element-id]").nth(1);
    await targetElement.click();
    await frame.locator("[title='تکثیر (Duplicate)']").first().click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(initialCount + 1);

    // Delete an element
    await frame.locator("[title='حذف']").first().click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(initialCount);

    // Test Undo
    const undoBtn = page.locator("[title*='بازگشت']");
    await undoBtn.click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(initialCount + 1);

    // Test Redo
    const redoBtn = page.locator("[title*='انجام مجدد']");
    await redoBtn.click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(initialCount);

    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "04-container-dnd-ops.png") });
  });

  test("Scenario 13-14: Responsive viewports & Preview mode without editor chrome", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // 1. Tablet viewport
    await page.getByRole("button", { name: /تبلت/ }).click();
    await expect(page.locator(".max-w-\\[768px\\]")).toBeVisible();

    // 2. Mobile viewport
    await page.getByRole("button", { name: /موبایل/ }).click();
    await expect(page.locator(".max-w-\\[375px\\]")).toBeVisible();

    // 3. Desktop viewport
    await page.getByRole("button", { name: "دسکتاپ" }).click();
    await expect(page.locator(".transition-all.duration-300.max-w-full")).toBeVisible();

    // 4. Preview mode
    const previewBtn = page.getByRole("button", { name: /پیش‌نمایش/ });
    await previewBtn.click();

    // Verify sidebars are hidden
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).not.toBeVisible();
    await expect(page.locator("text=عنصری انتخاب نشده است")).not.toBeVisible();

    // Verify content is visible
    await expect(frame.locator("h2:has-text('سرتیتر اول')")).toBeVisible();
    await expect(frame.locator("p:has-text('متن دوم')")).toBeVisible();
    await expect(frame.locator("text=html_custom")).toHaveCount(0);

    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "05-preview-mode.png") });

    // Exit preview mode
    await page.getByRole("button", { name: /ویرایش/ }).click();
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible();
  });

  test("Scenario 15-17: Save, reload, and verify persistence on e2e-isolated-scratchpad", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // Add a heading with unique text
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.locator("button:has-text('سرتیتر')").first().click();

    const newHeading = frame.locator("[data-element-id]:has(h2)").last();
    await newHeading.click();
    const headingInput = page.locator("input[value*='عنوان']");
    await headingInput.fill("متن تایید پایداری دیتابیس");

    // Click explicit save draft
    await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click();
    await expect(page.locator("text=پیش‌نویس ذخیره شد")).toBeVisible({ timeout: 10_000 });

    // Reload the page
    await page.reload();
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });
    const reloadedFrame = page.frameLocator(CANVAS);
    await expect(reloadedFrame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 20_000 });

    // Verify our saved heading persisted after reload
    await expect(reloadedFrame.locator("h2:has-text('متن تایید پایداری دیتابیس')")).toBeVisible();

    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "06-saved-persistence.png") });
  });

  test("Verification of 7 named patterns: hero, feature, products, pricing, comparison, testimonials, faq", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // Open patterns tab
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.getByRole("button", { name: /الگوهای آماده/ }).click();

    const patternsToTest = [
      { slug: "hero-banner", title: "بنر اصلی (هیرو)", expectedText: "کالکشن جدید رسید" },
      { slug: "feature-grid", title: "شبکه ویژگی‌ها", expectedText: "چرا از ما بخرید؟" },
      { slug: "product-card-grid", title: "شبکه کارت محصول", expectedText: "محصولات پرفروش" },
      { slug: "pricing-table", title: "جدول قیمت‌گذاری و تعرفه‌ها", expectedText: "پلن‌های قیمت‌گذاری" },
      { slug: "comparison-table", title: "جدول مقایسه محصولات و مشخصات", expectedText: "مقایسه مشخصات" },
      { slug: "testimonials", title: "نظرات مشتریان", expectedText: "مشتریان ما چه می‌گویند" },
      { slug: "faq-accordion", title: "پرسش‌های متداول", expectedText: "پرسش‌های متداول" },
    ];

    for (const p of patternsToTest) {
      const card = page.locator(`div[draggable='true']:has-text('${p.title}')`).first();
      await expect(card).toBeVisible();
      await card.click();
      await expect(page.locator("text=الگو افزوده شد").first()).toBeVisible({ timeout: 10_000 });
      await expect(frame.locator(`text=${p.expectedText}`).first()).toBeVisible({ timeout: 10_000 });
      // Close toast if present
      await page.keyboard.press("Escape");
    }

    // Verify no "ویجت html_custom" error boxes on the canvas for any of the 7 patterns
    await expect(frame.locator("text=ویجت html_custom")).toHaveCount(0);

    await page.screenshot({ path: path.join(SCREENSHOTS_DIR, "07-seven-patterns-verified.png") });
  });
});
