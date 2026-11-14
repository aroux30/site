/**
 * 360° audit E2E: products & categories. Each test pins one audited claim
 * with live evidence; each one fails if its fixed bug regresses.
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

/** Persian digits → English digits. */
function faToEn(text: string): string {
  return text.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)));
}

test.describe("360° audit — products & categories", () => {
  test("AUDIT-1: admin products list shows ALL products, not just the first page", async ({ page }) => {
    test.setTimeout(90_000);
    await loginAdmin(page);

    const apiCount = await page.evaluate(async () => {
      const res = await fetch(`${window.location.origin}/api/v1/catalog/products?page_size=1`);
      const data = await res.json();
      return data.meta.total as number;
    });

    await page.goto("/admin/products");
    await expect(page.getByRole("heading", { name: "مدیریت محصولات" })).toBeVisible({
      timeout: BUDGET,
    });

    // 3,823 products paginate over ~39 requests; the counter grows until the
    // final page lands. Wait until it stops changing, then read it once.
    const totalCard = page.locator("p", { hasText: "کل محصولات" }).locator("..");
    const counter = totalCard.locator("p.font-mono");
    let uiCount = 0;
    let lastSeen = -1;
    const deadline = Date.now() + 45_000;
    for (;;) {
      const text = (await counter.textContent()) ?? "";
      uiCount = Number(faToEn(text).replace(/\D/g, ""));
      if (uiCount === lastSeen && uiCount > 0) break;
      if (Date.now() > deadline) break;
      lastSeen = uiCount;
      await page.waitForTimeout(1_000);
    }

    console.log(`AUDIT-1: API total=${apiCount} — admin page rows=${uiCount}`);
    expect(uiCount, "admin products page must show every product the API reports").toBe(apiCount);

    // The table now paginates at 50/page; the pager must report the FULL set
    // ("نمایش X تا Y از Z مورد"), so every product stays reachable by page.
    const pagerText =
      (await page.getByText(/نمایش \d+ تا \d+ از [\d,٬\s]+ مورد/).textContent()) ?? "";
    const pagerTotal = Number(faToEn(pagerText).split("از")[1]?.replace(/\D/g, "") ?? "0");
    expect(pagerTotal, "pager must report the full catalogue size").toBe(apiCount);
  });

  test("AUDIT-2: category list is not capped at 200 rows", async ({ page }) => {
    test.setTimeout(90_000);
    await loginAdmin(page);

    const apiTotal = await page.evaluate(async () => {
      const res = await fetch(`${window.location.origin}/api/v1/catalog/categories?page_size=1`);
      const data = await res.json();
      return data.meta.total as number;
    });

    await page.goto("/admin/categories");
    await expect(page.getByRole("heading", { name: /دسته‌بندی‌های فروشگاه/ })).toBeVisible({
      timeout: BUDGET,
    });
    await page.waitForLoadState("networkidle");

    const rows = await page.locator("table tbody tr").count();
    console.log(`AUDIT-2: API categories=${apiTotal} — admin table rows(page1)=${rows}`);
    // The table paginates at 50/page now — row count pins the page size, and
    // the pager must report the FULL catalogue so every category stays
    // reachable by page.
    expect(rows).toBeGreaterThan(0);
    const pagerText =
      (await page.getByText(/نمایش \d+ تا \d+ از [\d,٬\s]+ مورد/).textContent()) ?? "";
    const pagerTotal = Number(faToEn(pagerText).split("از")[1]?.replace(/\D/g, "") ?? "0");
    console.log(`AUDIT-2: pagerTotal=${pagerTotal}`);
    expect(pagerTotal, "pager must report every category in the catalogue").toBe(apiTotal);
  });

  test("AUDIT-3: deleting a category that has products is refused with a visible error", async ({ page }) => {
    test.setTimeout(90_000);
    await loginAdmin(page);

    const target = await page.evaluate(async () => {
      const res = await fetch(`${window.location.origin}/api/v1/catalog/categories?page_size=200`);
      const data = await res.json();
      const withProducts = (
        data.items as Array<{ id: string; name: string; products_count: number }>
      ).find((c) => c.products_count > 0);
      return withProducts ?? null;
    });
    expect(target, "a category with products must exist for this audit").not.toBeNull();

    await page.goto("/admin/categories");
    await page.getByPlaceholder("جستجو در دسته‌ها...").fill(target!.name);
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: BUDGET });

    await page.getByRole("button", { name: `حذف دسته ${target!.name}` }).click();
    await page.getByRole("button", { name: "حذف دسته‌بندی" }).click(); // confirm

    // The backend must refuse; the UI must show a visible error toast.
    await expect(page.getByText("حذف دسته‌بندی انجام نشد")).toBeVisible({ timeout: 10_000 });

    // The category must still exist afterwards.
    const stillThere = await page.evaluate(async (id) => {
      const res = await fetch(`${window.location.origin}/api/v1/catalog/categories/${id}`);
      return res.ok;
    }, target!.id);
    expect(stillThere).toBe(true);
  });

  test("AUDIT-4: storefront product page shows the category name and links to its filtered grid", async ({ page }) => {
    test.setTimeout(60_000);
    await page.setExtraHTTPHeaders({ "X-Forwarded-For": freshIp() });
    await page.goto("/"); // about:blank has no origin; the app must be loaded first

    const sample = await page.evaluate(async () => {
      const res = await fetch(
        `${window.location.origin}/api/v1/catalog/products?page_size=100&is_active=true`,
      );
      const data = await res.json();
      const p = (
        data.items as Array<{
          name: string;
          slug: string;
          category_name: string | null;
          category_slug: string | null;
        }>
      ).find((x) => x.category_name && x.category_slug && !x.name.includes("ممیزی") && !x.name.includes("تست"));
      return p ?? null;
    });
    expect(sample, "a product with a category must exist").not.toBeNull();

    await page.goto(`/products/${sample!.slug}`);
    await expect(page.locator("h1")).toBeVisible({ timeout: BUDGET });

    // Category badge/link visible with the real Persian name.
    const badge = page.getByRole("link", { name: sample!.category_name! }).first();
    await expect(badge).toBeVisible({ timeout: 10_000 });

    // Clicking it lands on the filtered grid.
    await badge.click();
    await page.waitForURL(/category_(id|slug)=/, { timeout: BUDGET });

    // The grid must not be empty for a category that has products.
    await expect(page.getByText(/نمایش\s+[۱-۹]/)).toBeVisible({ timeout: 20_000 });
  });

  test("AUDIT-5: creating a product from the admin modal persists the category end-to-end", async ({ page }) => {
    test.setTimeout(90_000);
    await loginAdmin(page);

    const suffix = Date.now().toString().slice(-6);
    const catName = `ممیزی ۳۶۰ دسته ${suffix}`;
    const catSlug = `audit-cat-${suffix}`;
    const productName = `ممیزی ۳۶۰ کالا ${suffix}`;
    const sku = `SKU-AUDIT-${suffix}`;

    // 1. Create the category.
    await page.goto("/admin/categories");
    await page.getByRole("button", { name: /افزودن دسته‌بندی/ }).click();
    await page.getByPlaceholder("مثال: ساعت هوشمند").fill(catName);
    await page.getByPlaceholder("مثال: smart-watches").fill(catSlug);
    await page.getByRole("button", { name: "ثبت دسته‌بندی" }).click();
    await expect(page.getByText("دسته‌بندی ایجاد شد")).toBeVisible({ timeout: 10_000 });

    // 2. Create the product in that category.
    await page.goto("/admin/products");
    await page.getByRole("button", { name: /افزودن محصول جدید/ }).click();
    await page.locator("input#prodName").fill(productName);
    await page.locator("input#prodSku").fill(sku);
    await page.locator("input#prodPrice").fill("۱۹۹٬۰۰۰");
    await page.locator("form").getByRole("combobox").first().click();
    await page.getByRole("option", { name: catName }).click();
    await page.getByRole("button", { name: "ایجاد و ثبت محصول" }).click();

    // The submit paginates categories before POSTing; wait for the success
    // toast so the write has definitely landed before probing the API.
    await expect(page.getByText("محصول جدید با موفقیت افزوده شد")).toBeVisible({
      timeout: 60_000,
    });

    // 3. Verify the backend persisted the link (source of truth).
    let persisted: { name: string; category_name: string | null } | null = null;
    const deadline2 = Date.now() + 15_000;
    while (persisted === null && Date.now() < deadline2) {
      persisted = await page.evaluate(async (name) => {
        const res = await fetch(
          `${window.location.origin}/api/v1/catalog/products?page_size=100&q=${encodeURIComponent(name)}`,
        );
        const data = await res.json();
        const hit = (data.items as Array<{ name: string; category_name: string | null }>).find(
          (p) => p.name === name,
        );
        return hit ?? null;
      }, productName);
      if (persisted === null) await page.waitForTimeout(1_000);
    }
    expect(persisted, "created product must be readable from the API").not.toBeNull();
    expect(persisted!.category_name).toBe(catName);

    // Cleanup: delete the product then the category (own test data only).
    await page.evaluate(async ({ name, catName }) => {
      const res = await fetch(
        `${window.location.origin}/api/v1/catalog/products?page_size=100&q=${encodeURIComponent(name)}`,
      );
      const data = await res.json();
      const hit = (data.items as Array<{ id: string; name: string }>).find((p) => p.name === name);
      if (hit) await fetch(`${window.location.origin}/api/v1/catalog/products/${hit.id}`, { method: "DELETE" });
      const cats = await (
        await fetch(
          `${window.location.origin}/api/v1/catalog/categories?page_size=200&q=${encodeURIComponent(catName)}`,
        )
      ).json();
      const cat = (cats.items as Array<{ id: string; name: string }>).find((c) => c.name === catName);
      if (cat) await fetch(`${window.location.origin}/api/v1/catalog/categories/${cat.id}`, { method: "DELETE" });
    }, { name: productName, catName });
  });
});
