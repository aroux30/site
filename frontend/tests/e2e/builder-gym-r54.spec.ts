import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1001";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-50/after");

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

test.describe("Builder Gym Round 50: Custom Attributes 4-Layer Parity & SSR Verification", () => {
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

  test("1. Custom Attributes textarea updates canvas live and preserves data in inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Verify studio loaded
    await expect(page.locator("text=ذخیره پیش‌نویس")).toBeVisible();

    // 1. Search in blocks palette
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("مسیر راهنما");
    await page.waitForTimeout(300);

    const crumbCard = page.locator('text="مسیر راهنما"').first();
    await expect(crumbCard).toBeVisible();

    // 2. Click to add breadcrumbs widget to canvas
    await crumbCard.click();
    await page.waitForTimeout(600);

    // 3. Switch to Advanced tab in inspector
    const advTab = page.locator('[role="tab"]:has-text("پیشرفته")').first();
    await expect(advTab).toBeVisible();
    await advTab.click();
    await page.waitForTimeout(400);

    // 4. Verify Custom Attributes control is visible
    const customAttrControl = page.locator('[data-testid="custom-attributes-control"]').first();
    await expect(customAttrControl).toBeVisible();

    const textarea = page.locator('[data-testid="custom-attributes-textarea"]').first();
    await expect(textarea).toBeVisible();

    // 5. Fill custom attributes
    await textarea.fill("data-analytics-category|hero-cta\naria-label|test-hero-heading");
    await page.waitForTimeout(500);

    // Verify value is preserved in textarea
    expect(await textarea.inputValue()).toContain("data-analytics-category|hero-cta");

    // 6. Verify live canvas iframe reflects custom attribute
    const frame = page.frameLocator('[data-testid="canvas-iframe"]');
    const customAttrEl = frame.locator('[data-analytics-category="hero-cta"]').first();
    await expect(customAttrEl).toBeVisible();
  });
});
