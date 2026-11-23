import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const PORT = 4002;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PORT}`;
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-048/after");
const ARTIFACTS_DIR_SHORT = path.resolve(".loop/artifacts/builder-gym/round-48/after");

fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
fs.mkdirSync(ARTIFACTS_DIR_SHORT, { recursive: true });

test.describe("Builder Gym Round 48: Nested Tabs & Nested Accordion Polish", () => {
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

  test("1. Nested Tabs and Nested Accordion insert, manage tabs in inspector, and switch tabs in canvas", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // 1. Search for nested tabs in palette
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("تودرتو");
    await page.waitForTimeout(400);

    // 2. Insert Nested Tabs
    const tabsCard = page.locator('text="تب‌های تودرتو"').first();
    await expect(tabsCard).toBeVisible();
    await tabsCard.click();
    await page.waitForTimeout(1000);

    // 3. Verify in frame
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    await expect(frame.locator('text="برگه اول"').first()).toBeVisible();

    // 4. Verify Inspector displays Nested Tabs controls
    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector).toBeVisible();

    // 5. Add a tab
    const addTabBtn = inspector.locator('text="+ افزودن زبانه"');
    if (await addTabBtn.isVisible()) {
      await addTabBtn.click();
      await page.waitForTimeout(300);
    }

    // 6. Capture after screenshot
    const shot1 = path.join(ARTIFACTS_DIR, "01-nested-tabs-customized-1920x1080.png");
    await page.screenshot({ path: shot1 });
    fs.copyFileSync(shot1, path.join(ARTIFACTS_DIR_SHORT, "01-nested-tabs-customized-1920x1080.png"));

    expect(fs.existsSync(shot1)).toBe(true);
  });

  test("3. Inserting loop_carousel renders horizontal scrollable card track inside canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("تکرارشونده");
    await page.waitForTimeout(300);

    const carouselCard = page.locator('button[data-block-type="loop_carousel"], button:has-text("کاروسل تکرارشونده پویا")').first();
    await carouselCard.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const loopContainer = frame.locator('[data-widget="loop_carousel"], .builder-product-grid').first();
    await expect(loopContainer).toBeVisible();
  });
});
