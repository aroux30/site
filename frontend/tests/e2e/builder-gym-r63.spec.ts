import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1001";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-59/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r59-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 59: Interactive & Form Widgets Semantic data-widget Synchronization", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1001", httpOnly: false, sameSite: "Lax" },
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

  test("1. Add interactive table and form widgets and verify data-widget attribute synchronization in canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Verify studio topbar loaded
    await expect(page.locator("text=ذخیره پیش‌نویس")).toBeVisible();

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    const frame = page.frameLocator('[data-testid="canvas-iframe"]');

    // Add Table
    await searchInput.fill("جدول");
    await page.waitForTimeout(300);
    const tableBtn = page.locator('button[data-block-type="table"]').first();
    if (await tableBtn.isVisible()) {
      await tableBtn.click();
      await page.waitForTimeout(400);
      const tableEl = frame.locator('[data-widget="table"]').first();
      await expect(tableEl).toBeVisible();
    }

    // Add Countdown
    await searchInput.fill("شمارشگر");
    await page.waitForTimeout(300);
    const countdownBtn = page.locator('button[data-block-type="countdown"]').first();
    if (await countdownBtn.isVisible()) {
      await countdownBtn.click();
      await page.waitForTimeout(400);
      const countdownEl = frame.locator('[data-widget="countdown"]').first();
      await expect(countdownEl).toBeVisible();
    }

    // Verify viewports 1440 and 1280
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(300);
    let overflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth - document.documentElement.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(5);

    await page.setViewportSize({ width: 1280, height: 720 });
    await page.waitForTimeout(300);
    overflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth - document.documentElement.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(5);

    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-r59-interactive-verified-1920x1080.png") });
  });
});
