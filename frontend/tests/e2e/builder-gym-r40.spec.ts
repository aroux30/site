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
  const tmp = path.join(BACKEND_DIR, `.gym-r40-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 40: 1920x1080 Viewport Full Studio & Code Highlight Parity", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

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

  test("1. Full Studio 3-zone layout (Right, Center, Left) is accessible and responsive at 1920x1080", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Verify Right Column (Blocks palette, Layers, History)
    const rightSidebar = page.locator('aside').filter({ hasText: "بلوک‌ها" }).first();
    await expect(rightSidebar).toBeVisible();

    const layersTabBtn = page.locator('[data-testid="sidebar-tab-layers"]');
    await expect(layersTabBtn).toBeVisible();
    await layersTabBtn.click();
    await page.waitForTimeout(300);

    const historyTabBtn = page.locator('[data-testid="history-tab-btn"]');
    await expect(historyTabBtn).toBeVisible();
    await historyTabBtn.click();
    await page.waitForTimeout(300);

    const blocksTabBtn = page.locator('button[title="افزودن بلوک"]');
    await expect(blocksTabBtn).toBeVisible();
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    // Verify Center Column (Canvas iframe)
    const canvasFrame = page.locator('iframe[title="Visual Builder Canvas"]');
    await expect(canvasFrame).toBeVisible();

    // Verify Left Column (Inspector Panel)
    const inspector = page.locator('[data-builder-inspector]');
    await expect(inspector).toBeVisible();
  });

  test("2. Code Highlight widget can be added and customized in Inspector and reflects in Live Canvas at 1920x1080", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("کد");
    await page.waitForTimeout(400);

    const codeCard = page.locator('[data-block-type="code_highlight"]').first();
    await expect(codeCard).toBeVisible();
    await codeCard.click();
    await page.waitForTimeout(600);

    const inspector = page.locator('[data-builder-inspector]');
    const titleInput = inspector.locator('[data-testid="code-title-input"]');
    await expect(titleInput).toBeVisible();
    await titleInput.fill("script.py");
    await page.waitForTimeout(300);

    const codeTextarea = inspector.locator('[data-testid="code-content-textarea"]');
    await expect(codeTextarea).toBeVisible();
    await codeTextarea.fill('print("Hello from Round 40 in 1920x1080!")');
    await page.waitForTimeout(400);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    await expect(frame.locator('text="script.py"').first()).toBeVisible();
    await expect(frame.getByText("Hello from Round 40").first()).toBeVisible();
  });
});
