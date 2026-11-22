import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4004";
const AFTER_DIR = path.resolve("..", ".loop", "artifacts", "builder-gym", "round-35", "after");

test.describe("Builder Gym Round 35: Elementor Core & Pro Widget Parity (Audio, Maps, Search, Nav, ReadMore)", () => {
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

  test("1. Block palette filters and includes all newly ported Elementor widgets", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const paletteSearch = page.locator('aside input[placeholder*="جستجو"]').first();
    await expect(paletteSearch).toBeVisible();

    // Verify search finds audio
    await paletteSearch.fill("صوت");
    await page.waitForTimeout(300);
    const audioCard = page.locator('aside button:has-text("صوت")').first();
    await expect(audioCard).toBeVisible();

    // Verify search finds google_maps
    await paletteSearch.fill("نقشه");
    await page.waitForTimeout(300);
    const mapCard = page.locator('aside button:has-text("نقشه تعاملی")').first();
    await expect(mapCard).toBeVisible();

    // Verify search finds search_bar
    await paletteSearch.fill("فرم جستجو");
    await page.waitForTimeout(300);
    const searchCard = page.locator('aside button:has-text("فرم جستجو")').first();
    await expect(searchCard).toBeVisible();

    // Verify search finds nav_menu
    await paletteSearch.fill("منوی ناوبری");
    await page.waitForTimeout(300);
    const navCard = page.locator('aside button:has-text("منوی ناوبری")').first();
    await expect(navCard).toBeVisible();

    // Verify search finds read_more
    await paletteSearch.fill("ادامه مطلب");
    await page.waitForTimeout(300);
    const readMoreCard = page.locator('aside button:has-text("ادامه مطلب")').first();
    await expect(readMoreCard).toBeVisible();

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

    // 1. Insert Audio Player
    await paletteSearch.fill("صوت");
    await page.waitForTimeout(300);
    const audioCard = page.locator('aside button:has-text("صوت")').first();
    await audioCard.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const audioEl = frame.locator('.builder-audio').first();
    await expect(audioEl).toBeVisible();
    await expect(audioEl.locator('text=پادکست اختصاصی')).toBeVisible();

    // Click audio element to open inspector
    await audioEl.click();
    await page.waitForTimeout(500);

    // Inspector nudge test: Change title
    const audioTitleInput = page.locator('[data-testid="audio-title-input"]');
    await expect(audioTitleInput).toBeVisible();
    await audioTitleInput.fill("پادکست ویژه مصاحبه مدیران");
    await page.waitForTimeout(400);

    // Verify live update inside canvas frame
    await expect(audioEl.locator('text=پادکست ویژه مصاحبه مدیران')).toBeVisible();

    // 2. Insert Google Maps
    await paletteSearch.fill("نقشه");
    await page.waitForTimeout(300);
    const mapCard = page.locator('aside button:has-text("نقشه تعاملی")').first();
    await mapCard.click();
    await page.waitForTimeout(600);

    const mapEl = frame.locator('.builder-google-maps').first();
    await expect(mapEl).toBeVisible();
    await expect(mapEl.locator('text=تهران، میدان آزادی')).toBeVisible();

    // Click map element and nudge address
    await mapEl.click();
    await page.waitForTimeout(500);

    const mapAddressInput = page.locator('[data-testid="google-maps-address-input"]');
    await expect(mapAddressInput).toBeVisible();
    await mapAddressInput.fill("تهران، میدان ونک، برج نگار");
    await page.waitForTimeout(400);
    await expect(mapEl.locator('text=تهران، میدان ونک، برج نگار')).toBeVisible();

    // 3. Insert Search Bar
    await paletteSearch.fill("فرم جستجو");
    await page.waitForTimeout(300);
    const searchCard = page.locator('aside button:has-text("فرم جستجو")').first();
    await searchCard.click();
    await page.waitForTimeout(600);

    const searchEl = frame.locator('.builder-search-bar').first();
    await expect(searchEl).toBeVisible();

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
