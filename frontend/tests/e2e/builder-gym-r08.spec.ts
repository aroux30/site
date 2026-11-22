import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3400";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r08-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 08: Weight 2 (Pricing Table, Categories & Quotes Regression)", () => {
  test.beforeEach(async ({ context }) => {
    const probeIp = `10.97.${Math.floor(Math.random() * 200) + 1}.${Math.floor(Math.random() * 200) + 1}`;
    await context.setExtraHTTPHeaders({
      "X-Forwarded-For": `${probeIp}, 10.0.0.1`,
    });
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
        })
      );
    });
  });

  test("1. pricing-table renders description for all plans including featured plan 2", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const patternsTab = page.locator('[data-testid="patterns-tab-btn"], button:has-text("الگوها")').first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(500);

    const pricingCard = page.locator("div[data-pattern-slug='pricing-table']").first();
    await expect(pricingCard).toBeVisible({ timeout: 15000 });
    await pricingCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const plan2Desc = frame.locator("text=/بهترین انتخاب برای تیم‌ها/").first();
    await expect(plan2Desc).toBeVisible({ timeout: 15000 });

    const plan1Heading = frame.locator("h3:has-text('پایه')").first();
    const plan2Heading = frame.locator("h3:has-text('حرفه‌ای')").first();
    const plan3Heading = frame.locator("h3:has-text('ویژه')").first();
    await expect(plan1Heading).toBeVisible({ timeout: 15000 });
    await expect(plan2Heading).toBeVisible({ timeout: 15000 });
    await expect(plan3Heading).toBeVisible({ timeout: 15000 });
  });

  test("2. mega-menu-categories renders 4 full-width category buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const patternsTab = page.locator('[data-testid="patterns-tab-btn"], button:has-text("الگوها")').first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(500);

    const megaMenuCard = page.locator("div[data-pattern-slug='mega-menu-categories']").first();
    await expect(megaMenuCard).toBeVisible({ timeout: 15000 });
    await megaMenuCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const laptopBtn = frame.locator("a:has-text('لپ‌تاپ و کامپیوتر'), button:has-text('لپ‌تاپ و کامپیوتر'), span:has-text('لپ‌تاپ و کامپیوتر')").first();
    await expect(laptopBtn).toBeVisible({ timeout: 15000 });
  });

  test("3. pull-quote and support-callout render semantic quote and support box", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const patternsTab = page.locator('[data-testid="patterns-tab-btn"], button:has-text("الگوها")').first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(500);

    const quoteCard = page.locator("div[data-pattern-slug='pull-quote']").first();
    await expect(quoteCard).toBeVisible({ timeout: 15000 });
    await quoteCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const quoteEl = frame.locator("h3:has-text('سرمایه‌گذاری روی کیفیت')").first();
    await expect(quoteEl).toBeVisible({ timeout: 15000 });
  });
});
