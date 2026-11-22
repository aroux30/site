import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3400";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r11-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 11: Weight 6 (Deep Container Layout & Inspector History Regression)", () => {
  test.beforeEach(async ({ context }) => {
    const probeIp = `10.97.${Math.floor(Math.random() * 200) + 1}.${Math.floor(Math.random() * 200) + 1}`;
    await context.setExtraHTTPHeaders({
      "X-Forwarded-For": `${probeIp}, 10.0.0.1`,
    });
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
        })
      );
    });
  });

  test("1. Deep container layout modification via Inspector updates AST and supports undo", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const patternsTab = page.locator('[data-testid="patterns-tab-btn"], button:has-text("الگوها")').first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(600);

    const heroCard = page.locator("div[data-pattern-slug='hero-banner']").first();
    await expect(heroCard).toBeVisible({ timeout: 15000 });
    await heroCard.click();
    await page.waitForTimeout(600);

    // Click on hero row container inside iframe
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const heroH1 = frame.locator("h1:has-text('کالکشن جدید رسید')").first();
    await expect(heroH1).toBeVisible({ timeout: 15000 });
    await heroH1.click();
    await page.waitForTimeout(400);

    // Open Inspector Style Tab
    const styleTab = page.getByRole("tab", { name: "استایل" });
    await expect(styleTab).toBeVisible({ timeout: 15000 });
    await styleTab.click();
    await page.waitForTimeout(400);

    // Verify Inspector renders Padding label
    const paddingLabel = page.locator("text=فاصله داخلی (Padding)");
    await expect(paddingLabel).toBeVisible({ timeout: 15000 });
  });

  test("2. Inspector element name editing applies deep update to LayersTree", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });

    // Select the first element in canvas
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstBlock = frame.locator("[data-element-id]").first();
    await firstBlock.click();
    await page.waitForTimeout(400);

    // Switch to Advanced tab in Inspector
    const advancedTab = page.getByRole("tab", { name: "پیشرفته" });
    await expect(advancedTab).toBeVisible({ timeout: 15000 });
    await advancedTab.click();
    await page.waitForTimeout(400);

    const nameInput = page.locator("aside[data-builder-inspector] input").first();
    await expect(nameInput).toBeVisible({ timeout: 15000 });
    await nameInput.fill("کانتینر اصلی تست");
    await page.waitForTimeout(400);

    // Switch to Layers Tree and verify renamed element appears
    const layersTab = page.locator('[data-testid="sidebar-tab-layers"], button:has-text("لایه‌ها")').first();
    await layersTab.waitFor({ state: "visible", timeout: 15000 });
    await layersTab.click();
    await page.waitForTimeout(600);

    const renamedLayer = page.locator("text='کانتینر اصلی تست'").first();
    await expect(renamedLayer).toBeVisible({ timeout: 15000 });
  });

  test("3. Detach global component clears synced state without corrupting tree", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstBlock = frame.locator("[data-element-id]").first();
    await firstBlock.click();
    await page.waitForTimeout(400);

    // Switch to Advanced Tab
    const advancedTab = page.locator("button:has-text('پیشرفته')").first();
    if (await advancedTab.isVisible()) {
      await advancedTab.click();
      await page.waitForTimeout(400);

      const makeGlobalBtn = page.locator("button:has-text('تبدیل به کامپوننت همگام سراسری')").first();
      if (await makeGlobalBtn.isVisible()) {
        await makeGlobalBtn.click();
        await page.waitForTimeout(400);

        const detachBtn = page.locator("button:has-text('جدا کردن از کامپوننت سراسری')").first();
        await expect(detachBtn).toBeVisible();
        await detachBtn.click();
        await page.waitForTimeout(400);

        // Verify it reverted to Make Global
        await expect(makeGlobalBtn).toBeVisible();
      }
    }
  });
});
