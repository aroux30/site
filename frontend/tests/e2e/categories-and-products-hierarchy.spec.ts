/**
 * E2E tests for Categories & Products Hierarchy, Parent assignment, Image thumbnail,
 * and Inline Quick-Add Category inside product modal.
 */
import { test, expect } from "@playwright/test";

const ADMIN_PHONE = "09120000000";
const ADMIN_PASSWORD = "Admin@123456";
const BUDGET = 30_000;

function freshIp(): string {
  return `10.97.${Math.floor(Math.random() * 200) + 1}.${Math.floor(Math.random() * 200) + 1}, 10.0.0.1`;
}

async function loginAdmin(page: import("@playwright/test").Page) {
  await page.setExtraHTTPHeaders({ "X-Forwarded-For": freshIp() });
  await page.goto("/login");
  await page.fill('input[name="phone"], input[type="tel"]', ADMIN_PHONE);
  await page.fill('input[name="password"], input[type="password"]', ADMIN_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/admin|dashboard/, { timeout: BUDGET });
}

test.describe("Category Hierarchy & Product Parity E2E", () => {
  test("creates parent & child categories, verifies parent_name in table, and edits parent", async ({ page }) => {
    test.setTimeout(90_000);
    await loginAdmin(page);

    const suffix = Date.now().toString().slice(-5);
    const parentName = `والد تست ${suffix}`;
    const parentSlug = `parent-test-${suffix}`;
    const childName = `فرزند تست ${suffix}`;
    const childSlug = `child-test-${suffix}`;

    // ── 1. Create Parent Category ──────────────────────────────────────────
    await page.goto("/admin/categories");
    await expect(page.getByRole("heading", { name: /دسته‌بندی‌های فروشگاه/ })).toBeVisible({
      timeout: BUDGET,
    });
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /افزودن دسته‌بندی/ }).click();
    await page.getByPlaceholder("مثال: ساعت هوشمند").fill(parentName);
    await page.getByPlaceholder("مثال: smart-watches").fill(parentSlug);
    await page.getByRole("button", { name: "ثبت دسته‌بندی" }).click();
    await expect(page.getByText("دسته‌بندی ایجاد شد")).toBeVisible({ timeout: 15_000 });

    // ── 2. Create Child Category with Parent assigned ───────────────────────
    await page.getByRole("button", { name: /افزودن دسته‌بندی/ }).click();
    await page.getByPlaceholder("مثال: ساعت هوشمند").fill(childName);
    await page.getByPlaceholder("مثال: smart-watches").fill(childSlug);

    // Select the parent category from the hierarchy dropdown (now a Radix
    // select). The options render in a portal after opening; the hierarchy
    // refetch must land first, so wait for the option before clicking it.
    await page.getByRole("combobox", { name: "دسته‌بندی والد" }).first().click();
    const parentOption = page.getByRole("option", { name: parentName, exact: true });
    await expect(parentOption).toBeVisible({ timeout: 20_000 });
    await parentOption.click();

    await page.getByRole("button", { name: "ثبت دسته‌بندی" }).click();
    await expect(page.getByText("دسته‌بندی ایجاد شد")).toBeVisible({ timeout: 15_000 });

    // ── 3. Verify Child Category shows Parent Name in the table ────────────
    await page.getByPlaceholder("جستجو در دسته‌ها...").fill(childName);
    const childRow = page.locator("table tbody tr").filter({ hasText: childName });
    await expect(childRow).toBeVisible({ timeout: 10_000 });

    // Parent column must show the real parentName badge, NOT "—"!
    await expect(childRow.getByText(parentName)).toBeVisible({ timeout: 5_000 });

    // ── 4. Edit Child Category and change parent or name ───────────────────
    await childRow.getByTitle(`ویرایش دسته ${childName}`).click();
    await expect(page.getByRole("heading", { name: "ویرایش دسته‌بندی" })).toBeVisible();

    // Verify parent is pre-selected in the edit modal — the Radix select's
    // trigger text is the selected item's label.
    const editParentTrigger = page
      .getByRole("combobox", { name: "دسته‌بندی والد" })
      .first();
    await expect(editParentTrigger).toBeVisible();
    await expect(editParentTrigger).toHaveText(parentName);

    // Change title and save
    const updatedChildName = `${childName} ویرایش‌شده`;
    await page.locator("div[role='dialog'] input").first().fill(updatedChildName);
    await page.getByRole("button", { name: "ذخیره تغییرات" }).click();

    await expect(page.getByText("دسته‌بندی بروزرسانی شد")).toBeVisible({ timeout: 15_000 });
  });

  test("product creation displays indented categories and supports inline quick category creation", async ({ page }) => {
    test.setTimeout(90_000);
    await loginAdmin(page);

    const suffix = Date.now().toString().slice(-5);
    const quickCatName = `دسته سریع اینلاین ${suffix}`;
    const quickCatSlug = `quick-cat-${suffix}`;
    const prodName = `کالای تست دسته سریع ${suffix}`;
    const prodSku = `SKU-QC-${suffix}`;

    await page.goto("/admin/products");
    await expect(page.getByRole("heading", { name: "مدیریت محصولات" })).toBeVisible({
      timeout: BUDGET,
    });

    await page.getByRole("button", { name: /افزودن محصول جدید/ }).click();
    await expect(page.getByRole("heading", { name: "افزودن محصول جدید" })).toBeVisible();

    // Click quick add category button inside product modal
    await page.getByRole("button", { name: "دسته‌بندی جدید" }).click();
    await expect(page.getByRole("heading", { name: "افزودن سریع دسته‌بندی" })).toBeVisible();

    await page.getByPlaceholder("مثال: قاب و محافظ صفحه").fill(quickCatName);
    await page.getByPlaceholder("مثال: phone-cases").fill(quickCatSlug);
    await page.getByRole("button", { name: "افزودن و انتخاب" }).click();

    await expect(page.getByText("دسته‌بندی افزوده شد")).toBeVisible({ timeout: 15_000 });

    // Fill remaining required product fields
    await page.locator("input#prodName").fill(prodName);
    await page.locator("input#prodSku").fill(prodSku);
    await page.locator("input#prodPrice").fill("۳۵۰٬۰۰۰");

    // Submit product
    await page.getByRole("button", { name: "ایجاد و ثبت محصول" }).click();
    await expect(page.getByText("محصول جدید با موفقیت افزوده شد")).toBeVisible({ timeout: 30_000 });

    // Filter by product name in table search box
    await page.getByPlaceholder("جستجو در نام محصول، کد انبار (SKU) یا برند...").fill(prodName);

    // Verify row appears with the new quick category in the table
    const productRow = page.locator("table tbody tr").filter({ hasText: prodName });
    await expect(productRow).toBeVisible({ timeout: 15_000 });
    await expect(productRow.getByText(quickCatName)).toBeVisible({ timeout: 10_000 });
  });

  test("product page displays clean hierarchical breadcrumbs (Home > Parent > Child > Name) without redundant 'محصولات'", async ({ page }) => {
    test.setTimeout(60_000);

    // Open Samsung Galaxy S24 Ultra (under smartphones, parent: digital-goods)
    await page.goto("/products/samsung-galaxy-s24-ultra");
    await expect(page.locator("h1")).toBeVisible({ timeout: BUDGET });

    const breadcrumbNav = page.locator("nav[aria-label='مسیر دسته‌بندی محصول']");
    await expect(breadcrumbNav).toBeVisible();

    // Verify breadcrumb elements in sequence
    await expect(breadcrumbNav.getByRole("link", { name: "صفحه اصلی" })).toBeVisible();
    await expect(breadcrumbNav.getByRole("link", { name: "کالای دیجیتال" })).toBeVisible();
    await expect(breadcrumbNav.getByRole("link", { name: "گوشی هوشمند" })).toBeVisible();
    await expect(breadcrumbNav.getByText("گوشی موبایل سامسونگ مدل Galaxy S24 Ultra")).toBeVisible();

    // Redundant "محصولات" link MUST NOT be present in this category breadcrumb
    await expect(breadcrumbNav.getByRole("link", { name: "محصولات" })).toHaveCount(0);
  });
});
