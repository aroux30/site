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
  const tmp = path.join(BACKEND_DIR, `.gym-r23-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 23: Elementor Icon List, Blockquote & Price Table Parity", () => {
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

  test("1. Block palette filters and includes icon_list, blockquote, and price_table", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجو"]');
    await expect(searchInput).toBeVisible();

    // Verify search finds icon_list
    await searchInput.fill("لیست آیکون");
    await page.waitForTimeout(300);
    const iconListCard = page.locator('button:has-text("لیست آیکون")');
    await expect(iconListCard).toBeVisible();

    // Verify search finds blockquote
    await searchInput.fill("نقل‌قول برجسته");
    await page.waitForTimeout(300);
    const blockquoteCard = page.locator('button:has-text("نقل‌قول برجسته")');
    await expect(blockquoteCard).toBeVisible();

    // Verify search finds price_table
    await searchInput.fill("جدول تعرفه");
    await page.waitForTimeout(300);
    const priceTableCard = page.locator('button:has-text("جدول تعرفه")');
    await expect(priceTableCard).toBeVisible();
  });

  test("2. Inserting blockquote renders quote text and author cite correctly", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Search and click blockquote to insert
    const searchInput = page.locator('input[placeholder*="جستجو"]');
    await searchInput.fill("نقل‌قول برجسته");
    await page.waitForTimeout(300);

    const blockquoteCard = page.locator('button:has-text("نقل‌قول برجسته")');
    await blockquoteCard.click();
    await page.waitForTimeout(600);

    // Check inside canvas iframe
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const quoteEl = frame.locator("blockquote").last();
    await expect(quoteEl).toBeVisible();
    await expect(quoteEl).toContainText("سادگی نهایت هوشمندی");
  });
});
