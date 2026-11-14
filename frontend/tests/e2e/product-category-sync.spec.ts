/**
 * E2E test: Product & Category synchronization verification (360-degree audit).
 * Tests:
 * 1. Creating a brand new category in /admin/categories
 * 2. Navigating to /admin/products and opening Add Product modal
 * 3. Verifying the newly created category is in the dropdown and selectable
 * 4. Creating the product with that category
 * 5. Verifying the product row in the table shows the category
 * 6. Opening Edit modal, updating category, and verifying persistence
 * 7. Category management: editing category and guarded deletion
 * 8. Storefront: filtering products by category slug and id
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

test.describe("Product & Category synchronization E2E (360 Audit)", () => {
  test("creates a new category and assigns it to a new product", async ({ page }) => {
    test.setTimeout(120_000);
    await loginAdmin(page);

    const uniqueSuffix = Date.now().toString().slice(-5);
    const categoryName = `دسته تست اسپرینت ${uniqueSuffix}`;
    const categorySlug = `cat-sync-${uniqueSuffix}`;
    const productName = `کالای هوشمند تست ${uniqueSuffix}`;
    const productSku = `SKU-SYNC-${uniqueSuffix}`;

    // ── 1. Create a new category in /admin/categories ─────────────────────
    await page.goto("/admin/categories");
    await expect(page.getByRole("heading", { name: /دسته‌بندی‌های فروشگاه/ })).toBeVisible({
      timeout: BUDGET,
    });

    await page.getByRole("button", { name: /افزودن دسته‌بندی/ }).click();
    await page.getByPlaceholder("مثال: ساعت هوشمند").fill(categoryName);
    await page.getByPlaceholder("مثال: smart-watches").fill(categorySlug);
    await page.getByRole("button", { name: "ثبت دسته‌بندی" }).click();

    // Verify toast appears
    await expect(page.getByText("دسته‌بندی ایجاد شد")).toBeVisible({ timeout: 10_000 });

    // ── 2. Open /admin/products and verify the category is selectable ──────
    await page.goto("/admin/products");
    await expect(page.getByRole("heading", { name: "مدیریت محصولات" })).toBeVisible({
      timeout: BUDGET,
    });

    await page.getByRole("button", { name: /افزودن محصول جدید/ }).click();
    await page.locator("input#prodName").fill(productName);
    await page.locator("input#prodSku").fill(productSku);
    await page.locator("input#prodPrice").fill("۲۵۰٬۰۰۰");

    // Click category select dropdown in modal
    const categorySelectTrigger = page.locator("form").getByRole("combobox").first();
    await categorySelectTrigger.click();

    // The newly created category MUST be present in the options! The modal
    // reads the shared admin-categories query, which refetches after the
    // category was just created — give the refetch time to land.
    const newCategoryOption = page.getByRole("option", { name: categoryName });
    await expect(newCategoryOption).toBeVisible({ timeout: 15_000 });
    await newCategoryOption.click();

    // Submit product
    await page.getByRole("button", { name: "ایجاد و ثبت محصول" }).click();

    // ── 3. Verify product is listed with the new category in the table ────
    const productRow = page.locator("table tbody tr").filter({ hasText: productName });
    await expect(productRow).toBeVisible({ timeout: 10_000 });
    await expect(productRow.getByText(categoryName)).toBeVisible();

    // ── 4. Verify editing the product preserves and updates the category ──
    await productRow.getByTitle("ویرایش محصول").click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 5_000 });

    // The modal select should have the assigned category
    const editCategoryCombobox = page.locator("form").getByRole("combobox").first();
    await expect(editCategoryCombobox).toHaveText(categoryName);

    // Change category to another category (a seed category, not ad-hoc data)
    await editCategoryCombobox.click();
    const otherCategoryOption = page.getByRole("option", { name: "گوشی هوشمند" });
    await expect(otherCategoryOption).toBeVisible({ timeout: 5_000 });
    await otherCategoryOption.click();

    // Save changes
    await page.getByRole("button", { name: "ذخیره تغییرات" }).click();

    // Wait for the save to complete (toast), then for the table to repaint
    // with the moved category — the list refetches after the save.
    await expect(page.getByText("محصول بروزرسانی شد")).toBeVisible({ timeout: 60_000 });
    await expect(productRow.getByText("گوشی هوشمند")).toBeVisible({ timeout: 30_000 });
  });

  test("admin categories panel allows editing and guarded deletion", async ({ page }) => {
    test.setTimeout(120_000);
    await loginAdmin(page);

    const uniqueSuffix = Date.now().toString().slice(-5);
    const categoryName = `دسته ویرایشی ${uniqueSuffix}`;
    const categorySlug = `edit-cat-${uniqueSuffix}`;
    const updatedCategoryName = `دسته اصلاح‌شده ${uniqueSuffix}`;

    // ── 1. Create a category to edit ──────────────────────────────────────
    await page.goto("/admin/categories");
    await page.getByRole("button", { name: /افزودن دسته‌بندی/ }).click();
    await page.getByPlaceholder("مثال: ساعت هوشمند").fill(categoryName);
    await page.getByPlaceholder("مثال: smart-watches").fill(categorySlug);
    await page.getByRole("button", { name: "ثبت دسته‌بندی" }).click();
    await expect(page.getByText("دسته‌بندی ایجاد شد")).toBeVisible({ timeout: 10_000 });

    // ── 2. Edit the category name ─────────────────────────────────────────
    // The post-create refetch paginates the whole catalogue; allow it to land.
    const catRow = page.locator("table tbody tr").filter({ hasText: categoryName });
    await expect(catRow).toBeVisible({ timeout: 20_000 });
    await catRow.getByTitle(`ویرایش دسته ${categoryName}`).click();

    // Edit dialog opens
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("heading", { name: "ویرایش دسته‌بندی" })).toBeVisible();
    await page.locator('div[role="dialog"] input').first().fill(updatedCategoryName);
    await page.getByRole("button", { name: "ذخیره تغییرات" }).click();

    // ── 3. Delete the category ────────────────────────────────────────────
    // The list now paginates the whole catalogue in the background after the
    // save; allow the refetch to land before asserting on the renamed row.
    const updatedRow = page.locator("table tbody tr").filter({ hasText: updatedCategoryName });
    await expect(updatedRow).toBeVisible({ timeout: 20_000 });
    await updatedRow.getByTitle(`حذف دسته ${updatedCategoryName}`).click();

    // Confirm dialog button appears
    const confirmDeleteBtn = page.getByRole("button", { name: "حذف دسته‌بندی" });
    await expect(confirmDeleteBtn).toBeVisible({ timeout: 5_000 });
    await confirmDeleteBtn.click();

    // Verify deletion toast
    await expect(page.getByText("دسته‌بندی حذف شد")).toBeVisible({ timeout: 10_000 });
  });

  /**
   * The previous version of this test counted `a[href^="/products/"]` and
   * passed with ANY number > 0 — header/footer links alone satisfy it, so a
   * completely broken filter was green. These assertions read the result
   * counter and the chip, both of which only exist when filtering works.
   *
   * The legacy `?category=` URL is pinned HERE as a client-side contract:
   * the hook rewrites it to `category_slug` before calling the API, so this
   * test proves the storefront honours the URL — it cannot see the backend's
   * own parsing, which `test_catalog_legacy_category_param.py` pins instead.
   */
  test("storefront filters by category for every URL form (id, slug, legacy)", async ({
    page,
    request,
  }) => {
    test.setTimeout(90_000);
    // Anchored to the seed catalogue («گوشی هوشمند»/smartphones) and resolved
    // at runtime: a hardcoded UUID died with an ad-hoc category the first
    // time the dev database was reseeded.
    const CATEGORY_NAME = "گوشی هوشمند";
    const slug = "smartphones";
    const catRes = await request.get(`/api/v1/catalog/categories/by-slug/${slug}`);
    expect(catRes.ok(), "seed category must exist").toBeTruthy();
    const cid = ((await catRes.json()) as { id: string }).id;

    const countLocator = page.getByText(/نمایش\s*[۰-۹0-9,٬]+\s*کالا از مجموع/);

    for (const [label, qs] of [
      ["category_id", `category_id=${cid}`],
      ["category_slug", `category_slug=${slug}`],
      ["legacy category", `category=${slug}`],
    ] as const) {
      await page.goto(`/products?${qs}`);
      // Wait for the query to resolve: the loading line is replaced by the
      // real counter (the counter never renders a bare 0 while loading).
      await expect(countLocator).toBeVisible({ timeout: BUDGET });
      // Let the label resolution (a second async read) settle before reading
      // the chip — otherwise the previous page's chip text can be observed.
      await page.waitForLoadState("networkidle").catch(() => {});
      const text = (await countLocator.innerText()).replace(/[۰-۹]/g, (d) =>
        String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)),
      );
      const shown = Number(text.match(/نمایش\s*(\d+)/)?.[1] ?? "0");
      expect(shown, `${label}: filtered grid must not be empty`).toBeGreaterThan(0);
      expect(shown, `${label}: must not be the whole catalogue (5k+)`).toBeLessThan(100);

      // The chip must name the category, never echo a raw UUID or slug. The
      // label resolves from the query result one tick after the counter, so
      // poll instead of a one-shot 5s visibility check. Log the value so a
      // failure shows WHAT the chip actually said.
      const chip = page.getByText(/^دسته:/);
      let chipText = "";
      const chipDeadline = Date.now() + 30_000;
      while (Date.now() < chipDeadline) {
        chipText = (await chip.first().textContent().catch(() => "")) ?? "";
        if (chipText.includes(CATEGORY_NAME)) break;
        await page.waitForTimeout(500);
      }
      console.log(`${label}: chip="${chipText.trim()}"`);
      expect(chipText, `${label}: chip must carry the Persian category name`).toContain(
        CATEGORY_NAME,
      );
    }

    // An unknown category must render the empty state — proving the grid is
    // actually filtered rather than always showing everything.
    await page.goto("/products?category_slug=does-not-exist-xyz");
    await expect(page.getByText(/محصولی با این مشخصات یافت نشد/)).toBeVisible({
      timeout: BUDGET,
    });
  });

  test("pretty /category/<slug> archive (WordPress parity) serves the filtered grid", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    const CATEGORY_NAME = "گوشی هوشمند";
    const slug = "smartphones";
    const countLocator = page.getByText(/نمایش\s*[۰-۹0-9,٬]+\s*کالا از مجموع/);

    await page.goto(`/category/${slug}`);
    await expect(countLocator).toBeVisible({ timeout: BUDGET });
    await page.waitForLoadState("networkidle").catch(() => {});
    const text = (await countLocator.innerText()).replace(/[۰-۹]/g, (d) =>
      String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)),
    );
    const shown = Number(text.match(/نمایش\s*(\d+)/)?.[1] ?? "0");
    expect(shown, "pretty URL must filter, not dump the catalogue").toBeGreaterThan(0);
    expect(shown).toBeLessThan(100);

    const chip = page.getByText(/^دسته:/);
    await expect(chip.first()).toContainText(CATEGORY_NAME, { timeout: 30_000 });

    // A rewrite, not a redirect: the pretty slug URL must survive navigation.
    await expect(page).toHaveURL(new RegExp(`/category/${slug}$`));
  });

  test("header category menu and PDP badge lead to a filtered grid", async ({ page }) => {
    test.setTimeout(90_000);
    const countLocator = page.getByText(/نمایش\s*[۰-۹0-9,٬]+\s*کالا از مجموع/);

    // ── PDP badge ─────────────────────────────────────────────────────────
    await page.goto("/products?category_slug=smartphones");
    await expect(countLocator).toBeVisible({ timeout: BUDGET });
    // Grid card links only (Card links carry `h-full`): the SEO crawlable
    // nav at the page bottom lists the UNFILTERED catalogue, and its first
    // product may be stale e2e data whose PDP has no category badge at all.
    const firstProduct = page.locator('main a.h-full[href^="/products/"]').first();
    const href = await firstProduct.getAttribute("href");
    expect(href).toBeTruthy();
    await page.goto(href!);
    // Under full-suite load the backend can shed the product fetch once and
    // the page parks on its error screen («خطا در دریافت محصول»). One reload
    // recovers it; failing there would say nothing about the badge itself.
    const pdpError = page.getByRole("heading", { name: "خطا در دریافت محصول" });
    if (await pdpError.isVisible({ timeout: 8_000 }).catch(() => false)) {
      await page.reload();
    }
    const badge = page.locator('main a[href*="category_id="]').first();
    // 60s: the first visit to a PDP in a suite run pays Turbopack's on-demand
    // compile, which can outgrow the 30s default budget on a busy dev server.
    await expect(badge).toBeVisible({ timeout: 60_000 });
    await expect(badge).not.toHaveText(/^$/);
    await badge.click();
    // Same 60s rationale as the badge wait: three heavy navigations against
    // the dev server in one test can outgrow the 30s default.
    await expect(countLocator).toBeVisible({ timeout: 60_000 });
    const shown = (await countLocator.innerText()).replace(/[۰-۹]/g, (d) =>
      String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)),
    );
    expect(Number(shown.match(/نمایش\s*(\d+)/)?.[1] ?? "0")).toBeGreaterThan(0);
  });
});
