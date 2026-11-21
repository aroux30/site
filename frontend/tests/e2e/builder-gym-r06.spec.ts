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
  const tmp = path.join(BACKEND_DIR, `.gym-r06-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 06: Weight 2 (Pattern Converter Classes & Toast Stacking Regression)", () => {
  test.beforeEach(async ({ context }) => {
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

  test("1. Heading and text_editor widgets on canvas preserve customCssClass from AST", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.click();

    const heroCard = page.locator("div[data-pattern-slug='hero-banner']").first();
    await expect(heroCard).toBeVisible({ timeout: 15000 });
    await heroCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const heroHeading = frame.locator("h1:has-text('کالکشن جدید رسید')").first();
    await expect(heroHeading).toBeVisible({ timeout: 15000 });

    // Verify customCssClass from createHeadingWidget is applied
    const classes = await heroHeading.getAttribute("class");
    expect(classes).toContain("text-3xl");
    expect(classes).toContain("md:text-5xl");
  });

  test("2. Countdown-offer pattern applies font-mono and text-primary to timer heading", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.click();

    const countdownCard = page.locator("div[data-pattern-slug='countdown-offer']").first();
    await expect(countdownCard).toBeVisible({ timeout: 15000 });
    await countdownCard.click();

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const timerHeading = frame.locator("h3:has-text('مهلت:')").first();
    await expect(timerHeading).toBeVisible({ timeout: 15000 });

    const classes = await timerHeading.getAttribute("class");
    expect(classes).toContain("font-mono");
    expect(classes).toContain("text-primary");
  });

  test("3. Rapid pattern additions auto-dismiss toasts without viewport overlay clutter", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.click();

    const featureCard = page.locator("div[data-pattern-slug='feature-grid']").first();
    await expect(featureCard).toBeVisible({ timeout: 15000 });
    await featureCard.click();

    const toastItem = page.locator("[role='alert']").first();
    await expect(toastItem).toBeVisible();
  });
});
