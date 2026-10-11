import type { Metadata } from "next";

import { openGraphBase } from "@/lib/seo-meta";
import { siteOrigin } from "@/lib/site-url";

export const metadata: Metadata = {
  title: "علاقه‌مندی‌های من",
  description: "فهرست کالاهای نشان‌شده شما.",
  robots: { index: false, follow: true },
  // noindex — but a share of the page still needs a card, which is why the
  // og fields live here rather than a canonical.
  openGraph: openGraphBase({ url: `${siteOrigin()}/wishlist` }),
};

export default function FavoritesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
