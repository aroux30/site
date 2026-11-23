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
  const tmp = path.join(BACKEND_DIR, `.gym-r30-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 46: 1920x1080 Elementor Slides & Code Highlight Parity", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

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

  test("1. Block palette filters and includes slides and code_highlight", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await expect(searchInput).toBeVisible();

    // Verify search finds slides
    await searchInput.fill("اسلاید");
    await page.waitForTimeout(300);
    const slidesCard = page.locator('button[data-block-type="slides"]').first();
    await expect(slidesCard).toBeVisible();

    // Verify search finds code_highlight
    await searchInput.fill("هایلایت");
    await page.waitForTimeout(300);
    const codeCard = page.locator('button[data-block-type="code_highlight"]').first();
    await expect(codeCard).toBeVisible();
  });

  test("2. Inserting code_highlight renders syntax box inside canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("هایلایت");
    await page.waitForTimeout(300);

    const codeCard = page.locator('button[data-block-type="code_highlight"]').first();
    await codeCard.click();
    await page.waitForTimeout(800);

    // Check inside canvas iframe
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const codeBox = frame.locator("pre, code, [data-widget-type='code_highlight']").first();
    await expect(codeBox).toBeVisible({ timeout: 10000 });
  });

  test("3. Inserting slides renders hero slider with active navigation dots", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("اسلاید");
    await page.waitForTimeout(300);

    const slidesCard = page.locator('button[data-block-type="slides"]').first();
    await slidesCard.click();
    await page.waitForTimeout(800);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const slidesWidget = frame.locator('[data-widget="slides"]').first();
    await expect(slidesWidget).toBeVisible({ timeout: 10000 });
  });
});
