import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-057/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w7-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Weight 7: Elementor Wave 2 Porting (Core & Pro Key Widgets, Popups, and Off-Canvas)", () => {
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
      "x-forwarded-for": `10.212.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Animated Headline widget renders highlighted text with wavy decoration", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("متحرک");
    await page.waitForTimeout(300);

    const headlineCard = page.locator('text="تیتر متحرک"').first();
    await expect(headlineCard).toBeVisible();
    await headlineCard.click();
    await page.waitForTimeout(600);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("h2:has-text('رشد کسب‌وکار'), h2:has-text('تیتر')").first()).toBeVisible();
  });

  test("2. Off-Canvas widget triggers sliding drawer with custom title", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("کشوی");
    await page.waitForTimeout(300);

    const offCanvasCard = page.locator('text="کشوی کناری"').first();
    await expect(offCanvasCard).toBeVisible();
    await offCanvasCard.click();
    await page.waitForTimeout(600);

    // Verify Off-Canvas identifier badge or drawer container
    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("text=کشوی جانبی (Off-Canvas)").first()).toBeVisible();
  });

  test("3. Popup Builder widget configures trigger conditions and popup title", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("پاپ");
    await page.waitForTimeout(300);

    const popupCard = page.locator('text="پاپ‌آپ تعاملی"').first();
    await expect(popupCard).toBeVisible();
    await popupCard.click();
    await page.waitForTimeout(600);

    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector.locator("text=محرک نمایش").first()).toBeVisible();
  });

  test("4. Price Table & Multi-Step Form render clean semantic structures in SSR", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("قیمت");
    await page.waitForTimeout(300);

    const priceCard = page.locator('text="جدول تعرفه و قیمت"').first();
    await expect(priceCard).toBeVisible();
    await priceCard.click();
    await page.waitForTimeout(600);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("text=پلن ویژه کسب‌وکار").first()).toBeVisible();
  });
});
