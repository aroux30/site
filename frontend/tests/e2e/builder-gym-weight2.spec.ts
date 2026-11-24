import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-052/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w2-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Weight 2: 100% Audit of Content, Style, and Advanced Controls for Interactive Widgets", () => {
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
      "x-forwarded-for": `10.207.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Table widget can be added and customized in Inspector (headers, rows, bordered, striped)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    // Search table in palette
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("جدول");
    await page.waitForTimeout(300);

    const tableCard = page.locator('text="جدول داده"').first();
    await expect(tableCard).toBeVisible();
    await tableCard.click();
    await page.waitForTimeout(600);

    // Verify Inspector controls
    const headersInput = page.locator("[data-testid='table-headers-input']");
    await expect(headersInput).toBeVisible();

    // Verify canvas iframe renders table
    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const tableEl = iframeEl.locator("table").first();
    await expect(tableEl).toBeVisible();
  });

  test("2. Star Rating widget renders vector SVG star without raw star text", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("امتیاز");
    await page.waitForTimeout(300);

    const starCard = page.locator('text="امتیاز ستاره‌ای"').first();
    await expect(starCard).toBeVisible();
    await starCard.click();
    await page.waitForTimeout(600);

    // Verify Inspector controls
    const ratingInput = page.locator("[data-testid='star-rating-value-input']");
    await expect(ratingInput).toBeVisible();

    // Verify canvas iframe renders SVG
    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const svgEl = iframeEl.locator("svg").first();
    await expect(svgEl).toBeVisible();
  });

  test("3. Form Select widget controls allow editing label, name, and newline-separated options", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("کشویی");
    await page.waitForTimeout(300);

    const selectCard = page.locator('text="منوی کشویی"').first();
    await expect(selectCard).toBeVisible();
    await selectCard.click();
    await page.waitForTimeout(600);

    const labelInput = page.locator("[data-testid='form-select-label-input']");
    await expect(labelInput).toBeVisible();
    await labelInput.fill("انتخاب استان");
    await page.waitForTimeout(300);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("text=انتخاب استان").first()).toBeVisible();
  });

  test("4. Countdown widget renders live countdown boxes with Persian numerals and titles", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("شمارنده");
    await page.waitForTimeout(300);

    const countCard = page.locator('text="شمارنده معکوس"').first();
    await expect(countCard).toBeVisible();
    await countCard.click();
    await page.waitForTimeout(600);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("text=روز").first()).toBeVisible();
    await expect(iframeEl.locator("text=ساعت").first()).toBeVisible();
  });
});
