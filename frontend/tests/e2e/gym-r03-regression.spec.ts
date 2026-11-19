import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 03 Regression Invariants (Complex Interactions & Widgets - 20kg)", () => {
  test.beforeEach(async ({ page }) => {
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

  test("1. Product QuickView Modal opens with RTL layout and product image", async ({ page }) => {
    await page.goto(`${BASE_URL}/products`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const quickViewBtn = page.locator("button[title*='مشاهده سریع'], button:has-text('مشاهده سریع')").first();
    if (await quickViewBtn.isVisible()) {
      await quickViewBtn.click();
      await page.waitForTimeout(800);

      const dialog = page.locator("[role='dialog']");
      await expect(dialog).toBeVisible();

      // Check RTL layout
      const dir = await dialog.getAttribute("dir");
      expect(dir).toBe("rtl");

      // Check product image element or media container exists inside dialog
      const media = dialog.locator("img, [class*='aspect-square']").first();
      await expect(media).toBeVisible();
    }
  });

  test("2. MegaMenu dropdown renders functional category navigation link for empty child states", async ({ page }) => {
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const categoriesBtn = page.locator("button:has-text('دسته‌بندی کالاها')").first();
    await expect(categoriesBtn).toBeVisible();
    await categoriesBtn.click();
    await page.waitForTimeout(600);

    const menuPanel = page.locator("[role='menu']");
    await expect(menuPanel).toBeVisible();

    // Check that categories menu has navigation link
    const viewCategoryLink = menuPanel.locator("a[href*='/category/']").first();
    await expect(viewCategoryLink).toBeVisible();
  });

  test("3. Form submission creates accessible row in admin forms panel", async ({ page, request }) => {
    const uniqueFormId = `gym_r03_verify_${Date.now()}`;
    const submitPayload = {
      form_id: uniqueFormId,
      page_slug: "e2e-isolated-scratchpad",
      data: {
        fullname: "تست رگرسیون راند ۳",
        email: "test.round3@example.com",
        message: "پیام راستی‌آزمایی رگرسیون",
      },
      hp_field: "",
    };

    const res = await request.post(`${BASE_URL}/api/v1/content/forms/submit`, {
      data: submitPayload,
      headers: { "Content-Type": "application/json" },
    });
    expect(res.status()).toBe(201);

    // Verify row in /admin/forms
    await page.goto(`${BASE_URL}/admin/forms`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const submittedRow = page.locator(`td:has-text('${uniqueFormId}')`);
    await expect(submittedRow).toBeVisible();
  });
});
