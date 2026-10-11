import { apiInternalUrl } from "@/lib/api/server-base";
import { CrawlableLinks } from "@/components/shared/crawlable-links";
import ProductsListClient from "./products-list-client";

/**
 * Thin server shell: the client list body + a server-rendered link block.
 *
 * Same reason as /blog: the product list is a client component, so the raw
 * HTML contained zero product links (live-verified 2026-10-10) and a
 * JS-less crawler could not discover the catalog. Metadata stays in
 * `products/layout.tsx`; this file exports none.
 */
export default async function ProductsPage() {
  let links: { href: string; label: string }[] = [];
  try {
    const res = await fetch(
      `${apiInternalUrl()}/catalog/products?is_active=true&page_size=50`,
      { next: { revalidate: 300 } },
    );
    if (res.ok) {
      // Live shape: {"items":[{slug, name, ...}], "meta":{...}}
      const data = (await res.json()) as {
        items?: { slug: string; name: string }[];
      };
      links = (data.items ?? []).map((p) => ({
        href: `/products/${p.slug}`,
        label: p.name,
      }));
    }
  } catch {
    // Outage: the block renders empty; the client body shows its error.
    links = [];
  }
  return (
    <>
      <ProductsListClient />
      <CrawlableLinks title="محصولات" links={links} />
    </>
  );
}
