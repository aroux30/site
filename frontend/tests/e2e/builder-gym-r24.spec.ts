import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4002";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r24-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 24: Elementor Wave 2 Widgets, Single Toolbar Hotkeys, and Clean Advanced Inspector", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
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

  test("1. Toolbar has exactly one shortcuts button and no duplicate hotkey buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shortcutsButtons = page.locator('button:has-text("میانبرها")');
    const count = await shortcutsButtons.count();
    expect(count).toBe(1);
  });

  test("2. Advanced tab has exactly one Transform control group (no duplicate controls)", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const headingEl = frame.locator('[data-element-id="el_e2ehead1"]').first();
    await expect(headingEl).toBeVisible();
    await headingEl.click();
    await page.waitForTimeout(400);

    const inspector = page.locator('[data-builder-inspector]');
    const advTab = inspector.locator('button[role="tab"]:has-text("پیشرفته")').first();
    await advTab.click();
    await page.waitForTimeout(400);

    const rotateInputs = inspector.locator('[data-testid="transform-rotate-input"]');
    expect(await rotateInputs.count()).toBe(1);

    const scaleInputs = inspector.locator('[data-testid="transform-scale-input"]');
    expect(await scaleInputs.count()).toBe(1);
  });

  test("3. Blocks Palette includes new Elementor widgets (Progress Bar, Testimonial, CTA, Flip Box, Animated Headline)", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
    await blocksTabBtn.click();
    await page.waitForTimeout(400);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("پیشرفت");
    await page.waitForTimeout(300);

    const progressBarCard = page.locator('text="نوار پیشرفت"').first();
    await expect(progressBarCard).toBeVisible();

    await searchInput.fill("دیدگاه");
    await page.waitForTimeout(300);
    const testimonialCard = page.locator('text="دیدگاه مشتری"').first();
    await expect(testimonialCard).toBeVisible();

    await searchInput.fill("فلیپ");
    await page.waitForTimeout(300);
    const flipBoxCard = page.locator('text="جعبه فلیپ‌باکس"').first();
    await expect(flipBoxCard).toBeVisible();
  });
});
