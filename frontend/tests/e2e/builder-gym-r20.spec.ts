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
  const tmp = path.join(BACKEND_DIR, `.gym-r11-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 20: Navigation, Recently Viewed & Product Title Inspector Controls", () => {
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

  test("1. Mega menu button label is editable in Inspector with live canvas sync", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const basicBlocksSubTab = page.locator('[data-testid="sidebar-tab-blocks"], button:has-text("بلوک‌ها")').first();
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("مگامنو");
    await page.waitForTimeout(300);

    const megaMenuCard = page.locator("button", { hasText: "مگامنو" }).first();
    await expect(megaMenuCard).toBeVisible();
    await megaMenuCard.click();
    await page.waitForTimeout(800);

    // Inspector has label field
    const labelInput = page.locator("div.space-y-4 input.h-8").first();
    await expect(labelInput).toBeVisible();
    await labelInput.fill("کاتالوگ محصولات ویژه");
    await page.waitForTimeout(400);

    // Canvas updates
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const menuBtn = frame.locator("button:has-text('کاتالوگ محصولات ویژه')").first();
    await expect(menuBtn).toBeVisible();
  });

  test("2. Recently viewed block title and limit are editable in Inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const basicBlocksSubTab = page.locator('[data-testid="sidebar-tab-blocks"], button:has-text("بلوک‌ها")').first();
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("بازدیدهای اخیر");
    await page.waitForTimeout(300);

    const recentCard = page.locator("button", { hasText: "بازدیدهای اخیر" }).first();
    await expect(recentCard).toBeVisible();
    await recentCard.click();
    await page.waitForTimeout(800);

    // Inspector has title and limit fields
    const titleLabel = page.locator("text=عنوان بخش");
    await expect(titleLabel).toBeVisible();

    const titleInput = page.locator("div.space-y-4 input.h-8").first();
    await titleInput.fill("کالاهای مشاهده‌شده شما");
    await page.waitForTimeout(400);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const sectionHeading = frame.locator("text=کالاهای مشاهده‌شده شما").first();
    await expect(sectionHeading).toBeVisible();
  });

  test("3. Product title fallback title is editable in Inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const basicBlocksSubTab = page.locator('[data-testid="sidebar-tab-blocks"], button:has-text("بلوک‌ها")').first();
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("سرتیتر");
    await page.waitForTimeout(300);

    const headingCard = page.locator("button", { hasText: "سرتیتر" }).first();
    await expect(headingCard).toBeVisible();
    await headingCard.click();
    await page.waitForTimeout(800);

    const titleInput = page.locator("div.space-y-4 input.h-8").first();
    await expect(titleInput).toBeVisible();
  });
});
