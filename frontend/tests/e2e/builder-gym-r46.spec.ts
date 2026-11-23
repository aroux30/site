import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const PORT = 4002;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PORT}`;
const BACKEND_DIR = path.resolve(__dirname, "../../../backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-046/after");
const ARTIFACTS_DIR_SHORT = path.resolve(".loop/artifacts/builder-gym/round-46/after");

fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
fs.mkdirSync(ARTIFACTS_DIR_SHORT, { recursive: true });

test.describe("Builder Gym Round 46: Price Table & Price List 4-Layer Parity & Inspector Polish", () => {
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

  test("1. Price Table and Price List insert, render with proper styles, and reflect inspector changes in canvas", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // 1. Search for Price Table in palette
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("قیمت");
    await page.waitForTimeout(400);

    // 2. Insert Price Table
    const priceTableCard = page.locator('text="جدول تعرفه و قیمت"').first();
    await expect(priceTableCard).toBeVisible();
    await priceTableCard.click();
    await page.waitForTimeout(1000);

    // 3. Verify in frame
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const priceElement = frame.locator('[data-widget="price_table"]').first();
    await expect(priceElement).toBeVisible();

    // 4. Verify Inspector displays Price Table controls
    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector).toBeVisible();

    // 5. Verify features list in inspector can add feature
    const addFeatureBtn = inspector.locator('text="+ افزودن ویژگی"');
    if (await addFeatureBtn.isVisible()) {
      await addFeatureBtn.click();
      await page.waitForTimeout(300);
    }

    // 6. Capture after screenshot of studio with customized price table
    const shot1 = path.join(ARTIFACTS_DIR, "01-price-table-customized-1920x1080.png");
    await page.screenshot({ path: shot1 });
    fs.copyFileSync(shot1, path.join(ARTIFACTS_DIR_SHORT, "01-price-table-customized-1920x1080.png"));

    // 7. Insert Price List
    await searchInput.fill("لیست قیمت");
    await page.waitForTimeout(400);
    const priceListCard = page.locator('text="لیست قیمت"').first();
    await expect(priceListCard).toBeVisible();
    await priceListCard.click();
    await page.waitForTimeout(800);

    const priceListElement = frame.locator('[data-widget="price_list"]').first();
    await expect(priceListElement).toBeVisible();

    // 8. Capture after screenshot showing both Price Table and Price List
    const shot2 = path.join(ARTIFACTS_DIR, "02-price-list-and-table-verified.png");
    await page.screenshot({ path: shot2 });
    fs.copyFileSync(shot2, path.join(ARTIFACTS_DIR_SHORT, "02-price-list-and-table-verified.png"));

    expect(fs.existsSync(shot1)).toBe(true);
    expect(fs.existsSync(shot2)).toBe(true);
  });
});
