/**
 * The public origin, for anything that has to be absolute.
 *
 * JSON-LD is the reason this exists. A schema.org `logo` or `BreadcrumbList`
 * item is meaningless to a crawler unless it is an absolute URL, so those
 * strings used to be written as `https://example.com/...` — which put
 * placeholder data into every article's structured metadata. A relative
 * `metadataBase` cannot help a JSON-LD node, so it is read from the same env
 * the storefront is served from instead.
 *
 * Server-side only, and safe to call in a server component.
 */
const FALLBACK = "http://localhost:3000";

/** The site origin with no trailing slash. */
export function siteOrigin(): string {
  const configured =
    process.env.NEXT_PUBLIC_SITE_URL || process.env.SITE_URL || FALLBACK;
  return configured.replace(/\/+$/, "");
}

/** The site origin as a plain constant (same env, read at module load). */
export const SITE_URL = siteOrigin();

/** Absolute URL for a site-relative path. */
export function absoluteUrl(path = "/"): string {
  const base = siteOrigin();
  return path.startsWith("http") ? path : `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * The oEmbed discovery URL that describes *this* page.
 *
 *  The site root advertises a bare `/oembed`, which tells a reader the site can
 *  be embedded without saying which part of it. WordPress puts a per-post
 *  `<link rel="alternate" type="application/json+oembed">` in the head, and a
 *  consumer that shares one post reads that one.
 *
 *  Absolute, because a consumer fetches the link exactly as given — with no
 *  referer and no base to resolve a relative URL against. A relative discovery
 *  link is the same as no link at all.
 */
export function oembedDiscoveryUrl(path: string): string {
  const url = absoluteUrl(path);
  return `${SITE_URL}/api/v1/content/oembed?url=${encodeURIComponent(url)}&format=json`;
}
