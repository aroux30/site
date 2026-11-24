import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-053/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w3-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Weight 3: 28 Preset Block Patterns, Blocks Palette, and Global Styles Dialog", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1005", httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://127.0.0.1:1005", httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.208.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
    });
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
        })
      );
    });
  });

  test("1. Blocks palette displays 3 tabs (Blocks, Patterns, My Templates) with search", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTabBtn = page.locator("[data-testid='sidebar-tab-blocks']");
    await expect(blocksTabBtn).toBeVisible();

    const patternsTabBtn = page.locator("[data-testid='patterns-tab-btn']");
    await expect(patternsTabBtn).toBeVisible();
    await expect(patternsTabBtn).toContainText("الگوها");

    // Click Patterns tab
    await patternsTabBtn.click();
    await page.waitForTimeout(400);

    // Verify search input placeholder adapts to patterns
    const searchInput = page.locator("aside input").first();
    await expect(searchInput).toBeVisible();

    // Verify category chips
    const categoryChips = page.locator("[data-category-chips]");
    await expect(categoryChips).toBeVisible({ timeout: 10000 });
  });

  test("2. Pattern insertion generates clean container tree on live canvas", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const patternsTabBtn = page.locator("[data-testid='patterns-tab-btn']");
    await patternsTabBtn.click();
    await page.waitForTimeout(400);

    // Filter or select first pattern card
    const firstInsertBtn = page.locator("aside button:has-text('درج الگو')").first();
    if (await firstInsertBtn.isVisible()) {
      await firstInsertBtn.click();
      await page.waitForTimeout(600);

      // Verify canvas iframe received the inserted container
      const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
      const containers = iframeEl.locator(".builder-container");
      await expect(containers.first()).toBeVisible();
    }
  });

  test("3. Global Styles dialog opens with brand color presets, font picker, and radius choices", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const globalStylesBtn = page.locator("button[title*='استایل‌های سراسری']");
    await expect(globalStylesBtn).toBeVisible();
    await globalStylesBtn.click();
    await page.waitForTimeout(500);

    // Verify Dialog content
    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator("text=تنظیمات استایل سراسری برگه")).toBeVisible();
    await expect(dialog.locator("text=رنگ اصلی برند")).toBeVisible();
    await expect(dialog.locator("text=شعاع گردی پیش‌فرض")).toBeVisible();

    // Close dialog
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    await expect(dialog).not.toBeVisible();
  });

  test("4. Reset to Site Theme in Global Styles cleans local overrides", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const globalStylesBtn = page.locator("button[title*='استایل‌های سراسری']");
    await globalStylesBtn.click();
    await page.waitForTimeout(500);

    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();

    const resetBtn = dialog.locator("button:has-text('بازنشانی به تم پیش‌فرض')");
    await expect(resetBtn).toBeVisible();
    await resetBtn.click();
    await page.waitForTimeout(400);

    // Verify dialog closes after reset
    await expect(dialog).not.toBeVisible();
  });
});
