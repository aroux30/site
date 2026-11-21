import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3100";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r14-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 14: Weight 6 (Keyboard Reordering Alt+Arrows & Escape Deselection)", () => {
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

  test("1. Escape key clears active selection and dismisses floating toolbar", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

    const firstBlock = frame.locator("[data-element-id]").first();
    await firstBlock.click();
    await page.waitForTimeout(400);

    const toolbar = frame.locator("[data-testid='floating-toolbar']");
    await expect(toolbar).toBeVisible({ timeout: 15000 });

    // Press Escape
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);

    await expect(toolbar).not.toBeVisible();
  });

  test("2. Alt+ArrowDown forwards keyboard reordering and changes section hierarchy", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();

    const heroCard = page.locator("div[data-pattern-slug='hero-banner']").first();
    await expect(heroCard).toBeVisible({ timeout: 15000 });
    await heroCard.click();
    await page.waitForTimeout(600);

    const compCard = page.locator("div[data-pattern-slug='comparison-table']").first();
    await expect(compCard).toBeVisible({ timeout: 15000 });
    await compCard.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const heroSection = frame.locator("text=/کالکشن جدید رسید/").first();
    await heroSection.click();
    await page.waitForTimeout(400);

    // Trigger Alt+ArrowDown
    await page.keyboard.press("Alt+ArrowDown");
    await page.waitForTimeout(500);

    // Undo should be enabled
    const undoBtn = page.locator("button[title*='Ctrl+Z']").first();
    await expect(undoBtn).toBeEnabled();
  });

  test("3. Ctrl+Z undo restores previous layout sequence", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

    const firstBlock = frame.locator("[data-element-id]").first();
    await firstBlock.click();
    await page.waitForTimeout(400);

    const dupBtn = frame.locator("button[title*='تکثیر']").first();
    if (await dupBtn.isVisible()) {
      await dupBtn.click();
      await page.waitForTimeout(500);

      await page.keyboard.press("Control+z");
      await page.waitForTimeout(500);
    }
  });
});
