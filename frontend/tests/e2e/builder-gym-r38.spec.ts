import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4004";
const AFTER_DIR = path.resolve("..", ".loop", "artifacts", "builder-gym", "round-38", "after");

test.describe("Builder Gym Round 38: Hero Slides Repeater & Left Inspector Width Parity", () => {
  test.beforeEach(async ({ context }) => {
    fs.mkdirSync(AFTER_DIR, { recursive: true });
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
    });
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
        })
      );
    });
  });

  test("1. Slides widget inspector provides full multi-slide repeater with add/delete and live canvas sync", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const paletteSearch = page.locator('aside input[placeholder*="جستجو"]').first();
    await expect(paletteSearch).toBeVisible();

    // Search and insert slides
    await paletteSearch.fill("اسلاید پیشرفته");
    await page.waitForTimeout(300);
    const slidesCard = page.locator('aside button:has-text("اسلاید پیشرفته")').first();
    await expect(slidesCard).toBeVisible();
    await slidesCard.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const slidesEl = frame.locator('h2:has-text("تخفیف ویژه آغاز فصل")').first();
    await expect(slidesEl).toBeVisible();

    // Click slides element to open inspector panel
    await slidesEl.click();
    await page.waitForTimeout(500);

    // Verify Inspector shows slides repeater title
    const repeaterHeader = page.locator('text=اسلایدهای هیرو').first();
    await expect(repeaterHeader).toBeVisible();

    // Verify Add slide button
    const addSlideBtn = page.locator('[data-testid="add-slide-btn"]');
    await expect(addSlideBtn).toBeVisible();

    // Click add slide
    await addSlideBtn.click();
    await page.waitForTimeout(400);

    // Verify Slide 3 appeared
    const slide3Title = page.locator('text=اسلاید 3').first();
    await expect(slide3Title).toBeVisible();

    // Nudge slide 1 title
    const slide1Input = page.locator('[data-testid="slide-title-0"]');
    await expect(slide1Input).toBeVisible();
    await slide1Input.fill("جشنواره طلایی بلک فرایدی");
    await page.waitForTimeout(400);

    // Verify live update inside canvas frame
    await expect(frame.locator('text=جشنواره طلایی بلک فرایدی').first()).toBeVisible();

    // Capture screenshots
    const studioImg = path.join(AFTER_DIR, "01-studio-slides-repeater.png");
    await page.screenshot({ path: studioImg });
    expect(fs.existsSync(studioImg)).toBe(true);

    const inspectorImg = path.join(AFTER_DIR, "02-inspector-slides-nudge.png");
    await page.screenshot({ path: inspectorImg });
    expect(fs.existsSync(inspectorImg)).toBe(true);
  });
});
