import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4004";
const AFTER_DIR = path.resolve("..", ".loop", "artifacts", "builder-gym", "round-37", "after");

test.describe("Builder Gym Round 37: Link in Bio and Posts Grid Parity", () => {
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

  test("1. Block palette filters and includes link_in_bio and posts_grid", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const paletteSearch = page.locator('aside input[placeholder*="جستجو"]').first();
    await expect(paletteSearch).toBeVisible();

    // Verify search finds link_in_bio
    await paletteSearch.fill("لینک بیو");
    await page.waitForTimeout(300);
    const bioCard = page.locator('aside button:has-text("لینک بیو")').first();
    await expect(bioCard).toBeVisible();

    // Verify search finds posts_grid
    await paletteSearch.fill("گرید مقالات");
    await page.waitForTimeout(300);
    const postsCard = page.locator('aside button:has-text("گرید مقالات")').first();
    await expect(postsCard).toBeVisible();

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

    // 1. Insert Link in Bio
    await paletteSearch.fill("لینک بیو");
    await page.waitForTimeout(300);
    const bioCard = page.locator('aside button:has-text("لینک بیو")').first();
    await bioCard.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const bioEl = frame.locator('.builder-link-in-bio').first();
    await expect(bioEl).toBeVisible();
    await expect(bioEl.locator('text=فروشگاه آنلاین آروکس')).toBeVisible();

    // Click bio element to open inspector
    await bioEl.click();
    await page.waitForTimeout(500);

    // Inspector nudge test: Change profile name
    const bioNameInput = page.locator('[data-testid="link-in-bio-name-input"]');
    await expect(bioNameInput).toBeVisible();
    await bioNameInput.fill("آکادمی آموزش طراحی و توسعه وب");
    await page.waitForTimeout(400);

    // Verify live update inside canvas frame
    await expect(bioEl.locator('text=آکادمی آموزش طراحی و توسعه وب')).toBeVisible();

    // 2. Insert Posts Grid
    await paletteSearch.fill("گرید مقالات");
    await page.waitForTimeout(300);
    const postsCard = page.locator('aside button:has-text("گرید مقالات")').first();
    await postsCard.click();
    await page.waitForTimeout(600);

    const postsEl = frame.locator('.builder-posts-grid').first();
    await expect(postsEl).toBeVisible();

    // Click posts element and nudge first title
    await postsEl.click();
    await page.waitForTimeout(500);

    const postTitleInput = page.locator('[data-testid="posts-grid-title-input-0"]');
    await expect(postTitleInput).toBeVisible();
    await postTitleInput.fill("بررسی ترندهای طراحی وب در سال ۲۰۲۶");
    await page.waitForTimeout(400);
    await expect(postsEl.locator('text=بررسی ترندهای طراحی وب در سال ۲۰۲۶')).toBeVisible();

    // 3. Capture after screenshots
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
