/**
 * HTML sitemap — a human-browsable index of everything the XML sitemaps list
 * (Rank Math Pro parity: "HTML Sitemap" option).
 *
 * This is a real page for readers, not for crawlers: it gives a lost visitor
 * a way to see the whole site at a glance, and gives every published URL one
 * more internal link (orphan pages are a real crawl problem). The data comes
 * from the same public payload the XML sitemaps use, so the two can never
 * disagree about what exists.
 *
 * It is deliberately `noindex` in spirit but NOT in tags — an HTML sitemap is
 * allowed to rank; the middleware's noindex rules do not cover it.
 */

import Link from "next/link";
import { apiInternalUrl } from "@/lib/api/server-base";

interface SectionRow {
  slug?: string;
  loc?: string;
  updated_at?: string;
}

interface Payload {
  items?: Array<{ slug: string }>;
  blog_categories?: SectionRow[];
  blog_tags?: SectionRow[];
  products?: SectionRow[];
  blog_authors?: SectionRow[];
  blog_date_archives?: SectionRow[];
}

export const metadata = {
  title: "نقشه سایت",
  description: "فهرست همهٔ صفحه‌ها، محصولات و نوشته‌های سایت",
  alternates: { canonical: "/sitemap-page" },
};

async function fetchEntries(): Promise<Payload> {
  try {
    const res = await fetch(`${apiInternalUrl()}/content/sitemap-entries`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return {};
    return (await res.json()) as Payload;
  } catch {
    return {};
  }
}

function LinkList({
  title,
  rows,
  buildHref,
}: {
  title: string;
  rows: SectionRow[] | undefined;
  buildHref: (row: SectionRow) => string;
}) {
  const items = (rows ?? []).filter((r) => r.slug || r.loc);
  if (items.length === 0) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      <ul className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
        {items.map((row) => {
          const href = buildHref(row);
          return (
            <li key={href}>
              <Link href={href} className="text-muted-foreground hover:text-foreground">
                {row.slug ?? href}
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default async function HtmlSitemapPage() {
  const payload = await fetchEntries();

  return (
    <main className="container mx-auto max-w-5xl space-y-8 px-4 py-10">
      <h1 className="text-2xl font-bold">نقشه سایت</h1>
      <LinkList
        title="صفحه‌ها"
        rows={payload.items?.map((p) => ({ slug: p.slug, loc: `/${p.slug}` }))}
        buildHref={(row) => row.loc ?? "/"}
      />
      <LinkList
        title="محصولات"
        rows={payload.products}
        buildHref={(row) => `/products/${row.slug}`}
      />
      <LinkList
        title="دسته‌بندی‌های وبلاگ"
        rows={payload.blog_categories}
        buildHref={(row) => `/blog/category/${row.slug}`}
      />
      <LinkList
        title="برچسب‌های وبلاگ"
        rows={payload.blog_tags}
        buildHref={(row) => `/blog/tag/${row.slug}`}
      />
      <LinkList
        title="نویسندگان"
        rows={payload.blog_authors}
        buildHref={(row) => row.loc ?? "/blog"}
      />
      <LinkList
        title="آرشیوها"
        rows={payload.blog_date_archives}
        buildHref={(row) => row.loc ?? "/blog"}
      />
    </main>
  );
}
