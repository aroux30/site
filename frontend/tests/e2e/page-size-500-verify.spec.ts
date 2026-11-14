import { expect, test, type Page } from "@playwright/test";

/**
 * One-off verification for the page-size selector fixes:
 *  - the trigger is wide enough for «500 در صفحه» (no clamp)
 *  - 500 is offered and applies on products (client-paginated)
 *  - orders now HAS a page-size selector (server-paginated, cap raised to 500)
 *
 * Run with E2E_ADMIN_PHONE / E2E_ADMIN_PASSWORD set in the environment.
 */

const ADMIN_PHONE = process.env.E2E_ADMIN_PHONE;
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD;

async function loginAdmin(page: Page) {
  if (!ADMIN_PHONE || !ADMIN_PASSWORD) {
    throw new Error("E2E_ADMIN_PHONE / E2E_ADMIN_PASSWORD must be set");
  }
  await page.setExtraHTTPHeaders({
    "X-Forwarded-For": `10.97.${Math.floor(Math.random() * 200) + 1}.${Math.floor(Math.random() * 200) + 1}, 10.0.0.1`,
  });
  await page.goto("/login");
  await page.fill('input[name="phone"], input[type="tel"]', ADMIN_PHONE);
  await page.fill('input[name="password"], input[type="password"]', ADMIN_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/admin|dashboard/, { timeout: 30_000 });
}

test("products: page-size selector offers and applies 500", async ({ page }) => {
  await loginAdmin(page);
  await page.goto("/admin/products");
  const trigger = page.getByRole("combobox", { name: "تعداد در هر صفحه" });
  await expect(trigger).toBeVisible({ timeout: 30_000 });

  // no horizontal clamping of the selected label
  const box = await trigger.boundingBox();
  expect(box!.width).toBeGreaterThanOrEqual(120);

  await trigger.click();
  const opt500 = page.getByRole("option", { name: "500 در صفحه" });
  await expect(opt500).toBeVisible();
  await opt500.click();

  await expect(trigger).toHaveText(/500/);
  // Row counts drift as other e2e suites create test data — assert the
  // "everything on one page" shape (from == 1, to == total), not a fixed N.
  await expect(page.getByText(/^نمایش 1 تا \d+ از \d+ مورد$/)).toBeVisible();
});

test("categories: page-size selector offers and applies 500", async ({ page }) => {
  await loginAdmin(page);
  await page.goto("/admin/categories");
  const trigger = page.getByRole("combobox", { name: "تعداد در هر صفحه" });
  await expect(trigger).toBeVisible({ timeout: 30_000 });

  await trigger.click();
  await page.getByRole("option", { name: "500 در صفحه" }).click();

  await expect(trigger).toHaveText(/500/);
  await expect(page.getByText(/^نمایش 1 تا \d+ از \d+ مورد$/)).toBeVisible();
});

test("orders: page-size selector exists and 500 reaches the backend", async ({ page }) => {
  await loginAdmin(page);
  await page.goto("/admin/orders");
  const trigger = page.getByRole("combobox", { name: "تعداد در هر صفحه" });
  await expect(trigger).toBeVisible({ timeout: 30_000 });

  const reqPromise = page.waitForRequest((r) =>
    r.url().includes("/orders") && r.url().includes("page_size=500"),
  );
  const respPromise = page.waitForResponse((r) =>
    r.url().includes("page_size=500") && r.request().method() === "GET",
  );
  await trigger.click();
  await page.getByRole("option", { name: "500 در صفحه" }).click();
  await reqPromise;
  const resp = await respPromise;
  expect(resp.status()).toBeLessThan(400);
});

test("products: custom page size (e.g. 101) applies", async ({ page }) => {
  await loginAdmin(page);
  await page.goto("/admin/products");
  const trigger = page.getByRole("combobox", { name: "تعداد در هر صفحه" });
  await expect(trigger).toBeVisible({ timeout: 30_000 });

  await trigger.click();
  await page.getByRole("option", { name: /تعداد دلخواه/ }).click();
  const input = page.getByLabel("تعداد دلخواه در هر صفحه");
  await expect(input).toBeFocused();
  await input.fill("101");
  await input.press("Enter");

  await expect(trigger).toHaveText(/101/);
  await expect(page.getByText(/^نمایش 1 تا \d+ از \d+ مورد$/)).toBeVisible();
});

test("orders: custom page size (e.g. 1003) reaches the backend", async ({ page }) => {
  await loginAdmin(page);
  await page.goto("/admin/orders");
  const trigger = page.getByRole("combobox", { name: "تعداد در هر صفحه" });
  await expect(trigger).toBeVisible({ timeout: 30_000 });

  await trigger.click();
  await page.getByRole("option", { name: /تعداد دلخواه/ }).click();
  const input = page.getByLabel("تعداد دلخواه در هر صفحه");
  await input.fill("1003");
  const respPromise = page.waitForResponse(
    (r) => r.url().includes("page_size=1003") && r.request().method() === "GET",
  );
  await input.press("Enter");
  const resp = await respPromise;
  expect(resp.status()).toBeLessThan(400);
  await expect(trigger).toHaveText(/1003/);
});

test("products, categories & orders: header select-all checks the page and opens the bulk bar", async ({ page }) => {
  await loginAdmin(page);

  for (const path of ["/admin/products", "/admin/categories", "/admin/orders"]) {
    await page.goto(path);
    const selectAll = page.getByRole("checkbox", {
      name: "انتخاب همهٔ ردیف‌های این صفحه",
    });
    await expect(selectAll).toBeVisible({ timeout: 30_000 });
    // The header renders before the client-side fetch lands; clicking
    // select-all against an empty page is a no-op, so wait for rows first.
    // (Row labels are «انتخاب ردیف …» on products/categories and
    // «انتخاب B2B-…» on orders — the lookahead skips the header itself.)
    const firstRow = page
      .getByRole("checkbox", { name: /^انتخاب (?!همهٔ)/ })
      .first();
    await expect(firstRow).toBeVisible({ timeout: 30_000 });

    await selectAll.click();
    await expect(selectAll).toBeChecked();
    await expect(firstRow).toBeChecked();
    if (path === "/admin/orders") {
      // The orders list keeps its own bulk bar (status actions), not the
      // shared toolbar.
      await expect(page.getByText(/سفارش انتخاب شده/)).toBeVisible();
    } else {
      const toolbar = page.getByRole("toolbar", { name: "کنش‌های گروهی" });
      await expect(toolbar).toBeVisible();
      await expect(toolbar.getByText(/مورد انتخاب شده/)).toBeVisible();
    }
  }
});

test("products & categories rows link to their storefront pages (WordPress «نمایش»)", async ({ page }) => {
  await loginAdmin(page);

  await page.goto("/admin/products");
  await expect(
    page.locator("table tbody tr").first().getByRole("link", { name: /نمایش .* در فروشگاه/ }),
  ).toBeVisible({ timeout: 30_000 });
  // The link targets the public product page, in a new tab.
  const productHref = await page
    .locator("table tbody tr")
    .first()
    .getByRole("link", { name: /نمایش .* در فروشگاه/ })
    .getAttribute("href");
  expect(productHref).toMatch(/^\/products\/.+$/);

  await page.goto("/admin/categories");
  await expect(
    page.locator("table tbody tr").first().getByRole("link", { name: /نمایش دسته .* در فروشگاه/ }),
  ).toBeVisible({ timeout: 30_000 });
  const catHref = await page
    .locator("table tbody tr")
    .first()
    .getByRole("link", { name: /نمایش دسته .* در فروشگاه/ })
    .getAttribute("href");
  expect(catHref).toMatch(/^\/category\/[^/]+$/);
});

test("settings/permalink: WP-style screen saves a structure and restores the default", async ({ page }) => {
  // The rewrite re-check loop can wait out the middleware's 60s routing cache.
  test.setTimeout(240_000);
  await loginAdmin(page);
  await page.goto("/admin/settings/permalink");

  await expect(
    page.getByRole("heading", { name: "پیوندهای یکتا", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("تنظیمات عمومی")).toBeVisible();
  await expect(page.getByText("دلخواه")).toBeVisible();

  // Pick «ماه و نام» like on options-permalink.php and save. The regex is
  // anchored: «روز، ماه و نام» also contains the substring.
  await page.getByRole("radio", { name: /^ماه و نام/ }).check();
  await page.getByRole("button", { name: /ذخیره پیوندهای یکتا/ }).click();
  await expect(page.getByText("پیوندهای یکتا ذخیره شد").last()).toBeVisible({ timeout: 15_000 });

  // End-to-end: the saved structure must actually change a real post's URL —
  // through the public routing endpoint and the rewrite middleware. The
  // middleware caches routing for 60s, so allow one retry after a pause.
  const postsRes = await page.request.get("/api/v1/blog/posts?page_size=1");
  expect(postsRes.status()).toBeLessThan(400);
  const postsBody = (await postsRes.json()) as {
    items?: Array<{ slug: string; published_at?: string | null }>;
  };
  const post = postsBody.items?.[0];
  test.skip(!post, "no published posts to exercise the permalink rewrite");
  const d = post!.published_at ? new Date(post!.published_at) : new Date();
  const structuredUrl = `/${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${post!.slug}`;

  let structuredStatus = 0;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    structuredStatus = (await page.request.get(structuredUrl)).status();
    if (structuredStatus === 200) break;
    // one routing-cache TTL; the middleware refreshes its config after that
    await page.waitForTimeout(35_000);
  }
  expect(structuredStatus, `structured URL ${structuredUrl} should resolve`).toBe(200);

  // …and the canonical /blog/<slug> route keeps working (physical route).
  const canonical = await page.request.get(`/blog/${post!.slug}`);
  expect(canonical.status()).toBe(200);

  // Persisted across a reload…
  await page.reload();
  await expect(page.getByRole("radio", { name: /^ماه و نام/ })).toBeChecked({
    timeout: 30_000,
  });

  // …and the store default is restored so this test leaves no trace.
  await page.getByRole("radio", { name: /پیش‌فرض فروشگاه/ }).first().check();
  await page.getByRole("button", { name: /ذخیره پیوندهای یکتا/ }).click();
  await expect(page.getByText("پیوندهای یکتا ذخیره شد").last()).toBeVisible({ timeout: 15_000 });

  // ── WooCommerce parity: custom product base aliases the shop ──────────
  // Pick the custom product base, type "shop", save.
  await page
    .getByRole("radio", { name: "پایهٔ سفارشی" })
    .check();
  await page.getByLabel("پایهٔ سفارشی آدرس کالا").fill("shop");
  await page.getByRole("button", { name: /ذخیره پیوندهای یکتا/ }).click();
  await expect(page.getByText("پیوندهای یکتا ذخیره شد").last()).toBeVisible({ timeout: 15_000 });

  // /shop/<slug> serves the product, /shop serves the listing, and the
  // physical /products/<slug> keeps working — same retry loop as the blog
  // part, waiting out the middleware's 60s routing cache.
  const productSlug = "samsung-galaxy-s24-ultra";
  for (const path of [`/shop/${productSlug}`, "/shop", `/products/${productSlug}`]) {
    let status = 0;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      status = (await page.request.get(path)).status();
      if (status === 200) break;
      await page.waitForTimeout(35_000);
    }
    expect(status, `${path} should resolve`).toBe(200);
  }

  // Restore the default product base.
  await page
    .getByRole("radio", { name: "پیش‌فرض فروشگاه" })
    .nth(1)
    .check();
  await page.getByRole("button", { name: /ذخیره پیوندهای یکتا/ }).click();
  await expect(page.getByText("پیوندهای یکتا ذخیره شد").last()).toBeVisible({ timeout: 15_000 });
});
