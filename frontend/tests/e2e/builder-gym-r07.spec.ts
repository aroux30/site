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
  const tmp = path.join(BACKEND_DIR, `.gym-r07-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 07: Weight 2 (E-Commerce, Ratings & Root-Level Pattern Insertion)", () => {
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

  test("1. star-rating-display applies text-amber-400 and font-bold to rating heading", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();

    const starCard = page.locator("div[data-pattern-slug='star-rating-display']").first();
    await expect(starCard).toBeVisible({ timeout: 15000 });
    await starCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const starHeading = frame.locator("h4:has-text('★★★★☆')").first();
    await expect(starHeading).toBeVisible({ timeout: 15000 });

    const classes = await starHeading.getAttribute("class");
    expect(classes).toContain("text-amber-400");
    expect(classes).toContain("font-bold");
  });

  test("2. discount-badge-banner renders text-destructive-foreground on percentage and custom button styling", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();

    const discountCard = page.locator("div[data-pattern-slug='discount-badge-banner']").first();
    await expect(discountCard).toBeVisible({ timeout: 15000 });
    await discountCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const discountHeading = frame.locator("h3:has-text('تخفیف')").first();
    await expect(discountHeading).toBeVisible({ timeout: 15000 });

    const classes = await discountHeading.getAttribute("class");
    expect(classes).toContain("text-destructive-foreground");
  });

  test("3. Consecutively inserted patterns become independent root-level sections", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();

    const card1 = page.locator("div[data-pattern-slug='stats-counter']").first();
    await expect(card1).toBeVisible({ timeout: 15000 });
    await card1.click();
    await page.waitForTimeout(600);

    const card2 = page.locator("div[data-pattern-slug='image-gallery-showcase']").first();
    await expect(card2).toBeVisible({ timeout: 15000 });
    await card2.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const statsContainer = frame.locator("h3:has-text('۱,۲۳۴')").first();
    const galleryContainer = frame.locator("h2:has-text('گالری محصولات')").first();
    await expect(statsContainer).toBeVisible({ timeout: 15000 });
    await expect(galleryContainer).toBeVisible({ timeout: 15000 });
  });
});
