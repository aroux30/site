import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1004";
const BACKEND_DIR = path.resolve(__dirname, "../../../backend");
const ARTIFACTS_DIR = path.resolve(__dirname, "../../../.loop/artifacts/builder-gym/round-59/after");
fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });

function getAdminToken() {
  const script = `
import sys; sys.path.insert(0, ".")
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
  const tmp = path.join(BACKEND_DIR, `.gym-r59-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 59: Weight 4 Elementor Experience, Shortcuts, Templates & WYSIWYG Parity", () => {
  test.use({ viewport: { width: 1280, height: 720 } });

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
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
        })
      );
    });
  });

  test("1. Verify Shortcuts dialog, Page Template dialog, Save Draft and Preview Mode toggle", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // 1. Open Shortcuts Help Dialog
    const shortcutsBtn = page.locator('[data-testid="shortcuts-help-btn"]').first();
    await expect(shortcutsBtn).toBeVisible();
    await shortcutsBtn.click();
    await page.waitForTimeout(300);

    const shortcutsModal = page.locator("text=راهنمای کلیدهای میانبر");
    await expect(shortcutsModal).toBeVisible();
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);

    // 2. Open Save Page Template Dialog
    const savePageTemplateBtn = page.locator('[data-testid="save-page-template-btn"]').first();
    await expect(savePageTemplateBtn).toBeVisible();
    await savePageTemplateBtn.click();
    await page.waitForTimeout(300);

    const tplModal = page.locator("text=ذخیره کل برگه به عنوان قالب");
    await expect(tplModal).toBeVisible();
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);

    // 3. Test Preview Mode Toggle
    const previewBtn = page.locator('button[title*="پیش‌نمایش"], button[title*="ویرایش"]').first();
    await expect(previewBtn).toBeVisible();
    await previewBtn.click();
    await page.waitForTimeout(400);

    // Inspector should be hidden in preview mode
    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector).not.toBeVisible();

    // Toggle back to Edit Mode
    await previewBtn.click();
    await page.waitForTimeout(400);

    // 4. Save Draft Button and Status Indicator
    const saveDraftBtn = page.locator("button:has-text('ذخیره پیش‌نویس')").first();
    await expect(saveDraftBtn).toBeVisible();
    await saveDraftBtn.click();
    await page.waitForTimeout(500);

    // 5. Canvas verification
    const frame = page.frameLocator('[data-testid="canvas-iframe"]');
    const rootContainer = frame.locator('[data-element-id]').first();
    await expect(rootContainer).toBeVisible();
  });
});
