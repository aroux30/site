/**
 * hreflang and canonical helpers.
 *
 * The backend has carried `locale` and `translation_group` on both pages and
 * posts for a while, but no route emitted the corresponding `<link
 * rel="alternate" hreflang>` tags — so the translations were unreachable to
 * search engines and to the site's own language switcher.
 *
 * One rule matters for correctness: hreflang must be self-referential. A page
 * that lists its alternates but omits its own locale is ignored by every
 * search engine, so `self` is added automatically rather than left to callers.
 */

export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"
).replace(/\/+$/, "");

export interface AlternateLocale {
  /** BCP-47 tag, e.g. "fa" or "fa-IR". */
  locale: string;
  /** Site-relative path of the translation, e.g. "/blog/my-post". */
  path: string;
}

export interface HreflangEntry {
  locale: string;
  url: string;
}

/**
 * Build the alternates map, always including the page's own locale.
 *
 * @param selfPath  site-relative path of the current page
 * @param selfLocale locale of the current page
 * @param translations other locales of the same content
 */
export function buildHreflang(
  selfPath: string,
  selfLocale: string,
  translations: AlternateLocale[] = [],
): { canonical: string; languages: Record<string, string> } {
  const entries: HreflangEntry[] = [
    { locale: selfLocale, url: absolute(selfPath) },
    // A translation can point back at the same path; dedupe by locale so a
    // duplicated key does not silently win in the object literal below.
    ...translations
      .filter((t) => t.locale && t.locale !== selfLocale && t.path)
      .map((t) => ({ locale: t.locale, url: absolute(t.path) })),
  ];

  const languages: Record<string, string> = {};
  for (const entry of entries) {
    languages[entry.locale] = entry.url;
  }
  // x-default points at the page itself so a search engine with no locale
  // preference has somewhere deterministic to land.
  languages["x-default"] = absolute(selfPath);

  return { canonical: absolute(selfPath), languages };
}

function absolute(path: string): string {
  if (!path) return SITE_URL;
  if (/^https?:\/\//i.test(path)) return path;
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

/** The Next.js `alternates` shape for a page with translations. */
export function alternatesFor(
  selfPath: string,
  selfLocale: string,
  translations: AlternateLocale[] = [],
) {
  const { canonical, languages } = buildHreflang(selfPath, selfLocale, translations);
  return { canonical, languages };
}

/** The oEmbed discovery URL that describes *this* page.
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
  const url = absolute(path);
  return `${SITE_URL}/api/v1/content/oembed?url=${encodeURIComponent(url)}&format=json`;
}
