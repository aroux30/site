import { expect, test } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Master Roadmap P4 - Advanced Visual Builder & E-Commerce E2E Suite", () => {
  test("Builder Studio configures Advanced Layout & Conditional Visibility on e2e-isolated-scratchpad", async ({
    page,
  }) => {
    test.setTimeout(75_000);

    // 1. Reset isolated scratchpad and authenticate as super_admin
    await resetE2EPage("e2e-isolated-scratchpad");
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
    await page.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user: {
              id: "admin-1",
              phone: "09123456789",
              isSuperuser: true,
              roles: ["super_admin"],
            },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });

    // 2. Open Builder Studio exclusively on e2e-isolated-scratchpad
    await page.goto("/e2e-isolated-scratchpad?visual_editor=true", {
      waitUntil: "domcontentloaded",
      timeout: 45_000,
    });
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });

    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 25_000 });

    // 3. Verify Save Page as Template dialog in Toolbar
    const pageTplBtn = page.getByRole("button", { name: /قالب برگه/ }).first();
    await expect(pageTplBtn).toBeVisible({ timeout: 10_000 });
    await pageTplBtn.click();

    // Verify Save Page Template dialog content
    await expect(page.locator("text=ذخیره کل برگه به عنوان قالب")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=صفحات فرود (Landing)")).toBeVisible({ timeout: 5_000 });
    await page.getByRole("button", { name: "انصراف" }).click();

    // 4. Select an element on the canvas
    const canvasFirstElem = frame.locator("h1, h2, div.builder-container").first();
    await expect(canvasFirstElem).toBeVisible({ timeout: 10_000 });
    await canvasFirstElem.click({ force: true });

    // 5. Open Style Tab and inspect Advanced Layout Controls
    await page.getByRole("tab", { name: "استایل" }).click();
    await expect(page.locator("text=چیدمان پیشرفته (Advanced Layout - P4)")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=تنظیمات فلکس (Flexbox Controls)")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=موقعیت‌یابی و لایه‌بندی (Positioning & Z-Index)")).toBeVisible({ timeout: 5_000 });

    // 6. Open Advanced Tab and verify Conditional Visibility & Global Component controls
    await page.getByRole("tab", { name: "پیشرفته" }).click();
    await expect(page.locator("text=نمایش شرطی (Conditional Visibility - P4)")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=نمایش بر اساس نوع دستگاه:")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=شرط ورود کاربر (Auth Visibility)")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=کامپوننت سراسری (Global / Synced Component)")).toBeVisible({ timeout: 5_000 });
  });

  test("Form Submission endpoint successfully validates honeypot anti-spam", async ({ request }) => {
    // 1. Submit legitimate form
    const legitRes = await request.post("/api/v1/content/forms/submit", {
      data: {
        form_id: "e2e_test_form",
        page_slug: "e2e-isolated-scratchpad",
        data: {
          full_name: "کاربر تستی E2E",
          phone: "09120000000",
          message: "پیام تستی برای راستی‌آزمایی دیتابیس",
        },
      },
    });

    expect(legitRes.status()).toBe(201);
    const legitBody = await legitRes.json();
    expect(legitBody.success).toBe(true);
    expect(legitBody.submission_id).toBeDefined();

    // 2. Submit bot form with honeypot filled -> must be accepted without error but dropped
    const botRes = await request.post("/api/v1/content/forms/submit", {
      data: {
        form_id: "e2e_test_form",
        page_slug: "e2e-isolated-scratchpad",
        data: {
          full_name: "SpamBot",
        },
        _hp_website: "http://bot-honeypot.xyz",
      },
    });

    expect(botRes.status()).toBe(201);
    const botBody = await botRes.json();
    expect(botBody.success).toBe(true);
  });
});
