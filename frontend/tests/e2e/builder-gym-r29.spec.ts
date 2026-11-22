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
  const tmp = path.join(BACKEND_DIR, `.gym-r29-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 29: Form Checkbox and Radio 4-Layer Synchronization", () => {
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

  test("1. Form checkbox can be inserted from palette and customized in Inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("چک‌باکس");
    await page.waitForTimeout(300);

    const chkCard = page.locator('text="چک‌باکس فرم"').first();
    await expect(chkCard).toBeVisible();
    await chkCard.click();
    await page.waitForTimeout(500);

    const inspector = page.locator('[data-builder-inspector]');
    const labelInput = inspector.locator('[data-testid="form-checkbox-label-input"]');
    await expect(labelInput).toBeVisible();
    await labelInput.fill("پذیرش کلیه شرایط و تعهدات");
    await page.waitForTimeout(400);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    await expect(frame.locator('text="پذیرش کلیه شرایط و تعهدات"').first()).toBeVisible();
  });

  test("2. Form radio group can be inserted and options edited in Inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("رادیویی");
    await page.waitForTimeout(300);

    const radioCard = page.locator('text="دکمه رادیویی"').first();
    await expect(radioCard).toBeVisible();
    await radioCard.click();
    await page.waitForTimeout(500);

    const inspector = page.locator('[data-builder-inspector]');
    const radioLabelInput = inspector.locator('[data-testid="form-radio-label-input"]');
    await expect(radioLabelInput).toBeVisible();
    await radioLabelInput.fill("انتخاب روش تسویه حساب");
    await page.waitForTimeout(400);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    await expect(frame.locator('text="انتخاب روش تسویه حساب"').first()).toBeVisible();
  });
});
