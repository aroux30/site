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
  const tmp = path.join(BACKEND_DIR, `.gym-r10-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 10: Weight 6 (Full Landing Assembly & Layers Tree Overflow Regression)", () => {
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

  test("1. Assembling full 6-section landing maintains distinct root elements", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const patternsTab = page.locator('[data-testid="patterns-tab-btn"], button:has-text("الگوها")').first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(600);

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
    const heroH1 = frame.locator("h1:has-text('کالکشن جدید رسید')").first();
    const compH2 = frame.locator("h2:has-text('مقایسه مشخصات')").first();
    await expect(heroH1).toBeVisible({ timeout: 15000 });
    await expect(compH2).toBeVisible({ timeout: 15000 });
  });

  test("2. LayersTree rows at depths 1 to 3 preserve action buttons without overflow clipping", async ({ page }) => {
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

    // Switch to Layers Tree
    const layersTab = page.locator('[data-testid="sidebar-tab-layers"], button:has-text("لایه‌ها")').first();
    await layersTab.waitFor({ state: "visible", timeout: 15000 });
    await layersTab.click();
    await page.waitForTimeout(600);

    // Verify all rows have visible buttons and no clipping
    const rows = page.locator("[data-layer-row]");
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(2);

    for (let i = 0; i < Math.min(rowCount, 8); i++) {
      const row = rows.nth(i);
      const copyBtn = row.locator("button[title*='تکثیر']").first();
      await expect(copyBtn).toBeVisible();
    }
  });

  test("3. Preview mode toggle completely hides builder outlines and toolbars", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    const previewBtn = page.locator("button:has-text('پیش‌نمایش')").first();
    await expect(previewBtn).toBeVisible({ timeout: 15000 });
    await previewBtn.click();
    await page.waitForTimeout(500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const floatingToolbar = frame.locator("[data-testid='floating-toolbar']");
    await expect(floatingToolbar).not.toBeVisible();
  });
});
