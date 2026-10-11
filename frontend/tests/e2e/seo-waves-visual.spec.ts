/**
 * Physical, visual E2E verification of the SEO waves + the storefront fixes.
 *
 * Runs against the live stack (dev server on :3000, backend on :8000).
 * Every assertion is a real browser observation — a rendered element, a
 * network response, or a screenshot — not a source-code read.
 *
 * Coverage:
 * - Products grid lists products (the ES-down Postgres fallback) + simplified
 *   mode banner.
 * - Compare page has NO flagship demo remnants (the removed fake products).
 * - Blog post renders breadcrumb nav + BreadcrumbList JSON-LD from the same
 *   trail (wave E) and the operator's meta title reaches the head (wave B).
 * - Product page emits Product JSON-LD with offers (wave F regression guard).
 * - /sitemap.xml, /news-sitemap.xml, /robots.txt serve valid content (wave A).
 */

import { test, expect } from "@playwright/test";

test.describe("storefront SEO waves — visual E2E", () => {
  test("products grid lists real products (ES-down fallback)", async ({ page }) => {
    await page.goto("/products");

    // Wait for data first: the page is a client component, so the initial
    // paint legitimately shows the zero-state before the fetch resolves.
    // Asserting on the pre-fetch frame would race, not test the fallback.
    const productLinks = page.locator('a[href^="/products/"]');
    await expect(productLinks.first()).toBeVisible({ timeout: 20_000 });
    const count = await productLinks.count();
    expect(count).toBeGreaterThan(0);

    // After the fetch resolves, the zero count must be gone.
    await expect(page.getByText("نمایش ۰ کالا")).toHaveCount(0, {
      timeout: 10_000,
    });

    // The simplified-mode banner appears (ES is down in this environment).
    await expect(
      page.getByText("حالت ساده‌شده", { exact: false }),
    ).toBeVisible();

    await page.screenshot({
      path: "tests/e2e/__screenshots__/products-grid.png",
      fullPage: false,
    });
  });

  test("compare page carries no flagship demo", async ({ page }) => {
    await page.goto("/compare");

    // The empty state (store starts empty) must NOT show the removed demo.
    await expect(page.getByText("پرچمدار", { exact: false })).toHaveCount(0);
    await expect(page.getByText("Galaxy S24", { exact: false })).toHaveCount(0);
    await expect(page.getByText("Zenbook", { exact: false })).toHaveCount(0);

    // The real path (browse products) is still offered.
    await expect(
      page.getByRole("link", { name: /افزودن محصول به لیست مقایسه/ }),
    ).toBeVisible();

    await page.screenshot({
      path: "tests/e2e/__screenshots__/compare-empty.png",
    });
  });

  test("blog post: breadcrumb nav + JSON-LD + meta title", async ({ page }) => {
    await page.goto("/blog/pubg-mobile");

    // Visible breadcrumb nav (wave E) — one trail with the operator's labels.
    const nav = page.locator('nav[aria-label="مسیر صفحه"]');
    await expect(nav).toBeVisible();
    await expect(nav.getByText("خانه", { exact: true })).toBeVisible();

    // BreadcrumbList + Article JSON-LD present in the DOM.
    const jsonLdBlocks = await page
      .locator('script[type="application/ld+json"]')
      .allTextContents();
    const joined = jsonLdBlocks.join("\n");
    // safeJsonLd serializes compact JSON (no spaces after colons).
    expect(joined).toContain('"@type":"BreadcrumbList"');
    expect(joined).toContain('"@type":"Article"');

    // The head title is a real string (wave B meta pipeline).
    const title = await page.title();
    expect(title.length).toBeGreaterThan(5);

    await page.screenshot({
      path: "tests/e2e/__screenshots__/blog-post.png",
      fullPage: false,
    });
  });

  test("product page: Product JSON-LD with offers (F regression)", async ({ page }) => {
    // Find a real product slug from the grid first.
    await page.goto("/products");
    const firstLink = page.locator('a[href^="/products/"]').first();
    await expect(firstLink).toBeVisible({ timeout: 20_000 });
    const href = await firstLink.getAttribute("href");
    expect(href).toBeTruthy();

    await page.goto(href!);
    // Wait for the client render — the PDP fetches its data, so an early
    // screenshot would capture the skeleton, not the product.
    await expect(page.locator("h1")).toBeVisible({ timeout: 20_000 });

    const jsonLdBlocks = await page
      .locator('script[type="application/ld+json"]')
      .allTextContents();
    const joined = jsonLdBlocks.join("\n");
    expect(joined).toContain('"@type":"Product"');
    // The P0 regression guard: offers must be present (the generated stub
    // once shadowed this node and dropped price/availability).
    expect(joined).toContain('"offers"');
    expect(joined).toContain('"price"');
    // The price-range fix: a real product's offer must carry a NON-ZERO
    // price (the detail response once dropped min_price and every offer
    // shipped "price":0 — Google rejects a zero-priced offer).
    const priceMatch = joined.match(/"price":(\d+)/);
    expect(priceMatch).toBeTruthy();
    expect(Number(priceMatch![1])).toBeGreaterThan(0);
    // No fabricated 4.7 with zero reviews.
    if (joined.includes('"aggregateRating"')) {
      expect(joined).toContain('"reviewCount"');
    }

    await page.screenshot({
      path: "tests/e2e/__screenshots__/product-detail.png",
      fullPage: false,
    });
  });

  test("crawler files: sitemap, news sitemap, robots", async ({ request }) => {
    const sitemap = await request.get("/sitemap.xml");
    expect(sitemap.status()).toBe(200);
    const sitemapText = await sitemap.text();
    expect(sitemapText).toContain("<urlset");
    expect(sitemapText).toContain("<loc>");
    // The fixed author route, not the old 404 path.
    expect(sitemapText).not.toContain("/blog/authors/");

    const news = await request.get("/news-sitemap.xml");
    expect(news.status()).toBe(200);
    const newsText = await news.text();
    // Valid empty file when no post was published in Google's 48h window —
    // the namespace declaration is the invariant, not an entry.
    expect(newsText).toContain("sitemap-news/0.9");
    expect(newsText).toContain("<urlset");

    const robots = await request.get("/robots.txt");
    expect(robots.status()).toBe(200);
    const robotsText = await robots.text();
    expect(robotsText).toContain("Sitemap:");
    expect(robotsText).toContain("news-sitemap.xml");
  });
});
