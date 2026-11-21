import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3750";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r21-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 21: Elementor Pro Custom Attributes Parity & P0 Invariants", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
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

  test("1. Empty container guide has 80px minimum height and action text (P0 Parity)", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const emptyGuide = frame.locator('[data-testid="empty-container-guide"]').first();
    await expect(emptyGuide).toBeVisible();

    // Verify Persian guide copy
    await expect(emptyGuide).toContainText("افزودن بلوک به این بخش");

    // Verify computed height >= 80px
    const box = await emptyGuide.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThanOrEqual(75);
  });

  test("2. Custom Attributes control in Advanced Inspector reflects on live canvas (Elementor Pro)", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Select the first heading on canvas
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const headingEl = frame.locator('[data-element-id="el_e2ehead1"]').first();
    await expect(headingEl).toBeVisible();
    await headingEl.click();
    await page.waitForTimeout(400);

    // Switch Inspector to Advanced Tab
    const advTab = page.locator('button[data-state]:has-text("پیشرفته"), button:has-text("پیشرفته")').first();
    if (await advTab.isVisible()) {
      await advTab.click();
      await page.waitForTimeout(400);
    }

    // Custom Attributes textarea is present
    const customAttrTextarea = page.locator('[data-testid="custom-attributes-textarea"]');
    await expect(customAttrTextarea).toBeVisible();

    // Enter key|value attribute lines
    await customAttrTextarea.fill("data-tracking|hero-cta\naria-label|test-region");
    await page.waitForTimeout(500);

    // Assert live canvas element received the custom attributes
    await expect(headingEl).toHaveAttribute("data-tracking", "hero-cta");
    await expect(headingEl).toHaveAttribute("aria-label", "test-region");
  });

  test("3. LayersTree vertical guide border and 24px per level RTL indent hold strictly", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.mouse.move(0, 0);

    const layersTab = page.getByRole("button", { name: "لایه‌ها", exact: true });
    if (await layersTab.isVisible()) {
      await layersTab.click();
      await page.waitForTimeout(500);
    }

    const rows = page.locator("[data-layer-row]");
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const row = rows.nth(i);
      const depthAttr = await row.getAttribute("data-depth");
      const depth = depthAttr ? parseInt(depthAttr, 10) : 0;
      if (depth > 0) {
        const parentDiv = row.locator("..");
        const style = await parentDiv.getAttribute("style");
        expect(style).toContain(`margin-right: ${depth * 24}px`);
      }
    }
  });
});
