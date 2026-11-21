import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4001";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r22-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 22: Elementor Core & Pro Widget Palette & Inspector Parity", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:4001", httpOnly: false, sameSite: "Lax" },
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

  test("1. Block palette includes new Elementor widgets (progress_bar, testimonial, call_to_action, flip_box, menu_anchor)", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Verify search finds progress bar
    const searchInput = page.locator('input[placeholder*="جستجو"]');
    await expect(searchInput).toBeVisible();
    await searchInput.fill("پیشرفت");
    await page.waitForTimeout(300);

    const progressBarBlock = page.locator('button:has-text("نوار پیشرفت")');
    await expect(progressBarBlock).toBeVisible();

    // Verify search finds testimonial
    await searchInput.fill("مشتری");
    await page.waitForTimeout(300);
    const testimonialBlock = page.locator('button:has-text("نظر مشتری")');
    await expect(testimonialBlock).toBeVisible();

    // Verify search finds CTA
    await searchInput.fill("اقدام");
    await page.waitForTimeout(300);
    const ctaBlock = page.locator('button:has-text("فراخوان اقدام")');
    await expect(ctaBlock).toBeVisible();

    // Verify search finds flip box
    await searchInput.fill("چرخان");
    await page.waitForTimeout(300);
    const flipBoxBlock = page.locator('button:has-text("جعبه چرخان")');
    await expect(flipBoxBlock).toBeVisible();

    // Verify search finds menu anchor
    await searchInput.fill("لنگر");
    await page.waitForTimeout(300);
    const anchorBlock = page.locator('button:has-text("لنگر منو")');
    await expect(anchorBlock).toBeVisible();
  });

  test("2. Inspector and toolbar duplicates cleaned up; shortcuts button single instance", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Single shortcuts help button in toolbar
    const shortcutsButtons = page.locator('button[data-testid="shortcuts-help-btn"]');
    await expect(shortcutsButtons).toHaveCount(1);
    await expect(shortcutsButtons).toBeVisible();

    // Select first heading element
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const headingEl = frame.locator('[data-element-id="el_e2ehead1"]').first();
    await expect(headingEl).toBeVisible();
    await headingEl.click();
    await page.waitForTimeout(400);

    // Go to advanced tab
    const advTab = page.locator('button[data-state]:has-text("پیشرفته"), button:has-text("پیشرفته")').first();
    await advTab.click();
    await page.waitForTimeout(400);

    // Verify custom attributes control exists
    const customAttrControl = page.locator('[data-testid="custom-attributes-textarea"]');
    await expect(customAttrControl).toBeVisible();
  });
});
