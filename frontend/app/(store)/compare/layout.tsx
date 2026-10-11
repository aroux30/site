import type { Metadata } from "next";

import { openGraphBase } from "@/lib/seo-meta";
import { siteOrigin } from "@/lib/site-url";

export const metadata: Metadata = {
  title: "مقایسه کالاها",
  description: "مقایسه مشخصات فنی کالاهای انتخابی شما.",
  robots: { index: false, follow: true },
  openGraph: openGraphBase({ url: `${siteOrigin()}/compare` }),
};

export default function CompareLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
