import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1004";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-50/after");

fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });

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
  const tmp = path.join(BACKEND_DIR, `.gym-r50-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 50: Inspector Scrolling & Menu Activation on Port 1004", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1004", httpOnly: false, sameSite: "Lax" },
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

  test("1. Inspector scrolling works smoothly on Content, Style and Advanced tabs", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // Click on "فرم سازنده" or "دکمه اقدام" in the blocks palette to insert and select it
    const addBtn = page.locator("button:has-text('دکمه اقدام')").first();
    await expect(addBtn).toBeVisible({ timeout: 10000 });
    await addBtn.click();
    await page.waitForTimeout(600);

    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector).toBeVisible();

    // Check Style Tab scroll
    const styleTab = page.locator('button[role="tab"]:has-text("استایل")').first();
    await styleTab.click();
    await page.waitForTimeout(400);

    const scrollContainer = inspector.locator(".builder-scrollbar").first();
    await expect(scrollContainer).toBeVisible();

    const metricsBefore = await scrollContainer.evaluate((el) => ({
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      scrollTop: el.scrollTop,
    }));
    expect(metricsBefore.scrollHeight).toBeGreaterThan(metricsBefore.clientHeight);

    // Scroll down
    await scrollContainer.evaluate((el) => { el.scrollTop = 500; });
    await page.waitForTimeout(300);

    const scrollTopAfter = await scrollContainer.evaluate((el) => el.scrollTop);
    expect(scrollTopAfter).toBeGreaterThan(0);

    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-inspector-style-scrolled.png") });

    // Check Advanced Tab scroll
    const advTab = page.locator('button[role="tab"]:has-text("پیشرفته")').first();
    await advTab.click();
    await page.waitForTimeout(400);

    const advMetrics = await scrollContainer.evaluate((el) => ({
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
    }));
    expect(advMetrics.scrollHeight).toBeGreaterThan(advMetrics.clientHeight);

    await scrollContainer.evaluate((el) => { el.scrollTop = 600; });
    await page.waitForTimeout(300);
    const advScrollAfter = await scrollContainer.evaluate((el) => el.scrollTop);
    expect(advScrollAfter).toBeGreaterThan(0);

    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "02-inspector-advanced-scrolled.png") });
  });

  test("2. Select menus open and appear above inspector (z-index verified)", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Insert a heading to inspect tag select menu
    const addHeading = page.locator("button[data-block-type='heading']").first();
    await expect(addHeading).toBeVisible({ timeout: 10000 });
    await addHeading.click();
    await page.waitForTimeout(600);

    const inspector = page.locator("[data-builder-inspector]");
    const selectTrigger = inspector.locator("button[role='combobox']").first();
    await expect(selectTrigger).toBeVisible();
    await selectTrigger.click();
    await page.waitForTimeout(500);

    // Verify dropdown content is visible and has z-index >= 120
    const selectContent = page.locator("[role='listbox']").first();
    await expect(selectContent).toBeVisible();

    const zIndex = await selectContent.evaluate((el) => window.getComputedStyle(el).zIndex);
    expect(parseInt(zIndex, 10)).toBeGreaterThanOrEqual(120);

    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "03-select-dropdown-open.png") });
  });

  test("3. Multi-step form widget configuration and step addition works in inspector", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Search for multi_step_form in blocks
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("فرم چندمرحله‌ای");
    await page.waitForTimeout(300);

    const formBlockBtn = page.locator("button:has-text('فرم چندمرحله‌ای')").first();
    await expect(formBlockBtn).toBeVisible();
    await formBlockBtn.click();
    await page.waitForTimeout(600);

    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector).toBeVisible();

    // Verify step inputs in Content tab
    const curStepInput = inspector.locator('[data-testid="step-form-cur-input"]');
    await expect(curStepInput).toBeVisible();

    // Add step button
    const addStepBtn = inspector.locator("button:has-text('+ افزودن مرحله')");
    await expect(addStepBtn).toBeVisible();
    await addStepBtn.click();
    await page.waitForTimeout(300);

    // Now 4 steps should be present
    await expect(inspector.locator("input[value='مرحله 4']")).toBeVisible();

    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "04-multi-step-form-inspector.png") });
  });
});
