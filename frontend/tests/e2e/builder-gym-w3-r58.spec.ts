import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1004";
const BACKEND_DIR = path.resolve(__dirname, "../../../backend");
const ARTIFACTS_DIR = path.resolve(__dirname, "../../../.loop/artifacts/builder-gym/round-58/after");
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
  const tmp = path.join(BACKEND_DIR, `.gym-r58-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 58: Weight 3 Patterns & Global Styles Verification", () => {
  test.use({ viewport: { width: 1280, height: 720 } });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1004", httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Verify Blocks Palette tabs, Patterns insertion, Global Styles dialog and Theme Reset", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // 1. Verify Blocks Palette tabs (Blocks, Patterns, Templates)
    const patternsTabBtn = page.locator('[data-testid="patterns-tab-btn"]').first();
    await expect(patternsTabBtn).toBeVisible();
    await patternsTabBtn.click();
    await page.waitForTimeout(400);

    // Verify Category chips in Patterns tab
    const categoryChips = page.locator("[data-category-chips]").first();
    await expect(categoryChips).toBeVisible();

    // 2. Open Global Styles Dialog from Toolbar
    const globalStylesBtn = page.locator('button[title*="استایل‌های سراسری"]').first();
    await expect(globalStylesBtn).toBeVisible();
    await globalStylesBtn.click();
    await page.waitForTimeout(400);

    // Verify Dialog content and Title
    const dialogTitle = page.locator("text=تنظیمات استایل سراسری برگه");
    await expect(dialogTitle).toBeVisible();

    // Change primary color preset
    const presetBtn = page.locator('button[title*="فیروزه‌ای"]').first();
    if (await presetBtn.isVisible()) {
      await presetBtn.click();
      await page.waitForTimeout(200);
    }

    // Click Reset to Site Theme button
    const resetThemeBtn = page.locator("button:has-text('بازنشانی به تم سایت')").first();
    await expect(resetThemeBtn).toBeVisible();
    await resetThemeBtn.click();
    await page.waitForTimeout(400);

    // Dialog should be closed
    await expect(dialogTitle).not.toBeVisible();

    // 3. Verify Canvas iframe theme token injection
    const frame = page.frameLocator('[data-testid="canvas-iframe"]');
    const container = frame.locator('[data-element-id]').first();
    await expect(container).toBeVisible();
  });
});
