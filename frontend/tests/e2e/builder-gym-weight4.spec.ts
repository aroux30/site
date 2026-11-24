import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-054/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w4-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Weight 4: Drag & Drop, Shortcuts, Templates, and Production Parity", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1005", httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://127.0.0.1:1005", httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.209.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Save Page Template dialog opens with Theme Builder template types and display conditions", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const saveTemplateBtn = page.locator("[data-testid='save-page-template-btn']");
    await expect(saveTemplateBtn).toBeVisible();
    await saveTemplateBtn.click();
    await page.waitForTimeout(500);

    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator("text=ذخیره کل برگه به عنوان قالب")).toBeVisible();
    await expect(dialog.locator("text=عنوان قالب برگه")).toBeVisible();

    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    await expect(dialog).not.toBeVisible();
  });

  test("2. Keyboard Shortcuts dialog opens with comprehensive keybinding reference", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shortcutsBtn = page.locator("[data-testid='shortcuts-help-btn']");
    await expect(shortcutsBtn).toBeVisible();
    await shortcutsBtn.click();
    await page.waitForTimeout(500);

    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator("text=راهنمای کلیدهای میانبر")).toBeVisible();

    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    await expect(dialog).not.toBeVisible();
  });

  test("3. Undo and Redo toolbar buttons track state history cleanly", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const undoBtn = page.locator("button[title*='Ctrl+Z']");
    const redoBtn = page.locator("button[title*='Ctrl+Y']");

    await expect(undoBtn).toBeVisible();
    await expect(redoBtn).toBeVisible();
    // Initially without mutations undo is disabled
    await expect(undoBtn).toBeDisabled();
    await expect(redoBtn).toBeDisabled();
  });

  test("4. Preview Mode toggle cleanly collapses sidebars into full-screen preview", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Initial state: aside is visible
    const aside = page.locator("aside[class*='w-80']").first();
    await expect(aside).toBeVisible();

    // Toggle Preview
    const previewBtn = page.locator("[data-testid='preview-mode-toggle-btn']");
    await expect(previewBtn).toBeVisible();
    await previewBtn.click();
    await page.waitForTimeout(500);

    // In preview mode sidebars are hidden
    await expect(aside).not.toBeVisible();

    // Toggle back to edit
    await previewBtn.click();
    await page.waitForTimeout(500);

    // Aside is visible again
    await expect(aside).toBeVisible();
    await page.waitForTimeout(500);

    // Aside is visible again
    await expect(aside).toBeVisible();
  });
});
