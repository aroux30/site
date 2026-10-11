/**
 * Pins raw-HTML discoverability of the two client-rendered list pages
 * (SEO audit F-17). The check runs against the RAW HTML — not the DOM — so
 * it fails exactly when a crawler without JavaScript would fail.
 *
 * Negative test: revert either page to a pure client component (or remove
 * the CrawlableLinks block) and the corresponding test goes red.
 */
import { test, expect } from "@playwright/test";

const API = process.env.API_BASE ?? "http://localhost:8000/api/v1";

test("every post on blog page 1 is linked in raw HTML", async ({ request }) => {
  const { items } = await (
    await request.get(`${API}/blog/posts?page=1&page_size=50`)
  ).json();
  expect(items.length).toBeGreaterThan(0); // guard against a vacuous pass
  const html = await (await request.get("/blog")).text();
  for (const p of items) expect(html).toContain(`/blog/${p.slug}`);
});

test("every active product on products page 1 is linked in raw HTML", async ({
  request,
}) => {
  const { items } = await (
    await request.get(`${API}/catalog/products?is_active=true&page_size=50`)
  ).json();
  expect(items.length).toBeGreaterThan(0);
  const html = await (await request.get("/products")).text();
  for (const p of items) expect(html).toContain(`/products/${p.slug}`);
});
