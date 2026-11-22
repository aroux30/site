import { test, expect } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1002";

test.describe("Builder Gym Round 22: Elementor Core/Pro Parity & TOC Inspector Synchronization", () => {
  test.beforeEach(async ({ context }) => {
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
    });
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });
  });

  test("1. Table of Contents widget can be added and live-nudge reflected in canvas and inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Click TOC in blocks palette
    const tocBtn = page.locator('button[data-block-type="table_of_contents"]').first();
    await tocBtn.scrollIntoViewIfNeeded();
    await tocBtn.click();
    await page.waitForTimeout(800);

    // Locate TOC in canvas iframe
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const tocElement = frame.locator('[data-widget-type="table_of_contents"]').first();
    await expect(tocElement).toBeVisible();

    // Click to select TOC and open Inspector
    await tocElement.click();
    await page.waitForTimeout(500);

    // Check TOC title input in inspector
    const tocTitleInput = page.locator('[data-testid="toc-title-input"]');
    await expect(tocTitleInput).toBeVisible();

    // Nudge TOC title
    await tocTitleInput.fill("فهرست سرفصل‌های جامع");
    await page.waitForTimeout(400);

    // Verify immediate reflection on canvas
    await expect(tocElement).toContainText("فهرست سرفصل‌های جامع");
  });

  test("2. Icon widget renders SVG from BUILDER_ICONS and responds to size control", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Click Icon in blocks palette
    const iconBtn = page.locator('button[data-block-type="icon"]').first();
    await iconBtn.scrollIntoViewIfNeeded();
    await iconBtn.click();
    await page.waitForTimeout(800);

    // Locate Icon in canvas iframe
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const iconElement = frame.locator('[data-widget-type="icon"]').first();
    await expect(iconElement).toBeVisible();

    // Verify SVG icon exists
    const iconSpan = iconElement.locator('[data-testid="builder-canvas-icon"]').first();
    await expect(iconSpan).toBeVisible();
    await expect(iconSpan.locator("svg")).toBeVisible();

    // Click icon to open inspector
    await iconElement.click();
    await page.waitForTimeout(500);

    // Check size input
    const sizeInput = page.locator('input[type="number"][value="32"], input[type="number"]').first();
    await expect(sizeInput).toBeVisible();
    await sizeInput.fill("48");
    await page.waitForTimeout(400);

    // Verify SVG style width updated to 48px
    const svgStyle = await iconSpan.locator("svg").getAttribute("style");
    expect(svgStyle).toContain("48px");
  });

  test("3. LayersTree Navigator renders all elements cleanly in 1920x1080 without horizontal scroll", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Open LayersTab
    const layersTabBtn = page.getByRole("button", { name: "لایه‌ها" }).first();
    await expect(layersTabBtn).toBeVisible();
    await layersTabBtn.click();
    await page.waitForTimeout(500);

    // Verify layers tree is visible and has items
    const layersTree = page.locator('[data-testid="layers-tree"], div:has-text("درخت ساختار لایه‌ها")').first();
    await expect(layersTree).toBeVisible();

    // Verify no body horizontal overflow on full 1920x1080 studio
    const isOverflowing = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(isOverflowing).toBe(false);
  });
});
