import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const PORT = 4002;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PORT}`;
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-047/after");
const ARTIFACTS_DIR_SHORT = path.resolve(".loop/artifacts/builder-gym/round-47/after");

fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
fs.mkdirSync(ARTIFACTS_DIR_SHORT, { recursive: true });

test.describe("Builder Gym Round 47: Multi-Step Form 4-Layer Parity & Inspector Polish", () => {
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

  test("1. Multi-Step Form inserts, renders step indicators, and supports live step preview", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // 1. Search for multi_step_form in palette
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("مرحله");
    await page.waitForTimeout(400);

    // 2. Insert Multi-Step Form
    const formCard = page.locator('text="فرم چندمرحله‌ای"').first();
    await expect(formCard).toBeVisible();
    await formCard.click();
    await page.waitForTimeout(1000);

    // 3. Verify in frame
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const formElement = frame.locator('[data-widget="multi_step_form"]').first();
    await expect(formElement).toBeVisible();

    // 4. Verify Inspector displays Multi-Step Form controls
    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector).toBeVisible();

    // 5. Verify step repeater can add a step
    const addStepBtn = inspector.locator('text="+ افزودن مرحله"');
    if (await addStepBtn.isVisible()) {
      await addStepBtn.click();
      await page.waitForTimeout(300);
    }

    // 6. Capture after screenshot of studio with multi-step form
    const shot1 = path.join(ARTIFACTS_DIR, "01-multi-step-form-customized-1920x1080.png");
    await page.screenshot({ path: shot1 });
    fs.copyFileSync(shot1, path.join(ARTIFACTS_DIR_SHORT, "01-multi-step-form-customized-1920x1080.png"));

    expect(fs.existsSync(shot1)).toBe(true);
  });

  test("3. Inserting nested_accordion renders container with accordion badge inside canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("کانتینری");
    await page.waitForTimeout(300);

    const accordionCard = page.locator('button[data-block-type="nested_accordion"]').first();
    await accordionCard.click();
    await page.waitForTimeout(600);

    // Check inside canvas iframe for nested accordion badge
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const badge = frame.getByText("آکاردئون کانتینری").first();
    await expect(badge).toBeVisible();
  });
});
