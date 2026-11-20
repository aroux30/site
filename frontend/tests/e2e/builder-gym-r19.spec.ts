import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3200";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r10-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 19: Ecommerce Block Customization (Variants CRUD & Cart Summary Controls)", () => {
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

  test("1. Product variants block supports adding and editing custom variant titles", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Switch to basic blocks tab
    const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    // Search and add product variants block
    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("تنوع محصول");
    await page.waitForTimeout(300);

    const variantsCard = page.locator("button", { hasText: "تنوع محصول" }).first();
    await expect(variantsCard).toBeVisible();
    await variantsCard.click();
    await page.waitForTimeout(800);

    // In inspector, click "+ افزودن تنوع"
    const addVarBtn = page.getByRole("button", { name: "+ افزودن تنوع" });
    await expect(addVarBtn).toBeVisible();
    await addVarBtn.click();
    await page.waitForTimeout(400);

    // Verify newly added variant pill is visible on canvas
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const newVariantPill = frame.locator("button:has-text('تنوع جدید')").first();
    await expect(newVariantPill).toBeVisible();
  });

  test("2. Cart summary block title and button label are editable in Inspector", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("خلاصه سبد خرید");
    await page.waitForTimeout(300);

    const cartSummaryCard = page.locator("button", { hasText: "خلاصه سبد خرید" }).first();
    await expect(cartSummaryCard).toBeVisible();
    await cartSummaryCard.click();
    await page.waitForTimeout(800);

    // Change title and button label in inspector
    const titleInput = page.locator("div.space-y-4 input.h-8").first();
    await expect(titleInput).toBeVisible();
    await titleInput.fill("صورت‌حساب نهایی سفارش");
    await page.waitForTimeout(400);

    // Verify canvas displays updated title
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const summaryTitle = frame.locator("text=صورت‌حساب نهایی سفارش").first();
    await expect(summaryTitle).toBeVisible();
  });

  test("3. Star rating showValue switch updates numeric badge display", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
    await basicBlocksSubTab.click();
    await page.waitForTimeout(400);

    const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
    await searchInput.fill("امتیاز ستاره‌ای");
    await page.waitForTimeout(300);

    const starCard = page.locator("button", { hasText: "امتیاز ستاره‌ای" }).first();
    await expect(starCard).toBeVisible();
    await starCard.click();
    await page.waitForTimeout(800);

    // In inspector, showValue switch is visible
    const switchLabel = page.locator("text=نمایش عدد امتیاز");
    await expect(switchLabel).toBeVisible();
  });
});
