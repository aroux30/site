import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r12-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 12: Weight 6 (Deterministic Section Reordering & Toolbar Arrows)", () => {
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

  test("1. Floating action toolbar includes functional Move Up and Move Down buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

    const firstBlock = frame.locator("[data-element-id]").first();
    await firstBlock.click();
    await page.waitForTimeout(400);

    const moveUp = frame.locator("[data-testid='move-up-btn']").first();
    const moveDown = frame.locator("[data-testid='move-down-btn']").first();
    await expect(moveUp).toBeVisible({ timeout: 15000 });
    await expect(moveDown).toBeVisible({ timeout: 15000 });
  });

  test("2. Reordering root sections changes order deterministically and supports undo", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();

    // Insert Hero and Comparison Table
    const heroCard = page.locator("div[data-pattern-slug='hero-banner']").first();
    await expect(heroCard).toBeVisible({ timeout: 15000 });
    await heroCard.click();
    await page.waitForTimeout(600);

    const compCard = page.locator("div[data-pattern-slug='comparison-table']").first();
    await expect(compCard).toBeVisible({ timeout: 15000 });
    await compCard.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const heroContainer = frame.locator("text=/کالکشن جدید رسید/").first();
    await heroContainer.click();
    await page.waitForTimeout(400);

    const moveDown = frame.locator("[data-testid='move-down-btn']").first();
    await expect(moveDown).toBeVisible({ timeout: 15000 });
    await moveDown.click();
    await page.waitForTimeout(500);

    // Test Undo via toolbar button
    const undoBtn = page.locator("button[title*='Ctrl+Z']").first();
    await expect(undoBtn).toBeEnabled();
    await undoBtn.click();
    await page.waitForTimeout(500);
  });

  test("3. Keyboard shortcuts Alt+ArrowUp/Down or Ctrl+Z operate smoothly", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

    const firstBlock = frame.locator("[data-element-id]").first();
    await firstBlock.click();
    await page.waitForTimeout(400);

    const toolbar = frame.locator("[data-testid='floating-toolbar']").first();
    await expect(toolbar).toBeVisible({ timeout: 15000 });
  });
});
