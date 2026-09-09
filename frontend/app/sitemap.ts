import { MetadataRoute } from "next";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://91.107.144.136";

  // Static core routes
  const routes = [
    "",
    "/products",
    "/about",
    "/contact",
    "/blog",
    "/cart",
    "/login",
    "/register",
  ].map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: new Date(),
    changeFrequency: "daily" as const,
    priority: route === "" ? 1.0 : 0.8,
  }));

  // Blog posts from fallback data for indexing
  const blogSlugs = [
    "flagship-phones-buying-guide-2026",
    "ultrabook-macbook-vs-windows-comparison",
    "best-wireless-headphones-anc-2026",
    "10-tips-to-extend-smartphone-battery-life",
    "smartwatch-health-savior-or-luxury",
    "oled-vs-miniled-tv-comparison",
  ];

  const blogRoutes = blogSlugs.map((slug) => ({
    url: `${baseUrl}/blog/${slug}`,
    lastModified: new Date(),
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));

  return [...routes, ...blogRoutes];
}
