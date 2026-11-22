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

test.describe("Builder Gym Round 25: Cart Summary, Mini Cart, and Recently Viewed 4-Layer Sync", () => {
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

  test("1. Cart Summary block can be inserted from palette and rendered live on canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("خلاصه سبد");
    await page.waitForTimeout(300);

    const cartCard = page.locator('text="خلاصه سبد خرید"').first();
    await expect(cartCard).toBeVisible();
    await cartCard.click();
    await page.waitForTimeout(500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const summaryHeading = frame.locator('text="جمع اقلام:"').first();
    await expect(summaryHeading).toBeVisible();
  });

  test("2. Inspector updates Cart Summary title and button label with live DOM reflection", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("خلاصه سبد");
    await page.waitForTimeout(300);

    const cartCard = page.locator('text="خلاصه سبد خرید"').first();
    await expect(cartCard).toBeVisible();
    await cartCard.click();
    await page.waitForTimeout(500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const summaryHeading = frame.locator('text="جمع اقلام:"').first();
    await summaryHeading.click();
    await page.waitForTimeout(400);

    const inspector = page.locator('[data-builder-inspector]');
    const titleInput = inspector.locator('input[value*="خلاصه سبد"]').first();
    await titleInput.fill("فاکتور نهایی و تسویه");
    await page.waitForTimeout(400);

    const btnInput = inspector.locator('input[value*="ادامه فرآیند"]').first();
    await btnInput.fill("پرداخت اینترنتی سفارش");
    await page.waitForTimeout(400);

    // Assert live canvas updated
    await expect(frame.locator('text="فاکتور نهایی و تسویه"').first()).toBeVisible();
    await expect(frame.locator('text="پرداخت اینترنتی سفارش"').first()).toBeVisible();
  });
});
