import type { Metadata } from "next";
import { apiInternalUrl } from "@/lib/api/server-base";
import { CrawlableLinks } from "@/components/shared/crawlable-links";
import ProductsListClient from "../../products/products-list-client";

/**
 * WordPress-style shop category archive: `/category/<slug>`.
 *
 * The list body is the same client component as `/products`; the category
 * filter is seeded from the path by `useFacetedSearch` (a server-side
 * rewrite could not feed it to `useSearchParams`, which parses the
 * browser's URL). The query forms (`/products?category_id=…`,
 * `?category_slug=…`, legacy `?category=…`) keep working unchanged.
 */
interface CategoryArchiveProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({
  params,
}: CategoryArchiveProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const res = await fetch(
      `${apiInternalUrl()}/catalog/categories/by-slug/${encodeURIComponent(slug)}`,
      { cache: "no-store" },
    );
    if (res.ok) {
      const cat = (await res.json()) as {
        name?: string;
        description?: string | null;
      };
      if (cat.name) {
        return {
          title: `${cat.name} | خرید با بهترین قیمت`,
          description:
            (cat.description || "").trim().slice(0, 160) ||
            `خرید ${cat.name} با بهترین قیمت، ضمانت اصالت و ارسال سریع`,
        };
      }
    }
  } catch {
    // Outage or unknown slug: the generic title; the page body shows the
    // honest empty/filtered state either way.
  }
  return { title: "دسته‌بندی محصولات" };
}

export default async function CategoryArchivePage({ params }: CategoryArchiveProps) {
  const { slug } = await params;

  // Same crawler-discovery pattern as /products: the list is a client
  // component, so its raw HTML contains no product links. Fetch the
  // category's products server-side and emit real anchors.
  let links: { href: string; label: string }[] = [];
  try {
    const res = await fetch(
      `${apiInternalUrl()}/catalog/products?is_active=true&category_slug=${encodeURIComponent(slug)}&page_size=50`,
      { cache: "no-store" },
    );
    if (res.ok) {
      const data = (await res.json()) as {
        items?: { slug: string; name: string }[];
      };
      links = (data.items ?? []).map((p) => ({
        href: `/products/${p.slug}`,
        label: p.name,
      }));
    }
  } catch {
    links = [];
  }

  return (
    <>
      <ProductsListClient />
      <CrawlableLinks title="محصولات این دسته" links={links} />
    </>
  );
}
