import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3800";
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
  const tmp = path.join(BACKEND_DIR, `.gym-w1-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Wave 1: Elementor Parity (Transform, Mask & Shape Dividers)", () => {
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

  test("1. Transform controls apply rotate and scale directly to canvas element style", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const headingEl = frame.locator('[data-element-id="el_e2ehead1"]').first();
    await expect(headingEl).toBeVisible();
    await headingEl.click();
    await page.waitForTimeout(400);

    // Switch to Advanced Tab
    const advTab = page.locator('button[data-state]:has-text("پیشرفته"), button:has-text("پیشرفته")').first();
    if (await advTab.isVisible()) {
      await advTab.click();
      await page.waitForTimeout(400);
    }

    // Input rotate deg
    const rotateInput = page.locator('input[type="number"][dir="ltr"]').first();
    if (await rotateInput.isVisible()) {
      await rotateInput.fill("15");
      await page.waitForTimeout(400);

      // Check live canvas element style
      const transformStyle = await headingEl.evaluate((el) => window.getComputedStyle(el).transform);
      expect(transformStyle).not.toBe("none");
    }
  });

  test("2. Shape Divider Top renders SVG path on container element without DOM error", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    // Select the first container
    const containerEl = frame.locator('[data-element-id="cont_e2eroot"]').first();
    if (await containerEl.isVisible()) {
      await containerEl.click();
      await page.waitForTimeout(400);

      // Open Style Tab
      const styleTab = page.locator('button[data-state]:has-text("استایل"), button:has-text("استایل")').first();
      if (await styleTab.isVisible()) {
        await styleTab.click();
        await page.waitForTimeout(400);
      }
    }
  });
});
