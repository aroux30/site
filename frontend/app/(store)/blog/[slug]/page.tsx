import { cache } from "react";
import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import {
  Calendar,
  Clock,
  Eye,
  Share2,
  Tag,
  User,
  ArrowRight,
  Bookmark,
  ChevronRight,
  ChevronLeft,
  Pin,
  Sparkles,
  Images,
  Video,
  Rss,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fetchBlogPostBySlug, type PostVisibility } from "@/lib/api/blog";
import { archiveHref, postHref } from "@/lib/permalinks";
import { getRoutingConfig } from "@/lib/routing";
import { apiInternalUrl } from "@/lib/api/server-base";
import cleanHtml from "@/lib/sanitize-html";
import { extractFaqEntries, faqJsonLd } from "@/lib/content-faq";
import { safeJsonLd } from "@/lib/safe-json-ld";
import {
  fetchPublicBreadcrumbOptions,
  fetchPublicDiscussionOptions,
} from "@/lib/public-options";
import { RemoteImage } from "@/components/shared/remote-image";
import { BlogComments } from "@/components/blog/blog-comments";
import PostFormatBody, { isSpecialFormat } from "@/components/blog/post-format-body";
import { PasswordProtectedContent } from "@/components/blog/password-protected-content";
import { siteOrigin } from "@/lib/site-url";

interface BlogPostPageProps {
  params: Promise<{
    slug: string;
  }>;
}

/**
 * The post fetch, deduplicated per request.
 *
 * `generateMetadata` and the page body both need the post, and each used to
 * fetch it separately — two round trips before the first byte, and (before
 * the `track_view` flag) two view counts. `cache()` makes the second caller
 * reuse the first's promise: one fetch per request, and metadata resolves
 * sooner because it is not queued behind a second network call.
 *
 * `trackView: false` here; the page body below counts the view itself via
 * its own fetch, so metadata assembly never inflates the counter.
 */
const getPost = cache(async (slug: string) =>
  fetchBlogPostBySlug(slug, { trackView: false }),
);

/** One end of the previous/next pair. */
interface NeighborLink {
  id: string;
  slug: string;
  title: string;
  published_at: string | null;
}

/** The previous and next published post.
 *
 * The endpoint existed with no caller, so a reader who landed mid-archive had
 * no way to keep reading. Fails to nulls rather than breaking the article. */
async function getNeighbors(
  slug: string,
): Promise<{ previous: NeighborLink | null; next: NeighborLink | null }> {
  try {
    const res = await fetch(
      `${apiInternalUrl()}/blog/posts/${encodeURIComponent(slug)}/neighbors`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return { previous: null, next: null };
    return (await res.json()) as { previous: NeighborLink | null; next: NeighborLink | null };
  } catch {
    return { previous: null, next: null };
  }
}

/** One Link Genius related-post suggestion (TF-IDF ranked). */
interface GeniusRelated {
  post_id: string;
  title: string;
  slug: string;
  url: string;
  score: number;
}

/** TF-IDF related posts (Link Genius) — the fallback when the same-category
 * heuristic returns nothing (a post with no category, or the only post in its
 * category). The ranking is computed server-side from the live bodies; this
 * fetch only carries the result. Fails to an empty list, never breaking the
 * article. */
async function getGeniusRelated(slug: string, limit = 3): Promise<GeniusRelated[]> {
  try {
    const res = await fetch(
      `${apiInternalUrl()}/seo/blog/${encodeURIComponent(slug)}/related?limit=${limit}`,
      { next: { revalidate: 600 } },
    );
    if (!res.ok) return [];
    const data = (await res.json()) as { items?: GeniusRelated[] };
    return data.items ?? [];
  } catch {
    return [];
  }
}

/** Article metadata, with the site's `blog_public` switch applied.
 *
 * A layout's `robots` is not inherited once the page returns its own metadata
 * object, so the noindex has to be re-applied here — otherwise a private site
 * still had its articles indexable.
 */
export async function generateMetadata(props: BlogPostPageProps): Promise<Metadata> {
  const { searchVisible } = await fetchPublicDiscussionOptions();
  const base = await buildPostMetadata(props);
  if (!searchVisible) return { ...base, robots: { index: false, follow: true } };

  // A password-protected post is not public content, and only the title and
  // the password form render on it. The site-wide flag did not cover this:
  // `robots` was derived only from `searchVisible`, so a protected article on a
  // public site stayed indexable, inviting a crawler onto a page that yields
  // it nothing. `noindex` also stops the bare-password URL being indexed as a
  // duplicate. `private` posts are excluded the same way.
  const { slug } = await props.params;
  let visibility: PostVisibility | undefined;
  try {
    // Deduplicated fetch (see `getPost`); this is a metadata read, not a
    // reader's page view, so the shared fetch never counts a view.
    visibility = (await getPost(slug))?.visibility;
  } catch {
    visibility = undefined; // network failure: leave metadata as built
  }
  if (visibility === "password" || visibility === "private") {
    return { ...base, robots: { index: false, follow: true } };
  }
  return base;
}

async function buildPostMetadata({
  params,
}: BlogPostPageProps): Promise<Metadata> {
  const { slug } = await params;
  // Network/5xx: keep metadata generic — the page body surfaces the real
  // error via the route error boundary. Only a genuine 404 (null) below
  // means "article not found" (BUG-FE-06).
  let post: Awaited<ReturnType<typeof fetchBlogPostBySlug>> = null;
  try {
    // Deduplicated fetch (see `getPost`) — the page body's own fetch below
    // is the one that counts the view.
    post = await getPost(slug);
  } catch {
    return {
      title: "وبلاگ تخصصی",
    };
  }

  if (!post) {
    return {
      title: "مقاله یافت نشد",
    };
  }

  // Canonical URL follows the admin's permalink structure: two paths may
  // serve the same article (structured + canonical slug route), so the one
  // the operator chose is the one search engines are pointed at.
  const routing = await getRoutingConfig();
  const canonical = postHref(routing.permalink_structure, {
    slug: post.slug,
    id: post.id,
    published_at: post.published_at,
    category_slug: post.category?.slug ?? null,
    author_slug: post.author_slug ?? null,
  });

  // The operator's SEO fields win over the generated fallbacks. They existed
  // on the response (and are what a WXR import brings in from Rank Math) but
  // were never read here: a hand-tuned title was stored, displayed in the
  // admin, and then ignored by the page the crawler actually sees.
  const seo = post.seo;
  const siteName = routing.blogname || "فروشگاه";
  // Single source for the origin (SEO audit F-15): NEXT_PUBLIC_SITE_URL.
  // The DB value feeds backend-built URLs only; reading it here too could
  // publish a different canonical domain than the rest of the site.
  const siteBase = siteOrigin();

  // The share image must be one WE can serve. A cover that still points at
  // the old site (`https://arouxshop.com/…` — what a WXR import stores when
  // the sideload did not run) would break the moment that site goes away,
  // which is the whole point of a migration: og:image and twitter:image
  // would 404 and social cards would show nothing. A foreign-host URL is
  // treated as "no image" — RemoteImage already degrades the on-page cover
  // the same way, so the two agree.
  const isLocalImage = (u?: string | null): u is string =>
    !!u && (u.startsWith("/") || u.includes(new URL(siteBase).hostname));
  const ogImage = isLocalImage(seo?.og_image)
    ? seo.og_image
    : isLocalImage(post.cover_image_url)
      ? post.cover_image_url
      : undefined;

  // Absolute image URL for og:image — the stored value is site-relative
  // (`/uploads/media/…`), and Facebook/LinkedIn fetch the og:image from
  // their own servers, where a relative path means nothing.
  const absoluteOgImage = ogImage
    ? ogImage.startsWith("http")
      ? ogImage
      : `${siteBase.replace(/\/$/, "")}${ogImage.startsWith("/") ? "" : "/"}${ogImage}`
    : undefined;

  return {
    title: seo?.title || `${post.title} | وبلاگ تخصصی`,
    description: seo?.description || post.excerpt || post.title,
    // The article's own keywords, not the root layout's shop defaults. The
    // layout sets generic keywords ("فروشگاه اینترنتی, خرید آنلاین…") which
    // described the storefront, not the article — every article page showed
    // them. The focus keyword from the SEO panel wins; the post's tags are
    // the fallback; with neither, no keywords tag is emitted (better than a
    // wrong one — search engines that still read it would be misled).
    keywords:
      (seo?.focus_keyword
        ? seo.focus_keyword.split(",").map((k) => k.trim()).filter(Boolean)
        : post.tags?.map((t) => t.name)) ?? undefined,
    // `max-image-preview:large` lets Google show the full image in search
    // results (the source site sends it; without it Google may show a
    // thumbnail instead). `max-snippet:-1` lifts the snippet length cap.
    //
    // The operator's Advanced-tab choices override the defaults: an explicit
    // true forces noindex/nofollow; an explicit false forces index/follow
    // (so a page can opt back IN even when a broader rule would exclude it);
    // null/undefined means "no choice" and the defaults apply.
    robots: {
      index: seo?.robots_noindex === true ? false : true,
      follow: seo?.robots_nofollow === true ? false : true,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
    openGraph: {
      title: seo?.og_title || seo?.title || post.title,
      description: seo?.og_description || seo?.description || post.excerpt || post.title,
      // The operator's og:type when set; "article" is the correct default
      // for a blog post (Next's type union only allows a few values, so a
      // custom one goes through the `other` escape hatch below).
      type: "article",
      // og:url — the page's own address. It was missing, so a share had no
      // canonical address attached.
      url: seo?.canonical_url || canonical,
      siteName,
      locale: "fa_IR",
      publishedTime: post.published_at ?? undefined,
      modifiedTime: post.updated_at ?? undefined,
      authors: post.author_name ? [post.author_name] : undefined,
      section: post.category?.name ?? undefined,
      tags: post.tags?.map((t) => t.name) ?? undefined,
      images: absoluteOgImage ? [absoluteOgImage] : [],
    },
    twitter: {
      card: "summary_large_image",
      // Twitter overrides win over the OG values, which win over the post
      // fields — Rank Math's precedence, and the reason the Social tab's
      // fields are stored separately.
      title: seo?.twitter_title || seo?.og_title || seo?.title || post.title,
      description:
        seo?.twitter_description ||
        seo?.og_description ||
        seo?.description ||
        post.excerpt ||
        post.title,
      images: (seo?.twitter_image || absoluteOgImage)
        ? [seo?.twitter_image || absoluteOgImage || ""]
        : [],
    },
    // Twitter's author/reading-time labels. Next's `twitter` type has no
    // field for them (they are Rank Math extras the source site sends), so
    // they go through `other` — the escape hatch for arbitrary meta tags.
    // A custom og:type also rides here: Next's typed `openGraph.type` only
    // accepts a fixed union, and an operator's "product"/"video.other"
    // choice must still reach the tag.
    other: {
      ...(post.author_name ? { "twitter:label1": "نویسنده", "twitter:data1": post.author_name } : {}),
      ...(post.reading_time
        ? { "twitter:label2": "زمان خواندن", "twitter:data2": `${post.reading_time} دقیقه` }
        : {}),
      ...(seo?.og_type ? { "og:type": seo.og_type } : {}),
    },
    alternates: {
      canonical: seo?.canonical_url || canonical,
      types: {
        // Point crawlers at the article's RSS feed, the way the source site
        // does — the feed existed but nothing in the head declared it.
        // The public path, not the /api/v1 implementation detail (SEO audit
        // F-12): a reader-facing feed URL should not leak the API prefix,
        // and /blog/feed/rss is the stable public route.
        "application/rss+xml": `${siteBase.replace(/\/$/, "")}/blog/feed/rss`,
      },
    },
  };
}

export default async function BlogPostDetailPage({
  params,
}: BlogPostPageProps) {
  const { slug } = await params;
  const post = await fetchBlogPostBySlug(slug);

  if (!post) {
    notFound();
  }

  // comment_registration: the form area renders a sign-in prompt instead of
  // the composer while the gate is on. The config read fails open (guests
  // see the form); the backend still rejects a guest submission, so a
  // wrong flag here cannot open the gate.
  const { commentRegistration: requiresLogin } =
    await fetchPublicDiscussionOptions();

  // Breadcrumb display settings (Rank Math's Breadcrumbs panel): the home
  // label, the blog-crumb toggle and the separator all come from one source,
  // so the visible trail and the BreadcrumbList JSON-LD cannot disagree.
  const breadcrumbOptions = await fetchPublicBreadcrumbOptions();

  const { previous, next } = await getNeighbors(post.slug);

  // Link Genius related posts: only fetched when the same-category heuristic
  // came back empty, so the common case makes no extra request. This is the
  // consumer for the /seo/blog/{slug}/related route — a route with no caller
  // would be a gap.
  const hasCategoryRelated = (post.related_posts?.length ?? 0) > 0;
  const geniusRelated = hasCategoryRelated ? [] : await getGeniusRelated(post.slug, 3);

  // Permalink routing for the links this page renders (breadcrumbs, tag
  // chips, related posts); the canonical slug route always keeps working.
  const routing = await getRoutingConfig();

  // JSON-LD nodes need absolute URLs and the real publisher name; both were
  // hardcoded to example.com and a literal store name.
  // Same single-origin rule as above (F-15).
  const siteBase = siteOrigin();
  const siteName = routing.blogname || "فروشگاه";

  // The same canonical the head declares, for `mainEntityOfPage`.
  const canonicalForJsonLd =
    post.seo?.canonical_url ||
    `${siteBase.replace(/\/$/, "")}${postHref(routing.permalink_structure, {
      slug: post.slug,
      id: post.id,
      published_at: post.published_at,
      category_slug: post.category?.slug ?? null,
      author_slug: post.author_slug ?? null,
    })}`;

  // FAQPage structured data, when the body has a FAQ section. The API sends
  // the already-rendered body (wpautop + ToC + heading demotion applied), so
  // the heading levels here match what the reader sees.
  const faqEntries = extractFaqEntries(post.content);

  // Generate JSON-LD Structured Data.
  //
  // Completeness matters to Rich Results: Google reads `mainEntityOfPage`
  // (which page this article is ON), `wordCount` and `articleSection`
  // (used for the article rich card), and `keywords` (the focus keyword).
  // The first version carried only headline/description/dates/author, and
  // its `image` was site-relative — schema.org needs an absolute URL, so
  // Google could not fetch it.
  const jsonLdImage = post.cover_image_url
    ? post.cover_image_url.startsWith("http")
      ? post.cover_image_url
      : `${siteBase.replace(/\/$/, "")}${post.cover_image_url.startsWith("/") ? "" : "/"}${post.cover_image_url}`
    : undefined;
  const wordCount = (post.content || "")
    .replace(/<[^>]+>/g, " ")
    .split(/\s+/)
    .filter((w) => /\S/.test(w)).length;
  const focusKeywords = post.seo?.focus_keyword;

  // The operator's schema override, when one is stored (the editor's schema
  // builder writes it to seo_metadata.schema_markup). This was saved but
  // never rendered — the page always emitted its own Article node, so the
  // operator's choice had no effect on the page. When present it REPLACES
  // the Article node (Rank Math semantics: the stored schema is the page's
  // schema), while the FAQ/Breadcrumb nodes below stay independent.
  const storedSchema = post.seo?.schema_markup;

  const jsonLd =
    storedSchema && typeof storedSchema === "object" && !Array.isArray(storedSchema)
      ? storedSchema
      : {
          "@context": "https://schema.org",
          "@type": "Article",
          headline: post.title,
          description: post.seo?.description || post.excerpt,
          ...(jsonLdImage ? { image: jsonLdImage } : {}),
          datePublished: post.published_at || post.created_at,
          dateModified: post.updated_at || post.created_at,
          author: {
            "@type": "Person",
            name: post.author_name || "تیم تحریریه",
          },
          publisher: {
            "@type": "Organization",
            name: siteName,
            logo: {
              "@type": "ImageObject",
              // /logo.png answers 404 (live-verified 2026-10-10); the only
              // logo on disk is the SVG. A broken logo URL invalidates the
              // Organization node for rich results.
              url: `${siteBase}/logo.svg`,
            },
          },
          // The page this article lives on. Required for the Article rich result.
          mainEntityOfPage: {
            "@type": "WebPage",
            "@id": canonicalForJsonLd,
          },
          ...(wordCount > 0 ? { wordCount } : {}),
          ...(post.category?.name ? { articleSection: post.category.name } : {}),
          ...(focusKeywords ? { keywords: focusKeywords } : {}),
          ...(post.tags && post.tags.length > 0
            ? { about: post.tags.map((t) => ({ "@type": "Thing", name: t.name })) }
            : {}),
        };

  // BreadcrumbList JSON-LD: mirrors the visible trail so search engines can
  // render the same path in results. Built from the post itself rather than a
  // second fetch — the server component already has everything it needs.
  //
  // The trail mirrors the operator's breadcrumb settings (home label,
  // blog-crumb toggle) so the JSON-LD and the visible nav below render the
  // exact same path — a structured trail that disagrees with the page is a
  // Rich Results mismatch.
  const breadcrumbTrail: Array<{ name: string; item?: string }> = [
    { name: breadcrumbOptions.homeLabel, item: siteBase },
    ...(breadcrumbOptions.showBlog
      ? [{ name: "وبلاگ", item: `${siteBase}/blog` }]
      : []),
    ...(post.category
      ? [
          {
            name: post.category.name,
            item: `${siteBase}${archiveHref(routing, "category", post.category.slug)}`,
          },
        ]
      : []),
    { name: post.title },
  ];
  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: breadcrumbTrail.map((crumb, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: crumb.name,
      ...(crumb.item ? { item: crumb.item } : {}),
    })),
  };

  return (
    <>
      {/* Article JSON-LD Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          // safeJsonLd escapes '<', '>' and '&' as JSON unicode escapes, so
          // no value can terminate the script tag; the payload still parses
          // back to the identical object.
          __html: safeJsonLd(jsonLd),
        }}
      />

      {/* BreadcrumbList JSON-LD Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLd(breadcrumbJsonLd) }}
      />

      {/* FAQPage JSON-LD — only when the body actually carries a FAQ
          section (an H2 like "سوالات متداول" with at least two H3 Q&As).
          A guide article without one emits no node; a fake or empty FAQ
          node is a Rich Results violation. */}
      {faqEntries && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: safeJsonLd(faqJsonLd(faqEntries)) }}
        />
      )}

      <article className="container mx-auto px-4 py-10 max-w-4xl">
        {/* Breadcrumb Navigation — rendered from the same trail array the
            JSON-LD above uses, so the visible path and the structured path
            are one construction (they cannot disagree). The operator's
            settings shape both: home label, blog-crumb toggle. */}
        <nav
          aria-label="مسیر صفحه"
          className="flex items-center gap-2 text-xs md:text-sm text-muted-foreground mb-8"
        >
          {breadcrumbTrail
            .filter((crumb) => crumb.item) // current page has no link
            .map((crumb, i) => (
              <span key={crumb.item ?? i} className="flex items-center gap-2">
                {i > 0 && (
                  <span aria-hidden="true" className="text-muted-foreground/50">
                    {breadcrumbOptions.separator}
                  </span>
                )}
                <Link href={crumb.item!} className="hover:text-foreground transition-colors">
                  {crumb.name}
                </Link>
              </span>
            ))}
        </nav>

        {/* Header Title Section */}
        <header className="mb-10">
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {post.is_featured && (
              <Badge className="bg-amber-500 hover:bg-amber-600 text-white font-bold px-3 py-1 text-xs gap-1">
                <Sparkles className="w-3.5 h-3.5" />
                مطلب ویژه
              </Badge>
            )}
            {post.category && (
              <Badge className="bg-emerald-600 text-white font-bold px-3 py-1 text-xs">
                {post.category.name}
              </Badge>
            )}
            {post.post_format && post.post_format !== "standard" && (
              <Badge variant="outline" className="text-xs gap-1 border-primary/40 text-primary">
                {post.post_format === "gallery" && <Images className="w-3.5 h-3.5" />}
                {post.post_format === "video" && <Video className="w-3.5 h-3.5" />}
                {post.post_format === "gallery"
                  ? "گالری تصویر"
                  : post.post_format === "video"
                  ? "ویدیو"
                  : post.post_format}
              </Badge>
            )}
          </div>

          <h1 className="text-3xl md:text-5xl font-black leading-tight mb-6">
            {post.title}
          </h1>

          <div className="flex flex-wrap items-center justify-between gap-4 py-4 border-y border-border text-sm text-muted-foreground">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-emerald-600" />
                <span className="font-medium text-foreground">
                  {post.author_name || "تیم تحریریه"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4" />
                <span>{post.reading_time || 5} دقیقه مطالعه</span>
              </div>
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4" />
                <span>{post.view_count} بازدید</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" asChild className="gap-1.5 text-xs">
                <a href="/blog/feed/rss" target="_blank" rel="noopener noreferrer">
                  <Rss className="w-3.5 h-3.5 text-amber-500" />
                  خوراک RSS
                </a>
              </Button>
              <Button variant="outline" size="sm" className="gap-2 text-xs">
                <Share2 className="w-3.5 h-3.5" />
                اشتراک‌گذاری
              </Button>
            </div>
          </div>

          {/* Tag chips (WordPress-style flat taxonomy) */}
          {post.tags && post.tags.length > 0 && (
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <Tag className="w-4 h-4 text-muted-foreground" />
              {post.tags.map((tag) => (
                <Link
                  key={tag.id}
                  href={archiveHref(routing, "tag", tag.slug)}
                  className="rounded-full border border-border bg-muted/60 px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-emerald-500/50 hover:text-emerald-600"
                >
                  #{tag.name}
                </Link>
              ))}
            </div>
          )}
        </header>

        {/* Featured Cover Image — rendered through RemoteImage, not a raw
            `next/image`.

            A raw `Image` **throws during render** when the src host is not in
            `images.remotePatterns`, and that throw takes the whole route down:
            an imported post whose cover still points at the source site
            (e.g. `arouxshop.com` — the WXR import stores whatever the file
            carried) returned **HTTP 500 to every crawler**. Verified live:
            Googlebot/bingbot/curl all received 500 on this page. `RemoteImage`
            checks the host first and degrades to a neutral panel instead —
            which is exactly what it was built for (see
            components/shared/remote-image.tsx). The cover keeps its aspect
            ratio (`h-auto`); `priority` is passed for the LCP hint when the
            host is allowed. */}
        {post.cover_image_url && (
          <div className="relative w-full rounded-3xl overflow-hidden mb-12 shadow-2xl border border-border">
            <RemoteImage
              src={post.cover_image_url}
              alt={post.title}
              fill={false}
              priority
              className="w-full h-auto"
            />
          </div>
        )}

        {/* Excerpt Lead — withheld alongside the body for locked posts: an
            excerpt summarizes the article and would leak it. */}
        {post.excerpt && !post.content_locked && (
          <div className="p-6 bg-muted/40 rounded-2xl border-r-4 border-emerald-600 text-lg leading-relaxed font-medium mb-10 text-muted-foreground">
            {post.excerpt}
          </div>
        )}

        {/* Main Article Body — password-protected posts arrive with an empty
            body and content_locked=true; the island renders the unlock form
            and swaps in the article after a server-verified password. */}
        <div className="prose prose-lg dark:prose-invert max-w-none mb-16 leading-relaxed space-y-6 text-foreground/90">
          {post.content_locked ? (
            <PasswordProtectedContent
              slug={post.slug}
              content={post.content ?? ""}
              locked
            />
          ) : post.content ? (
            <>
              {/* A special post format gets its own presentation — a quote
                  reads as a quote, a link reads as a link. It returns null
                  for `standard`, and falls back to the body below whenever
                  the format's element is missing, so no content is lost. */}
              {isSpecialFormat(post.post_format) && (
                <PostFormatBody
                  format={post.post_format}
                  content={post.content}
                  galleryImageIds={post.gallery_image_ids ?? []}
                  excerpt={post.excerpt}
                />
              )}
              {/* The server runs wpautop, so a plain-text body arrives already
                  wrapped in paragraphs (app/shared/content/text_filters.py). The
                  split("\n\n") fallback below only ran because that filter did
                  not exist, and it disagreed with the CMS page and the feed,
                  which render the same body. Anything still un-wrapped means the
                  body bypassed the filter, so the fallback is kept for that. */}
              {/<[a-z][\s\S]*>/i.test(post.content) ? (
              <div
                dangerouslySetInnerHTML={{ __html: cleanHtml(post.content) }}
              />
            ) : (
              post.content.split("\n\n").map((para, i) => {
                if (para.startsWith("### ")) {
                  return (
                    <h3 key={i} className="text-xl font-bold mt-6 mb-3 text-emerald-600 dark:text-emerald-400">
                      {para.replace("### ", "")}
                    </h3>
                  );
                }
                if (para.startsWith("## ")) {
                  return (
                    <h2 key={i} className="text-2xl font-bold mt-8 mb-4">
                      {para.replace("## ", "")}
                    </h2>
                  );
                }
                return (
                  <p key={i} className="text-base md:text-lg leading-loose">
                    {para}
                  </p>
                );
              })
            )}
            </>
          ) : (
            <p>متن مقاله به زودی بارگذاری می‌شود.</p>
          )}
        </div>

        {/* Post navigation — a reader who lands mid-archive needs a way to
            keep reading. Renders nothing at the ends of the archive. */}
        {(previous || next) && (
          <nav
            className="mb-12 grid grid-cols-1 gap-3 sm:grid-cols-2"
            aria-label="پیمایش بین نوشته‌ها"
          >
            {previous ? (
              <Link
                href={`/blog/${previous.slug}`}
                className="group rounded-2xl border border-border p-4 transition-colors hover:border-primary/50"
              >
                <span className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <ChevronRight className="h-3.5 w-3.5" />
                  نوشتهٔ قبلی
                </span>
                <span className="line-clamp-2 block text-sm font-medium text-foreground">
                  {previous.title}
                </span>
              </Link>
            ) : (
              <span aria-hidden />
            )}
            {next ? (
              <Link
                href={`/blog/${next.slug}`}
                className="group rounded-2xl border border-border p-4 text-start transition-colors hover:border-primary/50"
              >
                <span className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                  نوشتهٔ بعدی
                  <ChevronLeft className="h-3.5 w-3.5" />
                </span>
                <span className="line-clamp-2 block text-sm font-medium text-foreground">
                  {next.title}
                </span>
              </Link>
            ) : (
              <span aria-hidden />
            )}
          </nav>
        )}

        {/* Author Bio Box */}
        <div className="p-8 rounded-3xl bg-card border border-border mb-16 shadow-sm flex items-center gap-6">
          <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-600 shrink-0">
            <User className="w-8 h-8" />
          </div>
          <div>
            <h4 className="font-bold text-lg mb-1">{post.author_name || "تیم تحریریه"}</h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              نویسنده و کارشناس ارشد بررسی سخت‌افزار و راهنمای خرید فناوری در فروشگاه اینترنتی ایرانیان.
            </p>
          </div>
        </div>

        {/* Comments Section */}
        <BlogComments
          postId={post.id}
          allowComments={post.allow_comments !== false}
          requiresLogin={requiresLogin}
        />

        {/* Related Posts */}
        {post.related_posts && post.related_posts.length > 0 && (
          <section className="pt-10 border-t border-border mt-16">
            <h3 className="text-2xl font-bold mb-8">مقالات مرتبط پیشنهادی</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {post.related_posts.map((rel) => (
                <Card
                  key={rel.id}
                  className="group overflow-hidden rounded-2xl border-border bg-card hover:shadow-lg transition-all"
                >
                  <div className="relative w-full h-40 overflow-hidden">
                    {/* A related post with no cover image must not take the
                        whole article down — see components/shared/remote-image. */}
                    <RemoteImage
                      src={rel.cover_image_url}
                      alt={rel.title}
                      className="object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  </div>
                  <CardContent className="p-5">
                    <Link href={postHref(routing.permalink_structure, { slug: rel.slug, id: rel.id, published_at: rel.published_at, category_slug: rel.category?.slug ?? null, author_slug: rel.author_slug ?? null })}>
                      <h4 className="font-bold text-sm leading-snug line-clamp-2 group-hover:text-emerald-600 transition-colors">
                        {rel.title}
                      </h4>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* Link Genius fallback: TF-IDF related posts, shown only when the
            same-category list above is empty (no category, or the only post
            in its category). A reader never reaches the end of an article
            with nowhere to go next. */}
        {geniusRelated.length > 0 && (
          <section className="pt-10 border-t border-border mt-16">
            <h3 className="text-2xl font-bold mb-8">مقالات مرتبط پیشنهادی</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {geniusRelated.map((rel) => (
                <Card
                  key={rel.post_id}
                  className="group overflow-hidden rounded-2xl border-border bg-card hover:shadow-lg transition-all"
                >
                  <CardContent className="p-5">
                    <Link href={rel.url}>
                      <h4 className="font-bold text-sm leading-snug line-clamp-2 group-hover:text-emerald-600 transition-colors">
                        {rel.title}
                      </h4>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}
      </article>
    </>
  );
}
