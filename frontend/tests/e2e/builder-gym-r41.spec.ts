import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4001";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r25-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 25: Elementor Image Carousel, Toggle & Hotspot Parity", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:4001", httpOnly: false, sameSite: "Lax" },
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

  test("1. Block palette filters and includes image_carousel, toggle, and hotspot", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجو"]');
    await expect(searchInput).toBeVisible();

    // Verify search finds image_carousel
    await searchInput.fill("اسلایدر تصویر");
    await page.waitForTimeout(300);
    const carouselCard = page.locator('button:has-text("اسلایدر تصویر")');
    await expect(carouselCard).toBeVisible();

    // Verify search finds toggle
    await searchInput.fill("تاگل");
    await page.waitForTimeout(300);
    const toggleCard = page.locator('button:has-text("تاگل مستقل")');
    await expect(toggleCard).toBeVisible();

    // Verify search finds hotspot
    await searchInput.fill("نقطه کانونی");
    await page.waitForTimeout(300);
    const hotspotCard = page.locator('button:has-text("نقطه کانونی")');
    await expect(hotspotCard).toBeVisible();
  });

  test("2. Inserting toggle renders multiple collapsible details panels", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجو"]');
    await searchInput.fill("تاگل مستقل");
    await page.waitForTimeout(300);

    const toggleCard = page.locator('button:has-text("تاگل مستقل")');
    await toggleCard.click();
    await page.waitForTimeout(600);

    // Check inside canvas iframe (newly inserted toggle is the last details group)
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const toggleDetails = frame.locator("details:has-text('بخش تاشوی اول')");
    await expect(toggleDetails).toBeVisible();
    await expect(toggleDetails).toContainText("بخش تاشوی اول");
  });
});
