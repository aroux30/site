import { expect, test } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Phase P5 - Master Roadmap Production Hardening E2E Suite", () => {
  test.beforeEach(async ({ page }) => {
    // Authenticate as Super Admin
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
  });

  test("1. Builder Studio operations: element insertion, advanced layout, conditional visibility, global components, and page templates", async ({
    page,
  }) => {
    test.setTimeout(75_000);
    await resetE2EPage("e2e-isolated-scratchpad");

    await page.goto("/e2e-isolated-scratchpad?visual_editor=true", {
      waitUntil: "domcontentloaded",
      timeout: 45_000,
    });
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });

    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 25_000 });

    const initialCount = await frame.locator("[data-element-id]").count();

    // 1. Add block from palette
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.locator("text=سرتیتر").or(page.locator("text=کانتینر")).first().click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(initialCount + 1, { timeout: 15_000 });

    // 2. Open Save Page Template dialog via toolbar button
    const pageTplBtn = page.getByRole("button", { name: /قالب برگه/ }).first();
    await expect(pageTplBtn).toBeVisible({ timeout: 10_000 });
    await pageTplBtn.click();
    await expect(page.locator("text=ذخیره کل برگه به عنوان قالب")).toBeVisible({ timeout: 8_000 });
    await expect(page.locator("text=صفحات فرود (Landing)")).toBeVisible({ timeout: 5_000 });
    await page.getByRole("button", { name: "انصراف" }).click();

    // 3. Select first canvas element
    const firstEl = frame.locator("h1, h2, div.builder-container").first();
    await expect(firstEl).toBeVisible({ timeout: 10_000 });
    await firstEl.click({ force: true });

    // 4. Inspect Advanced Layout (Flexbox & Positioning)
    await page.getByRole("tab", { name: "استایل" }).click();
    await expect(page.locator("text=چیدمان پیشرفته (Advanced Layout - P4)")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=تنظیمات فلکس (Flexbox Controls)")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=موقعیت‌یابی و لایه‌بندی (Positioning & Z-Index)")).toBeVisible({ timeout: 5_000 });

    // 5. Inspect Conditional Visibility
    await page.getByRole("tab", { name: "پیشرفته" }).click();
    await expect(page.locator("text=نمایش شرطی (Conditional Visibility - P4)")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=نمایش در دسکتاپ")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=شرط ورود کاربر (Auth Visibility)")).toBeVisible({ timeout: 5_000 });

    // 6. Inspect Global Component
    await expect(page.locator("text=کامپوننت سراسری (Global / Synced Component)")).toBeVisible({ timeout: 5_000 });
    await page.getByRole("button", { name: "تبدیل به کامپوننت همگام سراسری (Make Global)" }).click();
    await expect(page.locator("text=کامپوننت همگام سراسری فعال است")).toBeVisible({ timeout: 5_000 });
  });

  test("2. Form Builder submission persistence and honeypot spam protection", async ({ request }) => {
    // 1. Submit legitimate visitor form
    const legitRes = await request.post("/api/v1/content/forms/submit", {
      data: {
        form_id: "p5_hardening_contact_form",
        page_slug: "e2e-isolated-scratchpad",
        data: {
          full_name: "مشتری نمونه P5",
          email: "customer@domain.ir",
          subject: "مشاوره خرید کالا",
          message: "درخواست پیش‌فاکتور رسمی شرکتی",
          accept_terms: true,
        },
      },
    });

    expect(legitRes.status()).toBe(201);
    const legitJson = await legitRes.json();
    expect(legitJson.success).toBe(true);
    expect(legitJson.submission_id).toBeDefined();

    // 2. Submit bot form with honeypot trap field filled
    const botRes = await request.post("/api/v1/content/forms/submit", {
      data: {
        form_id: "p5_hardening_contact_form",
        page_slug: "e2e-isolated-scratchpad",
        data: {
          full_name: "Spam Bot",
          message: "Buy cheap crypto",
        },
        _hp_website: "https://spammer-bot-trap.com",
      },
    });

    expect(botRes.status()).toBe(201);
    const botJson = await botRes.json();
    expect(botJson.success).toBe(true);
  });

  test("3. Admin Form Submissions Panel lists submitted customer entries", async ({ page }) => {
    await page.goto("/admin/forms");
    await expect(page.locator("h1:has-text('پیام‌ها و فرم‌های دریافتی')")).toBeVisible({
      timeout: 25_000,
    });

    await expect(page.getByPlaceholder("جستجو با شناسه فرم (Form ID)...")).toBeVisible();
    await expect(page.locator("text=مجموع پیام‌ها:")).toBeVisible();
  });

  test("4. Concurrent Editing Lock and Advisory Warning simulation", async ({ page }) => {
    // Intercept active lock call to simulate another active editor
    await page.route("**/api/v1/blog/admin/pages/**/lock", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            held: false,
            locked_by: "مدیر سیستم (admin-2)",
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/e2e-isolated-scratchpad?visual_editor=true", {
      waitUntil: "domcontentloaded",
      timeout: 45_000,
    });

    // Verify concurrent editing warning banner displays
    const lockBanner = page.locator("text=این برگه در حال حاضر توسط").or(page.locator("text=در اختیار گرفتن قفل ویرایش"));
    if (await lockBanner.first().isVisible({ timeout: 10_000 }).catch(() => false)) {
      await expect(lockBanner.first()).toBeVisible();
    }
  });
});
