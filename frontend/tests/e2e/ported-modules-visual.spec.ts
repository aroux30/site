/**
 * E2E visual test: ported modules admin panels.
 * Covers:
 * 1. /admin/referrals (Referral & Bonus system)
 * 2. /admin/currency (Nobitex USD Price Updater)
 * 3. /admin/user-verification (User Verification & Orders)
 */
import { test, expect } from "@playwright/test";

const ADMIN_PHONE = "09120000000";
const ADMIN_PASSWORD = "Admin@123456";
const BUDGET = 30_000;

async function loginAdmin(page: import("@playwright/test").Page) {
  await page.setExtraHTTPHeaders({
    "X-Forwarded-For": `10.97.${Math.floor(Math.random() * 200) + 1}.${Math.floor(Math.random() * 200) + 1}, 10.0.0.1`,
  });
  await page.goto("/login");
  await page.fill('input[name="phone"], input[type="tel"]', ADMIN_PHONE);
  await page.fill('input[name="password"], input[type="password"]', ADMIN_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/admin|dashboard/, { timeout: BUDGET });
}

test.describe("ported modules — visual E2E", () => {
  test.beforeEach(async ({ page }) => {
    await loginAdmin(page);
  });

  test("admin referrals panel renders all config cards and history tab", async ({ page }) => {
    await page.goto("/admin/referrals");
    await expect(page.getByRole("heading", { name: /برنامه دعوت دوستان/ })).toBeVisible({
      timeout: BUDGET,
    });

    // Check tabs
    await expect(page.getByRole("tab", { name: "تنظیمات" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "تاریخچهٔ پاداش‌ها" })).toBeVisible();

    // Check configuration cards using role heading to avoid strict-mode clashes with descriptions
    await expect(page.getByRole("heading", { name: "وضعیت برنامه" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "هدیهٔ ثبت‌نام (پاداش دعوت)" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "پورسانت خرید (درصدی)" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "بونوس شارژ کیف پول" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "اعلان‌ها" })).toBeVisible();

    // Check Save button
    await expect(page.getByRole("button", { name: "ذخیره" })).toBeVisible();

    // Switch to history tab
    await page.getByRole("tab", { name: "تاریخچهٔ پاداش‌ها" }).click();
    await expect(page.getByRole("button", { name: /خروجی اکسل/ })).toBeVisible({ timeout: BUDGET });
  });

  test("admin currency panel renders Nobitex status and manual update button", async ({ page }) => {
    await page.goto("/admin/currency");
    await expect(page.getByRole("heading", { name: /به‌روزرسانی خودکار قیمت دلاری/ })).toBeVisible({
      timeout: BUDGET,
    });

    // Check tabs
    await expect(page.getByRole("tab", { name: "تنظیمات" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "تاریخچهٔ اجراها" })).toBeVisible();

    // Check status panel and actions
    await expect(page.getByText("وضعیت فعلی")).toBeVisible();
    await expect(page.getByRole("button", { name: "به‌روزرسانی قیمت‌ها الآن" })).toBeVisible();
    await expect(page.getByRole("button", { name: "ذخیرهٔ تنظیمات" })).toBeVisible();

    // Switch to history tab
    await page.getByRole("tab", { name: "تاریخچهٔ اجراها" }).click();
    await expect(page.getByRole("button", { name: /خروجی CSV/ })).toBeVisible({ timeout: BUDGET });
  });

  test("admin user-verification panel renders users, logs, and settings tabs", async ({ page }) => {
    await page.goto("/admin/user-verification");
    await expect(page.getByRole("heading", { name: /احراز کاربران/ })).toBeVisible({
      timeout: BUDGET,
    });

    // Check all three tabs
    await expect(page.getByRole("tab", { name: "مدیریت کاربران" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "گزارش لاگ‌ها" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "تنظیمات" })).toBeVisible();

    // Check users table search & filter buttons
    await expect(page.getByPlaceholder("جستجو با شماره موبایل…")).toBeVisible();
    await expect(page.getByRole("button", { name: "احراز شده" })).toBeVisible();
    await expect(page.getByRole("button", { name: "احراز نشده" })).toBeVisible();

    // Switch to Settings tab
    await page.getByRole("tab", { name: "تنظیمات" }).click();
    await expect(page.getByRole("heading", { name: "تنظیمات احراز" })).toBeVisible({ timeout: BUDGET });
    await expect(page.getByRole("button", { name: /ذخیره/ })).toBeVisible();

    // Switch to Logs tab
    await page.getByRole("tab", { name: "گزارش لاگ‌ها" }).click();
    await expect(page.getByRole("button", { name: /خروجی اکسل/ })).toBeVisible({ timeout: BUDGET });
  });
});
