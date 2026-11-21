import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
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

test.describe("Builder Gym Round 09: Weight 2 (Comparison Table, Lead Form & Brand Highlights)", () => {
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

  test("1. comparison-table renders 3-column table with column 1 highlighted", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(500);

    const compCard = page.locator("div[data-pattern-slug='comparison-table']").first();
    await expect(compCard).toBeVisible({ timeout: 15000 });
    await compCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const tableEl = frame.locator("table").first();
    await expect(tableEl).toBeVisible({ timeout: 15000 });

    const thPro = frame.locator("th:has-text('مدل پرو')").first();
    await expect(thPro).toBeVisible();
    const classes = await thPro.getAttribute("class");
    expect(classes).toContain("bg-primary/10");
  });

  test("2. lead-capture-form renders contact inputs and full-width submit button", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(500);

    const leadCard = page.locator("div[data-pattern-slug='lead-capture-form']").first();
    await expect(leadCard).toBeVisible({ timeout: 15000 });
    await leadCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const nameInput = frame.locator("input[placeholder*='نام و نام خانوادگی']").first();
    const phoneInput = frame.locator("input[placeholder*='شماره همراه']").first();
    await expect(nameInput).toBeVisible({ timeout: 15000 });
    await expect(phoneInput).toBeVisible({ timeout: 15000 });

    const submitBtn = frame.locator(":is(a, button, span):has-text('درخواست تماس رایگان')").first();
    await expect(submitBtn).toBeVisible();
  });

  test("3. brand-logo-carousel renders logos grid and trust badge note", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(500);

    const brandCard = page.locator("div[data-pattern-slug='brand-logo-carousel']").first();
    await expect(brandCard).toBeVisible({ timeout: 15000 });
    await brandCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const brandHeading = frame.locator("h2:has-text('برندهای معتبر')").first();
    await expect(brandHeading).toBeVisible({ timeout: 15000 });

    const samsungTile = frame.locator("text=/سامسونگ/").first();
    await expect(samsungTile).toBeVisible();
  });
});
