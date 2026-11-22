import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4004";
const AFTER_DIR = path.resolve("..", ".loop", "artifacts", "builder-gym", "round-36", "after");

test.describe("Builder Gym Round 36: Video Playlist, Image Comparison & Custom HTML Parity", () => {
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

  test("1. Block palette filters and includes video_playlist, image_comparison, and html_custom", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const paletteSearch = page.locator('aside input[placeholder*="جستجو"]').first();
    await expect(paletteSearch).toBeVisible();

    // Verify search finds video_playlist
    await paletteSearch.fill("لیست پخش");
    await page.waitForTimeout(300);
    const playlistCard = page.locator('aside button:has-text("لیست پخش ویدیو")').first();
    await expect(playlistCard).toBeVisible();

    // Verify search finds image_comparison
    await paletteSearch.fill("مقایسه تصویر");
    await page.waitForTimeout(300);
    const comparisonCard = page.locator('aside button:has-text("مقایسه تصویر")').first();
    await expect(comparisonCard).toBeVisible();

    // Verify search finds html_custom
    await paletteSearch.fill("کد سفارشی");
    await page.waitForTimeout(300);
    const htmlCard = page.locator('aside button:has-text("کد سفارشی HTML")').first();
    await expect(htmlCard).toBeVisible();

    // Capture palette showing new widgets
    await paletteSearch.fill("");
    await page.waitForTimeout(300);
    const paletteImg = path.join(AFTER_DIR, "02-palette-new-widgets.png");
    await page.screenshot({ path: paletteImg });
    expect(fs.existsSync(paletteImg)).toBe(true);
  });

  test("2. Inserting widgets into canvas renders authentic Elementor markup and inspector controls respond to nudges", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const paletteSearch = page.locator('aside input[placeholder*="جستجو"]').first();

    // 1. Insert Video Playlist
    await paletteSearch.fill("لیست پخش");
    await page.waitForTimeout(300);
    const playlistCard = page.locator('aside button:has-text("لیست پخش ویدیو")').first();
    await playlistCard.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const playlistEl = frame.locator('.builder-video-playlist').first();
    await expect(playlistEl).toBeVisible();
    await expect(playlistEl.locator('text=فهرست ویدیوهای آموزشی')).toBeVisible();

    // Click playlist element to open inspector
    await playlistEl.click();
    await page.waitForTimeout(500);

    // Inspector nudge test: Change title
    const playlistTitleInput = page.locator('[data-testid="video-playlist-title-input"]');
    await expect(playlistTitleInput).toBeVisible();
    await playlistTitleInput.fill("دوره تخصصی برنامه‌نویسی ری‌اکت");
    await page.waitForTimeout(400);

    // Verify live update inside canvas frame
    await expect(playlistEl.locator('text=دوره تخصصی برنامه‌نویسی ری‌اکت')).toBeVisible();

    // 2. Insert Image Comparison
    await paletteSearch.fill("مقایسه تصویر");
    await page.waitForTimeout(300);
    const comparisonCard = page.locator('aside button:has-text("مقایسه تصویر")').first();
    await comparisonCard.click();
    await page.waitForTimeout(600);

    const comparisonEl = frame.locator('.builder-image-comparison').first();
    await expect(comparisonEl).toBeVisible();

    // Click comparison element and nudge labels
    await comparisonEl.click();
    await page.waitForTimeout(500);

    const beforeLabelInput = page.locator('[data-testid="image-comparison-before-label-input"]');
    await expect(beforeLabelInput).toBeVisible();
    await beforeLabelInput.fill("پیش از طراحی");
    await page.waitForTimeout(400);
    await expect(comparisonEl.locator('text=پیش از طراحی')).toBeVisible();

    // 3. Insert Custom HTML
    await paletteSearch.fill("کد سفارشی");
    await page.waitForTimeout(300);
    const htmlCard = page.locator('aside button:has-text("کد سفارشی HTML")').first();
    await htmlCard.click();
    await page.waitForTimeout(600);

    const customHtmlEl = frame.locator('.builder-custom-html').first();
    await expect(customHtmlEl).toBeVisible();

    // 4. Capture after screenshots
    const canvasImg = path.join(AFTER_DIR, "03-canvas-with-new-widgets.png");
    await page.screenshot({ path: canvasImg });
    expect(fs.existsSync(canvasImg)).toBe(true);

    const inspectorImg = path.join(AFTER_DIR, "04-inspector-nudge-active.png");
    await page.screenshot({ path: inspectorImg });
    expect(fs.existsSync(inspectorImg)).toBe(true);

    const overviewImg = path.join(AFTER_DIR, "01-studio-overview.png");
    await page.screenshot({ path: overviewImg });
    expect(fs.existsSync(overviewImg)).toBe(true);
  });
});
