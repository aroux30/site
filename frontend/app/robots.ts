import { MetadataRoute } from "next";

import { fetchPublicDiscussionOptions } from "@/lib/public-options";

export default async function robots(): Promise<MetadataRoute.Robots> {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

  // The blog can be switched off in Settings → Reading. That already emits a
  // `noindex` meta tag on the blog subtree, but a crawler that honours
  // robots.txt and ignores meta robots would still walk it — and this file
  // used to advertise the sitemap unconditionally, which points at the blog
  // entries. Read the same public flag the blog metadata reads, so the two
  // surfaces cannot disagree.
  const { searchVisible } = await fetchPublicDiscussionOptions();

  return {
    rules: [
      {
        userAgent: "*",
        ...(searchVisible ? { allow: "/" } : { disallow: ["/"] }),
        disallow: searchVisible
          ? [
              "/admin/",
              "/account/",
              "/checkout/",
              "/api/",
              // Result pages are an unbounded crawlable parameter space
              // (?q=&category=&min_price=&sort=) that all emit the same `products`
              // metadata — indexable thin duplicates, and they compete with the
              // category pages that are actually meant to rank.
              "/search",
            ]
          : [],
      },
      {
        userAgent: ["GPTBot", "CCBot", "ClaudeBot", "anthropic-ai", "Bytespider"],
        disallow: ["/"],
      },
    ],
    // No point advertising a sitemap when the whole site is disallowed.
    ...(searchVisible ? { sitemap: `${baseUrl}/sitemap.xml` } : {}),
  };
}
