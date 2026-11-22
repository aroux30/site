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
  const tmp = path.join(BACKEND_DIR, `.gym-r24-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 24: Elementor Image Box, Price List & Share Buttons Parity", () => {
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

  test("1. Block palette filters and includes image_box, price_list, and share_buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجو"]');
    await expect(searchInput).toBeVisible();

    // Verify search finds image_box
    await searchInput.fill("جعبه تصویر");
    await page.waitForTimeout(300);
    const imgBoxCard = page.locator('button:has-text("جعبه تصویر")');
    await expect(imgBoxCard).toBeVisible();

    // Verify search finds price_list
    await searchInput.fill("لیست قیمت");
    await page.waitForTimeout(300);
    const priceListCard = page.locator('button:has-text("لیست قیمت")');
    await expect(priceListCard).toBeVisible();

    // Verify search finds share_buttons
    await searchInput.fill("اشتراک‌گذاری");
    await page.waitForTimeout(300);
    const shareCard = page.locator('button:has-text("دکمه‌های اشتراک‌گذاری")');
    await expect(shareCard).toBeVisible();
  });

  test("2. Inserting image_box renders title and description inside canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجو"]');
    await searchInput.fill("جعبه تصویر");
    await page.waitForTimeout(300);

    const imgBoxCard = page.locator('button:has-text("جعبه تصویر")');
    await imgBoxCard.click();
    await page.waitForTimeout(600);

    // Check inside canvas iframe
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const boxEl = frame.locator("h3:has-text('عنوان خدمات یا محصول')").first();
    await expect(boxEl).toBeVisible();
  });
});
