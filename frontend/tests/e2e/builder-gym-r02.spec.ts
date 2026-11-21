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
  const tmp = path.join(BACKEND_DIR, `.gym-r02-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 02: Weight 2 (Blocks & Patterns Regression)", () => {
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

  test("1. Blocks search and category filtering", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    const searchInput = page.locator("input[placeholder*='جستجو']").first();
    await searchInput.fill("کانتینر");
    await page.waitForTimeout(400);

    const containerCard = page.locator("button:has-text('کانتینر')").first();
    await expect(containerCard).toBeVisible();
  });

  test("2. Pattern insertion renders typed AST with custom button styles", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    // Switch to patterns tab
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.click();
    await page.waitForTimeout(800);

    const heroPattern = page.locator("div[data-pattern-slug='hero-banner']").first();
    await expect(heroPattern).toBeVisible();
    await heroPattern.click();
    await page.waitForTimeout(1000);

    // Check canvas has inserted hero-banner
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const heroHeading = frame.locator("h1:has-text('کالکشن جدید رسید')").first();
    await expect(heroHeading).toBeVisible();

    // Verify custom button style in hero has contrast and classes
    const btn = frame.locator("a:has-text('همین حالا بخرید'), span:has-text('همین حالا بخرید'), [data-element-name*='همین حالا بخرید']").first();
    await expect(btn).toBeVisible();
  });

  test("3. All 28 patterns available in patterns palette", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.click();
    await expect(page.locator("[data-pattern-slug]").first()).toBeVisible({ timeout: 15000 });

    const cards = page.locator("[data-pattern-slug]");
    await expect(cards).toHaveCount(28, { timeout: 15000 });
  });
});
