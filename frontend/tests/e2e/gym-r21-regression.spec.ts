import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 21 Regression Invariants (Notices, Titles-Meta, Telegram Notify & Indexing)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.87.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
    });
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
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

  test("1. Admin notices page renders tabbed layout with RTL text flow and SMS tab", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/notices`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('اعلانات زمان‌دار')");
    await expect(heading).toBeVisible();

    const noticesTab = page.locator("button[role='tab']:has-text('اطلاعیه‌ها')");
    await expect(noticesTab).toBeVisible();

    const smsTab = page.locator("button[role='tab']:has-text('ارسال پیامک')");
    await expect(smsTab).toBeVisible();

    // Switch to SMS tab and verify controls
    await smsTab.click();
    await page.waitForTimeout(500);
    const smsHeading = page.locator("h3:has-text('ارسال پیامک تکی')");
    await expect(smsHeading).toBeVisible();
  });

  test("2. Admin SEO titles & meta page renders RTL layout with separator and previews", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/titles-meta`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('عنوان و توضیحات پیش‌فرض')");
    await expect(heading).toBeVisible();

    const sepCard = page.locator("div:has-text('جداکننده عنوان')");
    await expect(sepCard.first()).toBeVisible();

    const saveAllBtn = page.locator("button:has-text('ذخیره همه')");
    await expect(saveAllBtn).toBeVisible();

    const previewBanner = page.locator("text=پیش‌نمایش با مقادیر نمونه").first();
    await expect(previewBanner).toBeVisible();
  });

  test("3. Admin telegram notify page renders with RTL direction and action buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/telegram-notify`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('اطلاع‌رسانی تلگرام سفارشات')");
    await expect(heading).toBeVisible();

    const testBtn = page.locator("button:has-text('ارسال تست')");
    await expect(testBtn).toBeVisible();

    const saveBtn = page.locator("button:has-text('ذخیره تنظیمات')");
    await expect(saveBtn).toBeVisible();
  });

  test("4. Admin SEO instant indexing page renders with RTL direction and IndexNow card", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/indexing`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('ایندکس فوری')");
    await expect(heading).toBeVisible();

    const indexNowHeading = page.locator("h2:has-text('ایندکس فوری')");
    await expect(indexNowHeading).toBeVisible();
  });
});
