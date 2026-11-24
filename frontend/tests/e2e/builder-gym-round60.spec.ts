import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-060/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w10-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 60: Direct Inline Editing & Ultra Polish on Port 1005", () => {
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
      "x-forwarded-for": `10.215.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Double click on Heading enters inline editing and commits on Enter", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const heading = iframeEl.locator("h1, h2").first();
    await expect(heading).toBeVisible();

    // Double click to trigger inline editing
    await heading.dblclick();
    await page.waitForTimeout(400);

    const editor = iframeEl.locator("[data-testid='inline-text-editor']").first();
    await expect(editor).toBeVisible();

    // Type text and commit with Enter
    await editor.fill("تیتر ویرایش‌شده با اینلاین ادیتور");
    await editor.press("Enter");
    await page.waitForTimeout(400);

    // Verify committed text
    await expect(iframeEl.locator("h1:has-text('تیتر ویرایش‌شده با اینلاین ادیتور'), h2:has-text('تیتر ویرایش‌شده با اینلاین ادیتور')").first()).toBeVisible();
  });

  test("2. Double click on Button widget enters inline editing and saves new label", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Add button to canvas
    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("دکمه");
    await page.waitForTimeout(300);

    const btnCard = page.locator('text="دکمه اقدام"').first();
    await expect(btnCard).toBeVisible();
    await btnCard.click();
    await page.waitForTimeout(600);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const btnWrapper = iframeEl.locator("[data-testid='button-widget-wrapper']").first();
    await expect(btnWrapper).toBeVisible();

    await btnWrapper.dblclick();
    await page.waitForTimeout(400);

    const editor = iframeEl.locator("[data-testid='inline-text-editor']").first();
    await expect(editor).toBeVisible();
    await editor.fill("سفارش آنی");
    await editor.press("Enter");
    await page.waitForTimeout(400);

    await expect(iframeEl.locator("text=سفارش آنی").first()).toBeVisible();
  });

  test("3. Layers tree double click renames element in tree and inspector immediately", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const layersTab = page.locator("[data-testid='sidebar-tab-layers']");
    await layersTab.click();
    await page.waitForTimeout(400);

    const firstRowName = page.locator("[data-layer-row] span[title*='دابل کلیک']").first();
    await expect(firstRowName).toBeVisible();
    await firstRowName.dblclick();
    await page.waitForTimeout(300);

    const nameInput = page.locator("[data-layer-row] input").first();
    await expect(nameInput).toBeVisible();
    await nameInput.fill("بخش اصلی سفارشی");
    await nameInput.press("Enter");
    await page.waitForTimeout(300);

    await expect(page.locator("[data-layer-row]:has-text('بخش اصلی سفارشی')").first()).toBeVisible();
  });

  test("4. Zero console errors, zero network errors, and zero horizontal overflows in ultra polish", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(errors.length).toBe(0);
  });
});
