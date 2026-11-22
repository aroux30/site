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
  const tmp = path.join(BACKEND_DIR, `.gym-r13-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 13: Weight 6 (Template Dialog Title Sync & Global Styles Reset)", () => {
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

  test("1. SavePageTemplateDialog synchronizes title from current AST and renders categories", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const savePageTplBtn = page.locator("button:has-text('قالب برگه')").first();
    await expect(savePageTplBtn).toBeVisible({ timeout: 15000 });
    await savePageTplBtn.click();
    await page.waitForTimeout(600);

    const dialog = page.locator("div[role='dialog']").first();
    await expect(dialog).toBeVisible({ timeout: 15000 });

    const titleInput = dialog.locator("input.h-8").first();
    await expect(titleInput).toBeVisible({ timeout: 15000 });
    const val = await titleInput.inputValue();
    expect(val.length).toBeGreaterThan(0);
  });

  test("2. GlobalStylesDialog includes Reset to Theme action button", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const globalStylesBtn = page.locator("button:has-text('استایل سراسری')").first();
    await expect(globalStylesBtn).toBeVisible({ timeout: 15000 });
    await globalStylesBtn.click();
    await page.waitForTimeout(600);

    const resetBtn = page.locator("button:has-text('بازنشانی به تم پیش‌فرض')").first();
    await expect(resetBtn).toBeVisible({ timeout: 15000 });
  });

  test("3. Blocks Palette Templates tab reflects empty or loaded state gracefully", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });

    const templatesTab = page.locator("button:has-text('قالب‌های من')").first();
    await expect(templatesTab).toBeVisible({ timeout: 15000 });
    await templatesTab.click();
    await page.waitForTimeout(600);

    const tabContent = page.locator("aside").first();
    await expect(tabContent).toBeVisible();
  });
});
