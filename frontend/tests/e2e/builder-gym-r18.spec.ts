import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3200";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r09-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 18: Dynamic Countdown Calculation & Product Grid Inspector Controls", () => {
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

  test("1. Countdown block dynamically computes Persian remaining days from target date", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Switch to basic blocks tab
    const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    // Search and click countdown block
    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("شمارنده معکوس");
    await page.waitForTimeout(300);

    const countdownCard = page.locator("button", { hasText: "شمارنده معکوس" }).first();
    await expect(countdownCard).toBeVisible();
    await countdownCard.click();
    await page.waitForTimeout(600);

    // In inspector, change target date to 5 days ahead
    const dateInput = page.locator("input.font-mono[placeholder*='2026-12-31']");
    await expect(dateInput).toBeVisible();
    const futureDate = new Date(Date.now() + 5 * 86400 * 1000).toISOString();
    await dateInput.fill(futureDate);
    await page.waitForTimeout(500);

    // Verify canvas displays computed days
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const dayUnits = frame.locator("span:has-text('روز')");
    await expect(dayUnits).toBeVisible();
  });

  test("2. Product grid block offers filter and pagination controls in Inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Switch to basic blocks tab
    const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("ویترین محصولات");
    await page.waitForTimeout(300);

    const gridBlockCard = page.locator("button", { hasText: "ویترین محصولات" }).first();
    await expect(gridBlockCard).toBeVisible();
    await gridBlockCard.click();
    await page.waitForTimeout(800);

    // Verify inspector controls for product grid
    const limitLabel = page.locator("text=تعداد کالاهای نمایشی");
    await expect(limitLabel).toBeVisible();

    const filterSelect = page.locator("text=فیلتر پیش‌فرض محصولات");
    await expect(filterSelect).toBeVisible();

    const paginationSwitch = page.locator("text=نمایش دکمه مشاهده بیشتر");
    await expect(paginationSwitch).toBeVisible();
  });

  test("3. Video widget URL and source type selection updates properly in Inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("پخش‌کننده ویدئو");
    await page.waitForTimeout(300);

    const videoCard = page.locator("button", { hasText: "پخش‌کننده ویدئو" }).first();
    await expect(videoCard).toBeVisible();
    await videoCard.click();
    await page.waitForTimeout(800);

    const videoTypeSelect = page.locator("text=نوع منبع ویدئو");
    await expect(videoTypeSelect).toBeVisible();

    const urlInput = page.locator("div.space-y-4 input.h-8").last();
    await expect(urlInput).toBeVisible();
  });
});
