import type { Metadata } from "next";

import { siteOrigin } from "@/lib/site-url";
import { openGraphBase } from "@/lib/seo-meta";

const canonical = `${siteOrigin()}/faq`;

export const metadata: Metadata = {
  title: "سوالات متداول",
  description:
    "پاسخ سوالات متداول درباره سفارش، ارسال، بازگشت کالا و حساب کاربری در فروشگاه آنلاین ما را بیابید.",
  // A relative canonical resolves against metadataBase, but the value is a
  // crawler-facing URL and an absolute one cannot be misread — same absolute
  // form the product and blog lists use.
  alternates: { canonical },
  openGraph: openGraphBase({ url: canonical }),
};

export default function FAQLayout({ children }: { children: React.ReactNode }) {
  return children;
}
