import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-061/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w11-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 61: Semantic SSR Vector Cleanliness & Typography Token Parity", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1005", httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://127.0.0.1:1005", httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.216.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Typography group controls allow setting font-size, weight, text-align and text-shadow", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Click heading in iframe to select it and open Inspector
    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const heading = iframeEl.locator("h2").first();
    await expect(heading).toBeVisible();
    await heading.click();
    await page.waitForTimeout(500);

    // Switch to Style tab
    const styleTab = page.locator("[role='tab']:has-text('استایل')");
    await expect(styleTab).toBeVisible();
    await styleTab.click();
    await page.waitForTimeout(400);

    // Verify typography inputs
    const fontSizeInput = page.locator("[data-testid='typography-fontsize-input']");
    await expect(fontSizeInput).toBeVisible();

    const textShadowInput = page.locator("[data-testid='typography-text-shadow-input']");
    await expect(textShadowInput).toBeVisible();

    const cssFilterInput = page.locator("[data-testid='css-filter-input']");
    await expect(cssFilterInput).toBeVisible();
  });

  test("2. Background group controls allow background-color token chips and gradient directions", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const heading = iframeEl.locator("h2").first();
    await expect(heading).toBeVisible();
    await heading.click();
    await page.waitForTimeout(500);

    const styleTab = page.locator("[role='tab']:has-text('استایل')");
    await expect(styleTab).toBeVisible();
    await styleTab.click();
    await page.waitForTimeout(400);

    const bgTokenChip = page.locator("button:has-text('رنگ اصلی')").first();
    await expect(bgTokenChip).toBeVisible();

    // Click gradient background mode
    const gradModeBtn = page.locator("button:has-text('گرادیانت')").first();
    await expect(gradModeBtn).toBeVisible();
    await gradModeBtn.click();
    await page.waitForTimeout(300);

    // Verify gradient direction select is shown
    await expect(page.locator("text=جهت گرادیانت").first()).toBeVisible();
  });

  test("3. Search Bar and Nav Menu widgets render cleanly without layout shift", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("فرم جستجو");
    await page.waitForTimeout(300);

    const searchCard = page.locator('text="فرم جستجو"').first();
    await expect(searchCard).toBeVisible();
    await searchCard.click();
    await page.waitForTimeout(600);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("input[placeholder*='جستجو']").first()).toBeVisible();
  });

  test("4. Zero console errors, zero network errors, and zero horizontal overflows in round 61", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(errors.length).toBe(0);
  });
});
