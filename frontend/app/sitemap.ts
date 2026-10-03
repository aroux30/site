import { MetadataRoute } from "next";
import { fetchBlogPosts } from "@/lib/api/blog";
import type { BlogPost } from "@/lib/api/blog";

/** Upper bound on sitemap paging: 100 pages x 100 = 10,000 posts.
 *  Past that a blog wants a real sitemap index rather than one file. */
const MAX_SITEMAP_PAGES = 100;
import {
  DEFAULT_ROUTING,
  archiveHref,
  postHref,
  type RoutingConfig,
} from "@/lib/permalinks";
import { getRoutingConfig } from "@/lib/routing";
import { apiInternalUrl } from "@/lib/api/server-base";

interface CmsPageSitemapRow {
  slug: string;
  locale?: string;
  updated_at?: string;
}

interface SitemapSectionRow {
  slug: string;
  updated_at?: string;
  changefreq?: string;
  priority?: number;
  /**
   * A rooted path, for sections that are not a bare slug: an author archive is
   * "/blog/authors/<slug>" and a date archive is "/archive/<year>/<month>", so
   * there is no slug to append — the backend sends the path itself.
   */
  loc?: string;
  /** Relative or absolute; resolved against the site URL before it is emitted. */
  image_url?: string;
}

interface SitemapEntriesPayload {
  // Legacy keys of GET /content/pages — unchanged contract for CMS pages.
  items?: CmsPageSitemapRow[];
  total?: number;
  // Additive sitemap-completeness sections served by GET /content/sitemap-entries.
  blog_categories?: SitemapSectionRow[];
  blog_tags?: SitemapSectionRow[];
  products?: SitemapSectionRow[];
  // Author and date archives, added for the same reason: the pages existed and
  // were crawlable, but nothing pointed a crawler at them.
  blog_authors?: SitemapSectionRow[];
  blog_date_archives?: SitemapSectionRow[];
}

async function fetchSitemapEntries(): Promise<SitemapEntriesPayload> {
  const apiBase = apiInternalUrl();
  try {
    // The public route, not the admin one. `/content/admin/pages` is behind
    // `settings:write`, and this fetch has no session — it answered 401,
    // which the `!res.ok` branch below swallowed, so CMS pages silently never
    // reached the sitemap. The public sitemap route returns only what a
    // crawler needs (slug/locale/dates per section).
    const res = await fetch(`${apiBase}/content/sitemap-entries`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) {
      // Loud, because a silent {} here is indistinguishable from "no URLs".
      console.error(
        `sitemap: sitemap-entries request returned ${res.status}; dynamic URLs omitted`,
      );
      return {};
    }
    return (await res.json()) as SitemapEntriesPayload;
  } catch (error) {
    console.error("sitemap: failed to fetch sitemap entries; dynamic URLs omitted", error);
    return {};
  }
}

type ChangeFrequency = NonNullable<MetadataRoute.Sitemap[number]["changeFrequency"]>;

/**
 * A stored media path as an absolute URL.
 *
 * Cover images are stored as a path ("/uploads/media/x.png") but a sitemap
 * entry needs a full URL, and a relative one is silently ignored by crawlers.
 * An already-absolute URL is passed through rather than prefixed twice, which
 * is what would happen if a CDN-hosted image were stored absolute.
 */
function absoluteMedia(src: string): string {
  if (/^https?:\/\//i.test(src)) return src;
  return src.startsWith("/") ? src : `/${src}`;
}

function sectionRoutes(
  baseUrl: string,
  rows: SitemapSectionRow[] | undefined,
  buildUrl: (slug: string) => string,
  fallback: { changeFrequency: ChangeFrequency; priority: number },
): MetadataRoute.Sitemap {
  return (rows ?? []).map((row) => ({
    url: buildUrl(row.slug),
    // No date means no date. Falling back to `new Date()` told a crawler the
    // page changed on every single crawl, which erodes trust in lastmod across
    // the whole sitemap rather than helping any one row.
    ...(row.updated_at ? { lastModified: new Date(row.updated_at) } : {}),
    // The backend sends lowercase sitemap values ("daily"/"weekly"/"monthly").
    changeFrequency: (row.changefreq ?? fallback.changeFrequency) as ChangeFrequency,
    priority: row.priority ?? fallback.priority,
    ...(row.image_url
      ? { images: [`${baseUrl}${absoluteMedia(row.image_url)}`] }
      : {}),
  }));
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

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

  // Admin-configured permalink structure shapes every blog URL the sitemap
  // advertises; a failure to load it degrades to the canonical paths, which
  // the middleware always serves.
  let routing: RoutingConfig = DEFAULT_ROUTING;
  try {
    routing = await getRoutingConfig();
  } catch {
    routing = DEFAULT_ROUTING;
  }

  // Blog posts advertised to search engines come from the CMS only — a
  // hardcoded slug list would send crawlers to 404s.
  let blogRoutes: MetadataRoute.Sitemap = [];
  try {
    // Page through the whole archive. The old call asked for one page of 100
    // and stopped, so on a blog with more than 100 posts every older article
    // silently dropped out of the sitemap — the posts that had the most
    // settled URLs, and the ones a new site most needs indexed.
    const posts: BlogPost[] = [];
    const PAGE = 100;
    for (let page = 1; page <= MAX_SITEMAP_PAGES; page += 1) {
      const batch = await fetchBlogPosts({ page, page_size: PAGE });
      const items = batch.items || [];
      posts.push(...items);
      if (items.length < PAGE || !batch.has_next) break;
    }
    blogRoutes = posts.map((post) => ({
      url: `${baseUrl}${postHref(routing.permalink_structure, {
        slug: post.slug,
        id: post.id,
        published_at: post.published_at,
        category_slug: post.category?.slug ?? null,
        author_slug: post.author_slug ?? null,
      })}`,
      // No date means no date, as in sectionRoutes: a fabricated lastmod says
      // "changed today" on every crawl, which crawlers discount for the whole
      // sitemap rather than for one row.
      ...(post.updated_at ? { lastModified: new Date(post.updated_at) } : {}),
      changeFrequency: "weekly" as const,
      priority: 0.7,
      // A post's cover image is the result a search engine shows next to the
      // link, and image search is a real source of traffic for a shop with
      // illustrated articles. Without it the page ranks on text alone.
      ...(post.cover_image_url
        ? { images: [`${baseUrl}${absoluteMedia(post.cover_image_url)}`] }
        : {}),
    }));
  } catch (error) {
    // A blog outage must not break the whole sitemap, but it must not be
    // silent either — log so the dropped blog URLs are visible in build logs.
    console.error("sitemap: failed to fetch blog posts; blog URLs omitted", error);
    blogRoutes = [];
  }

  // Taxonomy archives, published CMS pages, and active products now come from
  // one backend payload (GET /content/sitemap-entries). The backend skips a
  // failed section server-side, so per-section try/catch moved there — this
  // side only guards the fetch itself.
  const payload = await fetchSitemapEntries();

  const archiveRoutes: MetadataRoute.Sitemap = [
    ...sectionRoutes(
      baseUrl,
      payload.blog_categories,
      (slug) => `${baseUrl}${archiveHref(routing, "category", slug)}`,
      { changeFrequency: "weekly", priority: 0.6 },
    ),
    ...sectionRoutes(
      baseUrl,
      payload.blog_tags,
      (slug) => `${baseUrl}${archiveHref(routing, "tag", slug)}`,
      { changeFrequency: "weekly", priority: 0.5 },
    ),
  ];

  const productRoutes: MetadataRoute.Sitemap = sectionRoutes(
    baseUrl,
    payload.products,
    (slug) => `${baseUrl}/products/${slug}`,
    { changeFrequency: "daily", priority: 0.7 },
  );

  // Author and date archives arrive with a rooted `loc` rather than a slug —
  // an archive is a path with its own shape ("/archive/2026/3"), not a slug —
  // so they are read by their own field instead of going through buildUrl.
  const locRoutes = (
    rows: SitemapSectionRow[] | undefined,
    fallback: { changeFrequency: ChangeFrequency; priority: number },
  ): MetadataRoute.Sitemap =>
    // A row without a loc is skipped rather than rendered as baseUrl +
    // "undefined": the backend always sends one for these sections, and a
    // malformed row should disappear from a sitemap, not become a URL a
    // crawler will fetch.
    (rows ?? [])
      .filter((row): row is SitemapSectionRow & { loc: string } => Boolean(row.loc))
      .map((row) => ({
        url: `${baseUrl}${row.loc}`,
        ...(row.updated_at ? { lastModified: new Date(row.updated_at) } : {}),
        changeFrequency: fallback.changeFrequency,
        priority: fallback.priority,
      }));

  const authorRoutes: MetadataRoute.Sitemap = locRoutes(payload.blog_authors, {
    changeFrequency: "weekly",
    priority: 0.5,
  });
  const dateArchiveRoutes: MetadataRoute.Sitemap = locRoutes(
    payload.blog_date_archives,
    { changeFrequency: "monthly", priority: 0.4 },
  );

  // Published CMS pages (editor-managed storefront pages).
  const staticPaths = new Set(routes.map((r) => r.url));
  const cmsRoutes: MetadataRoute.Sitemap = (payload.items ?? [])
    .filter((page) => !staticPaths.has(`${baseUrl}/${page.slug}`))
    .map((page) => ({
      url: `${baseUrl}/${page.slug}`,
      lastModified: page.updated_at ? new Date(page.updated_at) : new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.5,
    }));

  return [
    ...routes,
    ...blogRoutes,
    ...archiveRoutes,
    ...productRoutes,
    ...authorRoutes,
    ...dateArchiveRoutes,
    ...cmsRoutes,
  ];
}
