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
  const tmp = path.join(BACKEND_DIR, `.gym-r03-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 03: Weight 3 (Inspector & Global Styles Regression)", () => {
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

  test("1. Global Styles Dialog displays properly above studio without z-index clipping", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const globalStylesBtn = page.getByRole("button", { name: "استایل سراسری" });
    await expect(globalStylesBtn).toBeVisible();
    await globalStylesBtn.click();
    await page.waitForTimeout(600);

    const dialog = page.locator("div[role='dialog']").first();
    await expect(dialog).toBeVisible();

    const title = dialog.locator("text=استایل سراسری برگه");
    await expect(title).toBeVisible();

    // Verify reset to site theme button is present
    const resetBtn = dialog.locator("button:has-text('بازنشانی به تم پیش‌فرض')");
    await expect(resetBtn).toBeVisible();
  });

  test("2. Inspector Tab switching updates controls immediately for active element", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await firstEl.click();
    await page.waitForTimeout(500);

    // Switch to style tab
    const styleTab = page.getByRole("tab", { name: "استایل" });
    await styleTab.click();
    await page.waitForTimeout(400);

    const paddingLabel = page.locator("text=فاصله داخلی (Padding)");
    await expect(paddingLabel).toBeVisible();

    // Switch to advanced tab
    const advTab = page.getByRole("tab", { name: "پیشرفته" });
    await advTab.click();
    await page.waitForTimeout(400);

    const visibilityLabel = page.locator("text=نمایش بر اساس نوع دستگاه");
    await expect(visibilityLabel).toBeVisible();
  });

  test("3. Background token selection updates active device style", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await firstEl.click();

    const styleTab = page.getByRole("tab", { name: "استایل" });
    await styleTab.click();
    await page.waitForTimeout(400);

    const bgTokenPrimary = page.locator("button:has-text('رنگ اصلی')").first();
    await expect(bgTokenPrimary).toBeVisible();
    await bgTokenPrimary.click();
    await page.waitForTimeout(500);

    // Background input should have var(--primary)
    const bgInput = page.locator("input[placeholder*='var(--primary)']").first();
    const val = await bgInput.inputValue();
    expect(val).toContain("var(--primary)");
  });
});
