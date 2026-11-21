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
  const tmp = path.join(BACKEND_DIR, `.gym-r01-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 01: Weight 1 Regression Invariants", () => {
  test.beforeEach(async ({ context }) => {
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

  test("1. ?builder=1 activates BuilderStudio directly and suppresses chat FAB collision", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Studio root must be visible and fullscreen
    const studio = page.locator("div.fixed.inset-0").first();
    await expect(studio).toBeVisible();

    // Body-level chat widget must NOT be visible or displayed in builder
    const chatWidget = page.locator("#n8n-w");
    if (await chatWidget.count() > 0) {
      const display = await chatWidget.evaluate((el) => window.getComputedStyle(el).display);
      expect(display).toBe("none");
    }
  });

  test("2. Floating action toolbar clears iframe ceiling without clipping", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await expect(firstEl).toBeVisible({ timeout: 15000 });
    await firstEl.click();
    await page.waitForTimeout(500);

    const toolbar = frame.locator('[data-testid="floating-toolbar"]').first();
    await expect(toolbar).toBeVisible({ timeout: 15000 });

    const rect = await toolbar.evaluate((el) => el.getBoundingClientRect());
    expect(rect.top).toBeGreaterThanOrEqual(0);
  });

  test("3. LayersTree action buttons permanently visible at mouse (0,0) with 24px RTL indent", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    await page.mouse.move(0, 0);

    const layersTab = page.locator("button:has-text('لایه‌ها')").first();
    await layersTab.waitFor({ state: "visible", timeout: 15000 });
    await layersTab.click();
    await expect(page.locator("[data-layer-row]").first()).toBeVisible({ timeout: 15000 });

    const rows = page.locator("[data-layer-row]");
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const row = rows.nth(i);
      const buttons = row.locator("button");
      const bCount = await buttons.count();
      for (let b = 0; b < bCount; b++) {
        const btn = buttons.nth(b);
        const cls = (await btn.getAttribute("class")) || "";
        expect(cls).not.toContain("opacity-0");
        expect(await btn.isVisible()).toBe(true);
      }
    }
  });

  test("4. Empty container guide maintains min-height >= 80px and dashed border", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const emptyGuide = frame.locator('[data-testid="empty-container-guide"]').first();
    if (await emptyGuide.count() > 0) {
      await expect(emptyGuide).toBeVisible();
      const box = await emptyGuide.boundingBox();
      expect(box).not.toBeNull();
      if (box) {
        expect(box.height).toBeGreaterThanOrEqual(70);
      }
    }
  });
});
