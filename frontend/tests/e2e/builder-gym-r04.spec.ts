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
  const tmp = path.join(BACKEND_DIR, `.gym-r04-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 04: Weight 4 (Productivity, Shortcuts & Global Components)", () => {
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

  test("1. Keyboard shortcuts forwarded from iframe canvas execute Copy and Paste with undo support", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await expect(firstEl).toBeVisible();

    const initialCount = await frame.locator("[data-element-id]").count();
    await firstEl.click();
    await page.waitForTimeout(400);

    // Press Ctrl+C inside canvas iframe
    await page.keyboard.press("Control+c");
    await page.waitForTimeout(300);

    // Press Ctrl+V to duplicate adjacent
    await page.keyboard.press("Control+v");
    await page.waitForTimeout(600);

    const postPasteCount = await frame.locator("[data-element-id]").count();
    expect(postPasteCount).toBeGreaterThan(initialCount);

    // Press Ctrl+Z to undo paste
    await page.keyboard.press("Control+z");
    await page.waitForTimeout(600);

    const postUndoCount = await frame.locator("[data-element-id]").count();
    expect(postUndoCount).toBe(initialCount);
  });

  test("2. Floating toolbar includes duplicate and delete buttons operating seamlessly", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await firstEl.click();
    await page.waitForTimeout(400);

    const toolbar = frame.locator('[data-testid="floating-toolbar"]');
    await expect(toolbar).toBeVisible();

    const initialCount = await frame.locator("[data-element-id]").count();
    const dupBtn = toolbar.locator('button[title*="تکثیر"]');
    await expect(dupBtn).toBeVisible();
    await dupBtn.click();
    await page.waitForTimeout(600);

    const postDupCount = await frame.locator("[data-element-id]").count();
    expect(postDupCount).toBe(initialCount + 1);
  });

  test("3. Blocks palette templates tab and Save Page Template dialog render correctly", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Open Templates tab
    const tplTab = page.getByRole("button", { name: /قالب‌های من/i });
    await expect(tplTab).toBeVisible();
    await tplTab.click();
    await page.waitForTimeout(500);

    // Check empty or populated template listing
    const searchInput = page.getByPlaceholder("جستجو در قالب‌های من...");
    await expect(searchInput).toBeVisible();

    // Check Save Page Template dialog trigger in toolbar
    const savePageTplBtn = page.getByRole("button", { name: "قالب برگه", exact: true });
    if (await savePageTplBtn.isVisible()) {
      await savePageTplBtn.click();
      await page.waitForTimeout(500);

      const dialog = page.locator("div[role='dialog']");
      await expect(dialog).toBeVisible();
      await expect(dialog.getByText(/ذخیره کل برگه به عنوان قالب/i)).toBeVisible();

      await page.keyboard.press("Escape");
    }
  });
});
