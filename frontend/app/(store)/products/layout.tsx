import type { Metadata } from "next";

import { siteOrigin } from "@/lib/site-url";
import { openGraphBase } from "@/lib/seo-meta";

/** The products list is a client component (filters/sort are interactive), so
 *  its canonical is declared here. The detail route overrides this with its
 *  own canonical (verified live: `/products/<slug>` emits its own URL), so
 *  the inherited value only reaches the list itself and its query-string
 *  variants — `?sort=`, `?min_price=` — which is the documented treatment
 *  for faceted listings: canonical to the clean path. */
const canonical = `${siteOrigin().replace(/\/$/, "")}/products`;

export const metadata: Metadata = {
  title: "فروشگاه محصولات | لیست قیمت کالاها",
  description:
    "جستجو و مقایسه هزاران کالای دیجیتال با بهترین قیمت، گارانتی رسمی و ارسال سریع به سراسر ایران.",
  alternates: { canonical },
  openGraph: openGraphBase({ url: canonical }),
};

export default function ProductsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
