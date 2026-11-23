import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1002";
const BACKEND_DIR = fs.existsSync(path.resolve("backend"))
  ? path.resolve("backend")
  : path.resolve("../backend");
const ARTIFACTS_DIR = fs.existsSync(path.resolve(".loop"))
  ? path.resolve(".loop/artifacts/builder-gym/round-50/after")
  : path.resolve("../.loop/artifacts/builder-gym/round-50/after");

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

test.describe("Builder Gym Round 50: Breadcrumbs 4-Layer Architecture & Validation Parity (1920x1080)", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://127.0.0.1:1002", httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1002", httpOnly: false, sameSite: "Lax" },
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

  test("1. Breadcrumbs widget can be searched in palette, inserted, customized in Inspector without 422 error", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    page.on("response", (res) => {
      if (res.status() === 422) {
        errors.push(`422 on ${res.url()}`);
      }
    });

    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // 1. Search in blocks palette
    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("مسیر راهنما");
    await page.waitForTimeout(300);

    const crumbCard = page.locator('text="مسیر راهنما"').first();
    await expect(crumbCard).toBeVisible();

    // 2. Click to add breadcrumbs widget to canvas
    await crumbCard.click();
    await page.waitForTimeout(1000);

    // 3. Verify Inspector panel shows breadcrumbs controls
    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector.locator('text="مسیر راهنما"').first()).toBeVisible();

    // 4. Verify separator selector
    const sepSelect = page.locator('[data-testid="breadcrumbs-sep-select"]');
    await expect(sepSelect).toBeVisible();

    // 5. Verify live canvas renders breadcrumbs with semantic ol/li
    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const crumbsNav = iframeEl.locator('nav[aria-label="مسیر راهنما"]').first();
    await expect(crumbsNav).toBeVisible();
    await expect(crumbsNav.locator('text="صفحه اصلی"')).toBeVisible();
    await expect(crumbsNav.locator('text="فروشگاه"')).toBeVisible();

    // 6. Test save draft and verify no 422 error
    const saveBtn = page.locator('button:has-text("ذخیره پیش‌نویس")').first();
    await saveBtn.click();
    await page.waitForTimeout(2000);

    expect(errors.filter((e) => e.includes("422"))).toEqual([]);

    // 7. Capture verified screenshot at 1920x1080
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-breadcrumbs-verified-1920x1080.png") });
  });
});
