import type { Metadata } from "next";

import { openGraphBase } from "@/lib/seo-meta";
import { siteOrigin } from "@/lib/site-url";

/**
 * Result pages must not be indexed.
 *
 * This page is a client component, so it cannot export `metadata` itself. Its
 * query space (`?q=&category=&min_price=&max_price=&sort=&page=`) is unbounded
 * and every combination emits the same `products` metadata, which turns the
 * site's crawl budget into thin duplicates competing with the category pages
 * that are meant to rank. `robots.ts` disallows the route; this tag is the
 * belt-and-braces half, because a disallowed URL that is still linked from
 * elsewhere can be indexed as "indexed, though blocked by robots.txt".
 */
export const metadata: Metadata = {
  // The root layout's title template appends "| <site name>" itself; adding
  // it here produced "جستجو | فروشگاه | فروشگاه" (verified live 2026-10-10).
  title: "جستجو",
  robots: { index: false, follow: true },
  openGraph: openGraphBase({ url: `${siteOrigin()}/search` }),
};

export default function SearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
