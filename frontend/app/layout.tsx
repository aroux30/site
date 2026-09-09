import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { Providers } from "./providers";
import "./globals.css";

const vazirmatn = localFont({
  src: [
    {
      path: "../public/fonts/Vazirmatn-Variable.woff2",
      style: "normal",
    },
  ],
  variable: "--font-vazirmatn",
  display: "swap",
  fallback: ["Tahoma", "Arial", "sans-serif"],
});

export const metadata: Metadata = {
  title: {
    default: "فروشگاه آنلاین | خرید آسان و مطمئن",
    template: "%s | فروشگاه آنلاین",
  },
  description:
    "فروشگاه اینترنتی با تنوع بالای محصولات، ارسال سریع و پرداخت امن. بهترین قیمت‌ها را در فروشگاه ما پیدا کنید.",
  keywords: [
    "فروشگاه اینترنتی",
    "خرید آنلاین",
    "فروشگاه آنلاین",
    "خرید اینترنتی",
  ],
  authors: [{ name: "فروشگاه آنلاین" }],
  creator: "فروشگاه آنلاین",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
  ),
  openGraph: {
    type: "website",
    locale: "fa_IR",
    siteName: "فروشگاه آنلاین",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl" className={vazirmatn.variable}>
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
