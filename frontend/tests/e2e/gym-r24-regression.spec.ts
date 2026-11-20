import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 24 Regression Invariants (Automation, Notices & Live Chat)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.88.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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

  test("1. Admin automation rules page renders action controls and guidelines", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/automation`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('قواعد خودکارسازی')");
    await expect(heading).toBeVisible();

    const newRuleBtn = page.locator("button:has-text('قاعده جدید')");
    await expect(newRuleBtn).toBeVisible();
  });

  test("2. Admin notices page renders tabbed layout with notices and SMS dispatch", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/notices`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h2:has-text('اعلانات زمان‌دار')");
    await expect(heading).toBeVisible();

    const smsTab = page.locator("button[role='tab']:has-text('ارسال پیامک')");
    await expect(smsTab).toBeVisible();
  });

  test("3. Admin live chat console renders active conversations and tabs", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/chat`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('گفتگوی زنده')");
    await expect(heading).toBeVisible();

    const onlineTab = page.locator("button:has-text('کاربران آنلاین')");
    await expect(onlineTab).toBeVisible();
  });
});
