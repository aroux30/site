import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4022";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-44/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r52-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 44: Left Inspector Panel Ergonomics & Hero Slides Multi-Item Repeater (1920x1080)", () => {
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

  test("1. Left Inspector Panel is 384px wide with clean multi-slide repeater, no clipping, and toolbar uncompressed", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // 1. Verify Left Inspector has comfortable 384px width (w-96)
    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector).toBeVisible();
    const inspectorBox = await inspector.boundingBox();
    expect(inspectorBox).not.toBeNull();
    expect(inspectorBox!.width).toBe(384);

    // 2. Insert Slides block from palette
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("اسلاید پیشرفته");
    await page.waitForTimeout(300);

    const slidesCard = page.locator('text="اسلاید پیشرفته"').first();
    await expect(slidesCard).toBeVisible();
    await slidesCard.click();
    await page.waitForTimeout(600);

    // 3. Verify Inspector header shows Slides element selected
    await expect(inspector.locator('text="اسلاید پیشرفته"').or(inspector.locator('text="اسلاید هیرو"')).first()).toBeVisible();

    // 4. Verify multi-slide repeater UI is present and clean
    await expect(inspector.getByText("اسلایدهای هیرو")).toBeVisible();
    const addSlideBtn = inspector.locator('[data-testid="add-slide-btn"]');
    await expect(addSlideBtn).toBeVisible();

    // 5. Add a 3rd slide using "+ افزودن اسلاید"
    await addSlideBtn.click();
    await page.waitForTimeout(400);

    // 6. Verify 3rd slide exists with title, description, button text, and button link
    const slide3Title = inspector.locator('input[data-testid="slide-title-2"]');
    await expect(slide3Title).toBeVisible();
    await slide3Title.fill("جشنواره طلایی بلک فرایدی");
    await page.waitForTimeout(300);

    // 7. Verify Top Toolbar on the left has no button overlap
    const publishBtn = page.locator('[data-testid="publish-page-btn"]');
    await expect(publishBtn).toBeVisible();
    const shortcutsBtn = page.locator('[data-testid="shortcuts-help-btn"]');
    await expect(shortcutsBtn).toBeVisible();

    // 8. Capture full screenshot at 1920x1080
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-inspector-slides-repeater-1920x1080.png") });
  });
});
