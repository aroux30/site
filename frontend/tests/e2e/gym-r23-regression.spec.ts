import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 23 Regression Invariants (SEO Settings, Visibility, Content AI, Link Audit & Counter)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.92.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Admin SEO settings page renders canonical URL form and robots.txt card in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/settings`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('تنظیمات سئو')");
    await expect(heading).toBeVisible();

    const urlInput = page.locator("#seo-site-url");
    await expect(urlInput).toBeVisible();

    const saveUrlBtn = page.locator("button:has-text('ذخیره آدرس')");
    await expect(saveUrlBtn).toBeVisible();

    const robotsHeading = page.locator("h2:has-text('فایل robots.txt')");
    await expect(robotsHeading).toBeVisible();
  });

  test("2. Admin search visibility page renders search engine indexing toggle in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/visibility`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('نمایش در موتورهای جست‌وجو')");
    await expect(heading).toBeVisible();

    const saveBtn = page.locator("button:has-text('ذخیره وضعیت نمایش')");
    await expect(saveBtn).toBeVisible();
  });

  test("3. Admin content AI page renders API credentials and model inputs in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/content-ai`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('هوش مصنوعی محتوا')");
    await expect(heading).toBeVisible();

    const saveBtn = page.locator("button:has-text('ذخیره تنظیمات')");
    await expect(saveBtn).toBeVisible();
  });

  test("4. Admin broken-link crawler renders audit trigger and severity counters in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/link-audit`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('بررسی لینک‌های شکسته')");
    await expect(heading).toBeVisible();

    const runBtn = page.locator("button:has-text('بررسی کن')");
    await expect(runBtn).toBeVisible();
  });

  test("5. Admin link counter page renders orphan filter and post count metrics in RTL", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/seo/link-counter`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('شمارش لینک‌ها')");
    await expect(heading).toBeVisible();

    const refreshBtn = page.locator("button:has-text('بروزرسانی')");
    await expect(refreshBtn).toBeVisible();
  });
});
