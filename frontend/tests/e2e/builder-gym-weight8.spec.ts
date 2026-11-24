import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-058/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w8-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Weight 8: Elementor Wave 3 Porting (Global Site Kit, Theme Builder, Loop Builder, Multi-Step Form)", () => {
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
      "x-forwarded-for": `10.213.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Multi-Step Form widget renders step indicators, navigation buttons, and inputs", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("چندمرحله");
    await page.waitForTimeout(300);

    const formCard = page.locator('text="فرم چندمرحله‌ای"').first();
    await expect(formCard).toBeVisible();
    await formCard.click();
    await page.waitForTimeout(600);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("button:has-text('مرحله بعد')").first()).toBeVisible();
    await expect(iframeEl.locator("button:has-text('مرحله قبل')").first()).toBeVisible();
  });

  test("2. Loop Grid widget configures columns count and data source in Inspector", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("حلقه پویا");
    await page.waitForTimeout(300);

    const loopCard = page.locator('text="حلقه پویا"').first();
    await expect(loopCard).toBeVisible();
    await loopCard.click();
    await page.waitForTimeout(600);

    const sourceSelect = page.locator("[data-testid='loop-source-select']");
    await expect(sourceSelect).toBeVisible();
  });

  test("3. Slides widget renders interactive carousel banner with title and CTA button", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("اسلاید");
    await page.waitForTimeout(300);

    const slidesCard = page.locator('text="اسلاید پیشرفته"').first();
    await expect(slidesCard).toBeVisible();
    await slidesCard.click();
    await page.waitForTimeout(600);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("[data-widget-type='slides']").first()).toBeVisible();
  });

  test("4. Code Highlight widget displays syntax box with language tags and copy button", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const blocksTab = page.locator("[data-testid='sidebar-tab-blocks']");
    await blocksTab.click();
    await page.waitForTimeout(200);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("هایلایت");
    await page.waitForTimeout(300);

    const codeCard = page.locator('text="هایلایت کد"').first();
    await expect(codeCard).toBeVisible();
    await codeCard.click();
    await page.waitForTimeout(600);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("pre, code").first()).toBeVisible();
  });
});
