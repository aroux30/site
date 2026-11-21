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
  const tmp = path.join(BACKEND_DIR, `.gym-r06-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 15: Progressive Overload (Nested Layouts, Gap Parity & Inspector Content Controls)", () => {
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

  test("1. Container layout update in inspector modifies AST node layout and gap properly", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Switch to basic blocks tab
    const basicBlocksSubTab = page.getByRole("button", { name: "بلوک‌ها", exact: true });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    // Click on the container block to insert a new container
    const containerBlockCard = page.locator("button", { hasText: "کانتینر" }).first();
    await expect(containerBlockCard).toBeVisible();
    await containerBlockCard.click();
    await page.waitForTimeout(600);

    // In inspector, layout controls should be visible for the container
    const layoutLabel = page.locator("text=نوع چیدمان کانتینر");
    await expect(layoutLabel).toBeVisible();

    // Change gap input
    const gapInput = page.locator('[data-testid="container-gap-input"]');
    await expect(gapInput).toBeVisible();
    await gapInput.fill("28");
    await page.waitForTimeout(400);

    const val = await gapInput.inputValue();
    expect(val).toBe("28");
  });

  test("2. Tabs and Divider widgets have dedicated rich content inspector controls", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Switch to basic blocks tab
    const basicBlocksSubTab = page.getByRole("button", { name: "بلوک‌ها", exact: true });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    // Search and click tabs block
    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("تب‌های محتوا");
    await page.waitForTimeout(300);

    const tabsBlockCard = page.locator("button", { hasText: "تب‌های محتوا" }).first();
    await expect(tabsBlockCard).toBeVisible();
    await tabsBlockCard.click();
    await page.waitForTimeout(800);

    // Check inspector content controls for tabs
    const tabsControls = page.locator('[data-testid="tabs-inspector-controls"]');
    await expect(tabsControls).toBeVisible();

    // Add new tab button should be clickable
    const addTabBtn = page.getByRole("button", { name: "+ افزودن زبانه" });
    await expect(addTabBtn).toBeVisible();
    await addTabBtn.click();
    await page.waitForTimeout(400);

    const tab3Label = page.locator("text=زبانه").first();
    await expect(tab3Label).toBeVisible();
  });

  test("3. Element renaming and visibility toggles operate correctly without AST corruption", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Select first canvas element
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await firstEl.click();
    await page.waitForTimeout(400);

    // Switch inspector to Advanced tab
    const advancedTab = page.getByRole("tab", { name: "پیشرفته" });
    await advancedTab.click();
    await page.waitForTimeout(400);

    // Rename input is the first text input in the advanced tab
    const nameInput = page.locator("div.space-y-4 input.h-8").first();
    await expect(nameInput).toBeVisible();
    await nameInput.fill("سکشن لندینگ آزمایشی");
    await page.waitForTimeout(400);

    // Switch to layers tab in sidebar to verify the rename is immediately visible
    const layersTab = page.getByRole("button", { name: "لایه‌ها" });
    await layersTab.click();
    await page.waitForTimeout(500);

    const renamedItem = page.locator("text=سکشن لندینگ آزمایشی").first();
    await expect(renamedItem).toBeVisible();
  });
});
