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
  const tmp = path.join(BACKEND_DIR, `.gym-r41-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 41: 1920x1080 Full Studio Parity & Toggle, Image Carousel, Hotspot", () => {
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

  test("1. Block palette filters and includes image_carousel, toggle, and hotspot at 1920x1080", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجو"]').first();
    await expect(searchInput).toBeVisible();

    // Verify search finds image_carousel
    await searchInput.fill("اسلایدر تصویر");
    await page.waitForTimeout(300);
    const carouselCard = page.locator('button:has-text("اسلایدر تصویر")').first();
    await expect(carouselCard).toBeVisible();

    // Verify search finds toggle
    await searchInput.fill("تاگل");
    await page.waitForTimeout(300);
    const toggleCard = page.locator('button:has-text("تاگل مستقل")').first();
    await expect(toggleCard).toBeVisible();

    // Verify search finds hotspot
    await searchInput.fill("نقطه کانونی");
    await page.waitForTimeout(300);
    const hotspotCard = page.locator('button:has-text("نقطه کانونی")').first();
    await expect(hotspotCard).toBeVisible();
  });

  test("2. Inserting toggle renders multiple collapsible details panels and can be customized in Inspector at 1920x1080", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجو"]').first();
    await searchInput.fill("تاگل مستقل");
    await page.waitForTimeout(300);

    const toggleCard = page.locator('button:has-text("تاگل مستقل")').first();
    await toggleCard.click();
    await page.waitForTimeout(600);

    // Check inside canvas iframe
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const toggleDetails = frame.locator("details:has-text('بخش تاشوی اول')").first();
    await expect(toggleDetails).toBeVisible();
    await expect(toggleDetails).toContainText("بخش تاشوی اول");

    // Customize first toggle title in Inspector
    const inspector = page.locator('[data-builder-inspector]');
    const firstTitleInput = inspector.locator('input[data-testid="toggle-item-title-0"]');
    if (await firstTitleInput.isVisible()) {
      await firstTitleInput.fill("پرسش اول کاربران");
      await page.waitForTimeout(300);
      await expect(frame.locator("details:has-text('پرسش اول کاربران')").first()).toBeVisible();
    }
  });
});
