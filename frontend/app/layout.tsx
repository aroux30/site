import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { Providers } from "./providers";
import "./globals.css";
import { apiInternalUrl } from "@/lib/api/server-base";
import { ThemePreviewBridge } from "@/components/shared/theme-preview-bridge";
import { fetchThemeTokens, themeStyleVars } from "@/lib/theme";

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

/**
 * Operator-set Site Icon (WordPress "site icon") as the favicon.
 *
 * The option holds a media URL; unset or an outage falls back to the bundled
 * /icons/icon.svg so the favicon never disappears. Read per-render (5-min
 * revalidate), not at build, so changing it in admin goes live without a
 * deploy.
 */
/**
 * The operator's branding, read once and used for the icon and the name.
 *
 * Both come from the same endpoint, so one request covers both; the previous
 * shape fetched only the icon and left the title hardcoded,
 * which is why the store's name could be set in the admin and still never
 * appear in a tab title or a search result.
 *
 * An unset name yields "" rather than a placeholder: the caller substitutes
 * the historical default, so a shop with nothing configured looks exactly as
 * it did before this existed.
 */
async function fetchBranding(): Promise<{ site_icon: string; store_name: string }> {
  const fallback = { site_icon: "/icons/icon.svg", store_name: "" };
  try {
    const res = await fetch(`${apiInternalUrl()}/settings/public/branding`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return fallback;
    const data = (await res.json()) as { site_icon?: string; store_name?: string };
    return {
      site_icon: data.site_icon?.trim() || fallback.site_icon,
      store_name: data.store_name?.trim() || "",
    };
  } catch {
    return fallback;
  }
}

export async function generateMetadata(): Promise<Metadata> {
  const branding = await fetchBranding();
  const siteIcon = branding.site_icon;
  // An unset store name keeps the historical wording, so nothing that relied
  // on it changes until the operator actually sets a name.
  const name = branding.store_name || "فروشگاه آنلاین";
  return {
    title: {
      default: `${name} | خرید آسان و مطمئن`,
      template: `%s | ${name}`,
    },
    description:
      `${name} — تنوع بالای محصولات، ارسال سریع و پرداخت امن. بهترین قیمت‌ها را در فروشگاه ما پیدا کنید.`,
    keywords: [
      "فروشگاه اینترنتی",
      "خرید آنلاین",
      "فروشگاه آنلاین",
      "خرید اینترنتی",
    ],
    authors: [{ name }],
    creator: name,
    manifest: "/manifest.json",
    metadataBase: new URL(
      process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
    ),
    // Feed autodiscovery: readers look for <link rel="alternate"> before a
    // visitor ever finds the RSS link by hand. Without these the feeds exist
    // and nobody can subscribe to them.
    //
    // These point at the public paths, not /api/v1 — the API prefix is an
    // implementation detail that changes when the service is renamed, and a
    // feed URL that 404s after such a rename breaks every existing reader.
    //
    // oEmbed discovery belongs here too: without it a third-party site that
    // pastes a product or article URL gets nothing, while the provider endpoint
    // has been public and correct the whole time.
    alternates: {
      types: {
        "application/rss+xml": [
          { url: "/blog/feed/rss", title: "نوشته‌های تازه" },
          { url: "/feed/comments/rss", title: "دیدگاه‌های تازه" },
        ],
        "application/atom+xml": [
          { url: "/blog/feed/atom", title: "نوشته‌های تازه (Atom)" },
        ],
        "application/rdf+xml": [
          { url: "/blog/feed/rdf", title: "نوشته‌های تازه (RDF)" },
        ],
        "text/json+oembed": [
          { url: "/oembed", title: "oEmbed" },
        ],
      },
    },
    openGraph: {
      type: "website",
      locale: "fa_IR",
      siteName: name,
    },
    robots: {
      index: true,
      follow: true,
    },
    icons: {
      icon: siteIcon,
      apple: siteIcon,
    },
    appleWebApp: {
      capable: true,
      statusBarStyle: "default",
      title: name,
    },
  };
}

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
  width: "device-width",
  initialScale: 1,
};

function buildSiteJsonLd(siteName: string) {
  const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
  return [
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      name: siteName,
      url: SITE_URL,
      logo: `${SITE_URL}/logo.svg`,
    },
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      name: siteName,
      url: SITE_URL,
      inLanguage: "fa-IR",
      potentialAction: {
        "@type": "SearchAction",
        target: {
          "@type": "EntryPoint",
          urlTemplate: `${SITE_URL}/products?q={search_term_string}`,
        },
        "query-input": "required name=search_term_string",
      },
    },
  ];
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Admin-editable theme tokens (CMS single type) applied as CSS vars — this
  // is what makes the ThemeEditor's colors actually reach the storefront.
  const themeTokens = await fetchThemeTokens();
  const styleVars = themeStyleVars(themeTokens) as React.CSSProperties;
  // The JSON-LD block lives in the body, outside generateMetadata, so it needs
  // the name for itself. fetchBranding is revalidate-cached, so this is a cache
  // read rather than a second request.
  const storeNameInPage = (await fetchBranding()).store_name || "فروشگاه آنلاین";

  return (
    <html lang="fa" dir="rtl" className={vazirmatn.variable} style={styleVars}>
      <body className="min-h-screen bg-background font-sans antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(buildSiteJsonLd(storeNameInPage)) }}
        />
        <Providers>{children}</Providers>
        {/* Listens for the admin theme editor's postMessage streams and
            applies them as CSS variables — what makes the preview iframe
            update per keystroke instead of per reload. A no-op in normal
            browsing (no parent-window messages arrive). */}
        <ThemePreviewBridge />
      </body>
    </html>
  );
}
