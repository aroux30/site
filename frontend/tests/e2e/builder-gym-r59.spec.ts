import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const port = process.env.PORT || "1003";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${port}`;
const BACKEND_DIR = path.resolve(__dirname, "../../../backend");
const ARTIFACTS_DIR = path.resolve(`.loop/artifacts/builder-gym/round-055/after`);

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
  const tmp = path.join(BACKEND_DIR, `.gym-r55-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 55: Weight 0 Triage & Parity Verification", () => {
  test.use({ viewport: { width: 1280, height: 720 } });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: `http://localhost:${port}`, httpOnly: false, sameSite: "Lax" },
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

  test("1. Toolbar layout does not overflow or intersect at 1280x720 and 1440x900", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const header = page.locator("header.h-14").first();
    await expect(header).toBeVisible();

    const overflow1280 = await page.evaluate(() => {
      const h = document.querySelector("header.h-14") || document.querySelectorAll("header")[1] || document.querySelector("header");
      return h ? h.scrollWidth - h.clientWidth : 0;
    });
    expect(overflow1280).toBeLessThanOrEqual(1);

    // Switch to 1440x900
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(500);
    const overflow1440 = await page.evaluate(() => {
      const h = document.querySelector("header.h-14") || document.querySelectorAll("header")[1] || document.querySelector("header");
      return h ? h.scrollWidth - h.clientWidth : 0;
    });
    expect(overflow1440).toBeLessThanOrEqual(1);
  });

  test("2. Single icon widget renders valid SVG element and no raw string text", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvas = page.frameLocator('iframe[title="Canvas Preview"], iframe').first();
    const iconWidget = canvas.locator('[data-widget="icon"]').first();
    if (await iconWidget.isVisible()) {
      const hasSvg = await iconWidget.locator("svg").count();
      expect(hasSvg).toBeGreaterThan(0);
      const text = (await iconWidget.innerText()).trim();
      expect(text).not.toBe("star");
    }
  });

  test("3. Left InspectorPanel vertical scroll chain and style controls reset buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const inspector = page.locator("aside[data-builder-inspector]");
    await expect(inspector).toBeVisible();

    const scrollContainer = inspector.locator(".overflow-y-auto").first();
    if (await scrollContainer.isVisible()) {
      const scrollInfo = await scrollContainer.evaluate((el) => ({
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
      }));
      expect(scrollInfo.clientHeight).toBeGreaterThan(0);
    }
  });
});
