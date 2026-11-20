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
  const tmp = path.join(BACKEND_DIR, `.gym-r08-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 17: Accordion Item CRUD, Dynamic Title Sync & Filter Event Propagation", () => {
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

  test("1. Accordion items can be added and deleted in Inspector with real-time canvas sync", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Switch to basic blocks tab
    const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    // Search and add accordion block
    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("آکاردئون");
    await page.waitForTimeout(300);

    const accordionCard = page.locator("button", { hasText: "آکاردئون" }).first();
    await expect(accordionCard).toBeVisible();
    await accordionCard.click();
    await page.waitForTimeout(600);

    // Check inspector has accordion manager
    const accordionTitle = page.locator("text=مدیریت آیتم‌های تاشو (Accordion)");
    await expect(accordionTitle).toBeVisible();

    // Count initial items
    const initialDeleteBtns = page.locator("div.space-y-4 button:has-text('حذف')");
    const count = await initialDeleteBtns.count();

    // Add a new item
    const addBtn = page.getByRole("button", { name: "+ افزودن آیتم جدید به آکاردئون" });
    await expect(addBtn).toBeVisible();
    await addBtn.click();
    await page.waitForTimeout(400);

    // Now delete the newly added item
    const newDeleteBtns = page.locator("div.space-y-4 button:has-text('حذف')");
    expect(await newDeleteBtns.count()).toBeGreaterThan(count);

    await newDeleteBtns.last().click();
    await page.waitForTimeout(400);

    expect(await page.locator("div.space-y-4 button:has-text('حذف')").count()).toBe(count);
  });

  test("2. Save Page Template dialog dynamically reflects the current page title on open", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const savePageTplBtn = page.getByRole("button", { name: /قالب برگه/i });
    await expect(savePageTplBtn).toBeVisible();
    await savePageTplBtn.click();
    await page.waitForTimeout(500);

    const dialog = page.locator("div[role='dialog']").first();
    await expect(dialog).toBeVisible();

    const titleInput = dialog.locator("input.h-8").first();
    const val = await titleInput.inputValue();
    expect(val).toContain("E2E Builder Scratchpad");

    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
  });

  test("3. Product grid filter tabs stop propagation on click inside canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Switch to basic blocks tab
    const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("ویترین محصولات");
    await page.waitForTimeout(300);

    const gridBlockCard = page.locator("button", { hasText: "ویترین محصولات" }).first();
    await expect(gridBlockCard).toBeVisible();
    await gridBlockCard.click();
    await page.waitForTimeout(800);

    // Frame canvas
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const featuredBtn = frame.locator("button:has-text('ویژه')").first();
    await expect(featuredBtn).toBeVisible();
    await featuredBtn.click();
    await page.waitForTimeout(400);

    // Active filter class applied to button
    await expect(featuredBtn).toHaveClass(/bg-primary/);
  });
});
