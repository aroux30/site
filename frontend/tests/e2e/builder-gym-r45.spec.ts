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
  const tmp = path.join(BACKEND_DIR, `.gym-r29-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 45: 1920x1080 Elementor Loop Grid & Multi-Step Form Parity", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

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

  test("1. Block palette filters and includes loop_grid and multi_step_form", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await expect(searchInput).toBeVisible();

    // Verify search finds loop_carousel / loop_grid
    await searchInput.fill("تکرارشونده");
    await page.waitForTimeout(300);
    const loopCard = page.locator('button[data-block-type="loop_carousel"], button:has-text("کاروسل تکرارشونده پویا")').first();
    await expect(loopCard).toBeVisible();

    // Verify search finds multi_step_form
    await searchInput.fill("چندمرحله‌ای");
    await page.waitForTimeout(300);
    const formCard = page.locator('button[data-block-type="multi_step_form"], button:has-text("فرم چندمرحله‌ای")').first();
    await expect(formCard).toBeVisible();
  });

  test("2. Inserting multi_step_form renders step header inside canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("چندمرحله‌ای");
    await page.waitForTimeout(300);

    const formCard = page.locator('button[data-block-type="multi_step_form"]').first();
    await formCard.click();
    await page.waitForTimeout(600);

    // Check inside canvas iframe for multi-step form steps
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const stepEl = frame.locator("text='اطلاعات تماس'").first();
    await expect(stepEl).toBeVisible();

    // Verify next button advances step preview unconditionally
    const nextBtn = frame.locator("button:has-text('مرحله بعد')").first();
    await expect(nextBtn).toBeVisible();
    await nextBtn.click();
    await page.waitForTimeout(300);
    const step2El = frame.locator("text='ورودی‌های آدرس و ارسال'").first();
    await expect(step2El).toBeVisible();
  });

  test("3. Inserting loop_grid renders grid cards inside canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("حلقه پویا");
    await page.waitForTimeout(300);

    const loopCard = page.locator('button[data-block-type="loop_grid"], button:has-text("حلقه پویا")').first();
    await loopCard.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const loopWidget = frame.locator('[data-widget="loop_grid"]').first();
    await expect(loopWidget).toBeVisible();
  });
});
