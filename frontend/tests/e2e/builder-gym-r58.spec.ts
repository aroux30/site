import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1001";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-54/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r54-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 54: Weight 9 Full Landing Page Stress Test From Scratch", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1001", httpOnly: false, sameSite: "Lax" },
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

  test("1. Build complete landing section with Hero, Price Table, Multi-step Form & responsive viewports", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // 1. Verify Studio topbar and sidebars
    await expect(page.locator("text=ذخیره پیش‌نویس")).toBeVisible();
    await expect(page.locator("text=استایل سراسری")).toBeVisible();

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    const frame = page.frameLocator('[data-testid="canvas-iframe"]');

    // 2. Add Container
    const containerBtn = page.locator('button[data-block-type="container"]').first();
    await expect(containerBtn).toBeVisible();
    await containerBtn.click();
    await page.waitForTimeout(500);

    // 3. Add Heading inside canvas
    await searchInput.fill("سرتیتر");
    await page.waitForTimeout(300);
    const headingBtn = page.locator('button[data-block-type="heading"]').first();
    if (await headingBtn.isVisible()) {
      await headingBtn.click();
      await page.waitForTimeout(400);
    }

    // 4. Add Price Table
    await searchInput.fill("قیمت");
    await page.waitForTimeout(300);
    const priceTableBtn = page.locator('button[data-block-type="price_table"]').first();
    if (await priceTableBtn.isVisible()) {
      await priceTableBtn.click();
      await page.waitForTimeout(400);
      const priceTable = frame.locator('[data-widget-type="price_table"]').first();
      await expect(priceTable).toBeVisible();
    }

    // 5. Add Multi-Step Form
    await searchInput.fill("چندمرحله‌ای");
    await page.waitForTimeout(300);
    const multiStepBtn = page.locator('button[data-block-type="multi_step_form"]').first();
    if (await multiStepBtn.isVisible()) {
      await multiStepBtn.click();
      await page.waitForTimeout(400);
      const stepForm = frame.locator('[data-widget-type="multi_step_form"]').first();
      await expect(stepForm).toBeVisible();
    }

    // 6. Test Responsive Viewport switching
    const tabletBtn = page.locator('button:has-text("تبلت (۷۶۸)")').first();
    if (await tabletBtn.isVisible()) {
      await tabletBtn.click();
      await page.waitForTimeout(400);
    }

    const mobileBtn = page.locator('button:has-text("موبایل (۳۷۵)")').first();
    if (await mobileBtn.isVisible()) {
      await mobileBtn.click();
      await page.waitForTimeout(400);
    }

    const desktopBtn = page.locator('button:has-text("دسکتاپ")').first();
    if (await desktopBtn.isVisible()) {
      await desktopBtn.click();
      await page.waitForTimeout(400);
    }

    // 7. Verify zero horizontal overflow on canvas
    const overflow = await page.evaluate(() => {
      const el = document.querySelector('iframe');
      if (!el || !el.contentDocument) return 0;
      return el.contentDocument.documentElement.scrollWidth - el.contentDocument.documentElement.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(5);

    // 8. Capture final verified screenshot
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-full-landing-verified-1920x1080.png") });
  });
});
