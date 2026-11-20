import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r07-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 07: Global Design Tokens, Width Presets & WYSIWYG Storefront Parity", () => {
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

  test("1. Global Styles Dialog includes color presets for both Primary and Secondary colors", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const globalStylesBtn = page.getByRole("button", { name: /استایل سراسری/i });
    await expect(globalStylesBtn).toBeVisible();
    await globalStylesBtn.click();
    await page.waitForTimeout(600);

    const dialog = page.locator("div[role='dialog']").first();
    await expect(dialog).toBeVisible();

    // Check secondary color presets are rendered
    const secondaryLabel = dialog.locator("text=رنگ مکمل / ثانویه (Secondary Color)");
    await expect(secondaryLabel).toBeVisible();

    // Swatches exist under secondary color
    const swatches = dialog.locator("div.space-y-1\\.5:has-text('Secondary Color') button");
    const count = await swatches.count();
    expect(count).toBeGreaterThanOrEqual(8);
  });

  test("2. Width token chips apply responsive dimensions with proper RTL labels", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await firstEl.click();
    await page.waitForTimeout(400);

    const styleTab = page.getByRole("tab", { name: "استایل" });
    await styleTab.click();
    await page.waitForTimeout(400);

    const container1280Chip = page.getByRole("button", { name: "۱۲۸۰ پیکسل (کانتینر)" });
    await expect(container1280Chip).toBeVisible();
    await container1280Chip.click();
    await page.waitForTimeout(400);

    const widthInput = page.locator("input[placeholder*='100% یا 1280px']");
    const val = await widthInput.inputValue();
    expect(val).toBe("1280px");
  });

  test("3. Published storefront page with builder_data renders full-width without redundant h1 header", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Redundant default header should NOT be present
    const redundantHeader = page.locator("article header h1.text-3xl");
    await expect(redundantHeader).toHaveCount(0);

    // Full-width builder content wrapper is rendered
    const builderContent = page.locator(".builder-rendered-content");
    await expect(builderContent).toBeVisible();
  });
});
