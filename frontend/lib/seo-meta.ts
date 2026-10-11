/**
 * Shared SEO metadata helpers.
 *
 * Next.js's openGraph object at the page level REPLACES the root layout's —
 * there is no deep merge. A page that sets `openGraph: { title, description }`
 * for its own title silently drops every other key the layout declared,
 * including `images`. That is why the home page had no og:image even after a
 * default was declared in the layout: the homepage's own openGraph object
 * shadowed it. These helpers build the full object so a page cannot forget
 * a key the layout intended for it.
 */

import type { Metadata } from "next";

import { siteOrigin } from "./site-url";

/** The default share image every page inherits unless it sets its own. */
export const DEFAULT_OG_IMAGE = {
  url: "/logo.svg",
  width: 1200,
  height: 630,
  alt: "فروشگاه آنلاین",
  type: "image/svg+xml",
} as const;

/**
 * A complete openGraph object a page spreads into its own metadata.
 *
 * Call it with the page's canonical URL and title; every other key the root
 * layout would have provided (siteName, locale, type, and the default share
 * image) comes along, so the page-level object no longer drops them. A page
 * with its own image overrides `images` after spreading this — the spread is
 * the merge the framework does not do.
 */
export function openGraphBase({
  url,
  siteName = "فروشگاه",
  locale = "fa_IR",
  type = "website",
}: {
  url: string;
  siteName?: string;
  locale?: string;
  type?: string;
}): NonNullable<Metadata["openGraph"]> {
  return {
    url,
    siteName,
    locale,
    type,
    images: [DEFAULT_OG_IMAGE],
  } as NonNullable<Metadata["openGraph"]>;
}
