import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4002";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r42-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 42: 1920x1080 Viewport Table of Contents & Progress Tracker Parity", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

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

  test("1. Block palette filters and includes table_of_contents and progress_tracker at 1920x1080", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجو"]').first();
    await expect(searchInput).toBeVisible();

    // Verify search finds table_of_contents
    await searchInput.fill("فهرست محتوا");
    await page.waitForTimeout(300);
    const tocCard = page.locator('button:has-text("فهرست محتوا")').first();
    await expect(tocCard).toBeVisible();

    // Verify search finds progress_tracker
    await searchInput.fill("ردیاب پیشرفت");
    await page.waitForTimeout(300);
    const trackerCard = page.locator('button:has-text("ردیاب پیشرفت")').first();
    await expect(trackerCard).toBeVisible();
  });

  test("2. Inserting table_of_contents renders heading list inside canvas at 1920x1080", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجو"]').first();
    await searchInput.fill("فهرست محتوا");
    await page.waitForTimeout(300);

    const tocCard = page.locator('button:has-text("فهرست محتوا")').first();
    await tocCard.click();
    await page.waitForTimeout(600);

    // Check inside canvas iframe
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const tocNav = frame.locator("nav[aria-label='فهرست محتوای صفحه']").first();
    await expect(tocNav).toBeVisible();
    await expect(tocNav).toContainText("فهرست عناوین برگه");
  });
});
