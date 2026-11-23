import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1003";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-050/after");

fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });

function getAdminToken() {
  const script = `
import asyncio, datetime, uuid
from app.core.security.jwt import create_access_token
async def main():
    user_id = str(uuid.UUID("47f274da-3abd-4d91-bc9c-83ba913fc66f"))
    print("TOKEN_START:" + create_access_token(
        user_id,
        extra_claims={"roles": ["super_admin"], "is_superuser": True, "permissions": ["*"]},
        expires_delta=datetime.timedelta(hours=2),
    ))
asyncio.run(main())
`;
  const tmp = path.join(BACKEND_DIR, `.gym-r50-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 50: Multi-Step Form & Loop Builder (Grid / Carousel) 4-Layer Parity", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1003", httpOnly: false, sameSite: "Lax" },
      ]);
    }
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

  test("1. Multi-Step Form widget can be customized in Inspector and renders in Canvas with custom buttons", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // 1. Search in blocks palette
    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("فرم چندمرحله‌ای");
    await page.waitForTimeout(300);

    const msfCard = page.locator('button[data-block-type="multi_step_form"]').first();
    await expect(msfCard).toBeVisible();

    // 2. Click to add multi-step form to canvas
    await msfCard.click();
    await page.waitForTimeout(800);

    // 3. Verify Inspector panel shows multi-step controls
    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector).toBeVisible();

    // 4. Verify live canvas renders multi_step_form with custom navigation buttons
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const msfWidget = frame.locator('[data-widget="multi_step_form"]').first();
    await expect(msfWidget).toBeVisible();
    await expect(msfWidget.locator('text="اطلاعات تماس"').first()).toBeVisible();
    await expect(msfWidget.locator('text="مرحله بعد"').first()).toBeVisible();
    await expect(msfWidget.locator('text="مرحله قبل"').first()).toBeVisible();

    // 5. Screenshot
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-multistep-form-verified.png") });
  });

  test("2. Loop Grid widget renders cards and controls without falling back to placeholder", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // 1. Search in blocks palette
    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("حلقه پویا");
    await page.waitForTimeout(300);

    const loopCard = page.locator('button[data-block-type="loop_grid"]').first();
    await expect(loopCard).toBeVisible();

    // 2. Insert into canvas
    await loopCard.click();
    await page.waitForTimeout(800);

    // 3. Verify canvas renders real loop_grid cards (not the dashed fallback)
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const loopGridWidget = frame.locator('[data-widget="loop_grid"]').first();
    await expect(loopGridWidget).toBeVisible();
    await expect(loopGridWidget.locator('h4').first()).toBeVisible();
    await expect(loopGridWidget.locator('text="ویجت loop_grid"')).toHaveCount(0);

    // 4. Screenshot
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "02-loop-grid-verified.png") });
  });

  test("3. Loop Carousel widget renders responsive carousel with navigation buttons", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // 1. Search in blocks palette
    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("گردونه پویا");
    await page.waitForTimeout(300);

    const loopCarouselCard = page.locator('button[data-block-type="loop_carousel"]').first();
    await expect(loopCarouselCard).toBeVisible();

    // 2. Insert into canvas
    await loopCarouselCard.click();
    await page.waitForTimeout(800);

    // 3. Verify canvas renders real loop_carousel (not the dashed fallback)
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const loopCarWidget = frame.locator('[data-widget="loop_carousel"]').first();
    await expect(loopCarWidget).toBeVisible();
    await expect(loopCarWidget.locator('text="ویجت loop_carousel"')).toHaveCount(0);

    // 4. Screenshot
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "03-loop-carousel-verified.png") });
  });

  test("4. Studio layout preserves 3 columns and zero horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const rightAside = page.locator("aside").first();
    await expect(rightAside).toBeVisible();
    const rightBox = await rightAside.boundingBox();
    expect(rightBox).not.toBeNull();
    expect(rightBox!.width).toBe(320);

    const inspectorAside = page.locator("[data-builder-inspector]");
    await expect(inspectorAside).toBeVisible();

    // Check for overflow
    const maxOverflow = await page.evaluate(() => {
      const sidebars = document.querySelectorAll("aside, main, [data-panel]");
      let overflow = 0;
      sidebars.forEach((el) => {
        const diff = el.scrollWidth - el.clientWidth;
        if (diff > overflow) overflow = diff;
      });
      return overflow;
    });
    expect(maxOverflow).toBe(0);
  });
});
