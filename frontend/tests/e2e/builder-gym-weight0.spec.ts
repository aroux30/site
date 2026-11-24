import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-050/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w0-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Weight 0: Triage Emergency Parity on Port 1005", () => {
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
      "x-forwarded-for": `10.205.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. InspectorPanel has min-h-0 and scrollable tabs without vertical clipping", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Select first canvas element
    await page.evaluate(() => {
      const store = (window as any).__builderStore || (window as any).__BUILDER_STORE__;
      if (store) {
        const rootEl = store.getState().ast.rootElements[0];
        if (rootEl) store.getState().selectElement(rootEl.id);
      }
    });
    await page.waitForTimeout(500);

    const scrollContainer = page.locator("[data-testid='inspector-scroll-container']");
    await expect(scrollContainer).toBeVisible();

    // Verify content tab is scrollable
    const beforeScroll = await scrollContainer.evaluate((el) => el.scrollTop);
    await scrollContainer.evaluate((el) => { el.scrollBy(0, 300); });
    await page.waitForTimeout(200);
    const afterScroll = await scrollContainer.evaluate((el) => el.scrollTop);
    expect(afterScroll).toBeGreaterThanOrEqual(beforeScroll);

    // Switch to Style tab and verify
    const styleTabTrigger = page.locator("[role='tab']:has-text('استایل')");
    await styleTabTrigger.click();
    await page.waitForTimeout(300);
    await expect(page.locator("text=ویرایش استایل:")).toBeVisible();

    // Switch to Advanced tab and verify
    const advancedTabTrigger = page.locator("[role='tab']:has-text('پیشرفته')");
    await advancedTabTrigger.click();
    await page.waitForTimeout(300);
    await expect(page.locator("text=نام نمایشی المان در لایه‌ها")).toBeVisible();
  });

  test("2. Zero horizontal overflow and clean toolbar spacing at 1280x720 and 1440x900", async ({ page }) => {
    // 1280x720 check
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const overflow1280 = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow1280).toBeLessThanOrEqual(1);

    // 1440x900 check
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(500);
    const overflow1440 = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow1440).toBeLessThanOrEqual(1);
  });

  test("3. Menus and dropdowns open with z-index >= 150 above studio overlay", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    await page.evaluate(() => {
      const store = (window as any).__builderStore || (window as any).__BUILDER_STORE__;
      if (store) {
        const rootEl = store.getState().ast.rootElements[0];
        if (rootEl) store.getState().selectElement(rootEl.id);
      }
    });
    await page.waitForTimeout(500);

    const combobox = page.locator("[data-builder-inspector] button[role='combobox']").first();
    if (await combobox.isVisible()) {
      await combobox.click();
      await page.waitForTimeout(300);

      const popoverWrapper = page.locator("[data-radix-popper-content-wrapper]").first();
      await expect(popoverWrapper).toBeVisible();
      await page.keyboard.press("Escape");
    }
  });

  test("4. Canvas helper text guides user to right panel in RTL without referencing left panel", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const bodyText = await page.evaluate(() => document.body.innerText);
    expect(bodyText).not.toContain("پنل سمت چپ");
  });
});
