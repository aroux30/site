import type { Metadata } from "next";

import { openGraphBase } from "@/lib/seo-meta";
import { siteOrigin } from "@/lib/site-url";

export const metadata: Metadata = {
  title: "ورود به حساب کاربری",
  description: "با شماره موبایل یا رمز عبور وارد حساب کاربری خود شوید.",
  robots: { index: false, follow: true },
  openGraph: openGraphBase({ url: `${siteOrigin()}/login` }),
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
