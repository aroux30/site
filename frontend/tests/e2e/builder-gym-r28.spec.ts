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
  const tmp = path.join(BACKEND_DIR, `.gym-r28-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 28: Table Highlight Column and Form Field Customization", () => {
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

  test("1. Table widget provides highlight column selector in Inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("جدول داده");
    await page.waitForTimeout(300);

    const tableCard = page.locator('text="جدول داده"').first();
    await expect(tableCard).toBeVisible();
    await tableCard.click();
    await page.waitForTimeout(500);

    const inspector = page.locator('[data-builder-inspector]');
    const highlightColTrigger = inspector.locator('[data-testid="table-highlight-col-select"]');
    await expect(highlightColTrigger).toBeVisible();
    await highlightColTrigger.click();
    await page.waitForTimeout(300);

    // Pick column 2 (1-based index or option item)
    const opt = page.locator('[role="option"]:has-text("ستون ۲"), [role="option"]:has-text("ستون 2")').first();
    if (await opt.isVisible()) {
      await opt.click();
      await page.waitForTimeout(400);

      // Verify highlighted cell style exists on live canvas
      const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
      const highlightedTh = frame.locator('th.bg-primary\\/10').first();
      await expect(highlightedTh).toBeVisible();
    }
  });

  test("2. Form input provides required toggle and custom label", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("ورودی متن");
    await page.waitForTimeout(300);

    const inputCard = page.locator('text="فیلد ورودی متن"').first();
    await expect(inputCard).toBeVisible();
    await inputCard.click();
    await page.waitForTimeout(500);

    const inspector = page.locator('[data-builder-inspector]');
    const labelInput = inspector.locator('[data-testid="form-input-label-input"]');
    await expect(labelInput).toBeVisible();
    await labelInput.fill("شماره ملی متقاضی");
    await page.waitForTimeout(400);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    await expect(frame.locator('text="شماره ملی متقاضی"').first()).toBeVisible();
  });
});
