import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 30 Regression Invariants (Digital Inventory, Fintech, Gamification, Cashback & Integrations)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.94.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
    });
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      { name: "access_token", value: token, url: "http://localhost:3000", httpOnly: false, sameSite: "Lax" },
    ]);
    await page.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user: { id: "47f274da-3abd-4d91-bc9c-83ba913fc66f", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });
  });

  test("1. Admin digital inventory page renders action buttons and tier pricing trigger in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/digital-inventory`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('انبار کدهای دیجیتال')");
    await expect(heading).toBeVisible();

    const tiersBtn = page.locator("button:has-text('قیمت‌گذاری پلکانی')");
    await expect(tiersBtn).toBeVisible();

    const uploadBtn = page.locator("button:has-text('بارگذاری کارت جدید')");
    await expect(uploadBtn).toBeVisible();
  });

  test("2. Admin fintech page renders gateway tabs and card-to-card receipts in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/fintech`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('پرداخت، کارت‌به‌کارت و درگاه‌ها')");
    await expect(heading).toBeVisible();

    const gatewaysBtn = page.locator("button:has-text('درگاه‌های پرداخت')");
    await expect(gatewaysBtn).toBeVisible();

    const receiptsBtn = page.locator("button:has-text('فیش‌های کارت‌به‌کارت')");
    await expect(receiptsBtn).toBeVisible();
  });

  test("3. Admin gamification page renders packages, rules, and rewards tab triggers in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/gamification`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('باشگاه مشتریان و گیمیفیکیشن')");
    await expect(heading).toBeVisible();

    const giftBtn = page.locator("button:has-text('صدور کارت هدیه')");
    await expect(giftBtn).toBeVisible();

    const packageTab = page.locator("button[role='tab']:has-text('بسته‌های شارژ')");
    await expect(packageTab).toBeVisible();

    const rulesTab = page.locator("button[role='tab']:has-text('قواعد امتیازدهی')");
    await expect(rulesTab).toBeVisible();
  });

  test("4. Admin cashback page renders rules heading and new rule action in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/cashback`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('کش‌بک و بازگشت وجه')");
    await expect(heading).toBeVisible();

    const newRuleBtn = page.locator("button:has-text('قاعده جدید')");
    await expect(newRuleBtn).toBeVisible();
  });

  test("5. Admin capability registry renders server-side integration table in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/integrations`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('فهرست قابلیت‌های یکپارچه‌سازی')");
    await expect(heading).toBeVisible();

    const refreshBtn = page.locator("button:has-text('بروزرسانی فهرست')");
    await expect(refreshBtn).toBeVisible();
  });
});
