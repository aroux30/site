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
import { fetchBlogPostBySlug, fetchBlogPosts, type PostVisibility } from "@/lib/api/blog";
import { archiveHref, postHref } from "@/lib/permalinks";
import { getRoutingConfig } from "@/lib/routing";
import { apiInternalUrl } from "@/lib/api/server-base";
import { alternatesFor, type AlternateLocale } from "@/lib/hreflang";
import cleanHtml from "@/lib/sanitize-html";
import { safeJsonLd } from "@/lib/safe-json-ld";
import { fetchPublicDiscussionOptions } from "@/lib/public-options";
import { RemoteImage } from "@/components/shared/remote-image";
import { BlogComments } from "@/components/blog/blog-comments";
import PostFormatBody, { isSpecialFormat } from "@/components/blog/post-format-body";
import { PasswordProtectedContent } from "@/components/blog/password-protected-content";
import { siteOrigin } from "@/lib/site-url";
import {
  LanguageSwitcher,
  type TranslationLink,
} from "@/components/shared/language-switcher";

interface BlogPostPageProps {
  params: Promise<{
    slug: string;
  }>;
}

/** One end of the previous/next pair. */
interface NeighborLink {
  id: string;
  slug: string;
  title: string;
  published_at: string | null;
}

/** Sibling translations of the current post, resolved from the public list.
 *  Only posts sharing a translation_group are offered; a lone post renders
 *  no switcher. (Per-locale list filtering is on the routing roadmap.) */
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

async function getTranslationLinks(
  translationGroup: string,
  selfId: string,
): Promise<TranslationLink[]> {
  try {
    const res = await fetchBlogPosts({ page: 1, page_size: 100 });
    return res.items
      .filter(
        (p) =>
          p.id !== selfId &&
          p.translation_group === translationGroup &&
          p.status === "published",
      )
      .map((p) => ({
        locale: p.locale || "fa",
        href: `/blog/${p.slug}`,
        title: p.title,
      }));
  } catch {
    return [];
  }
}

/** The post's own locale plus its published translations, for hreflang.
 *
 * Backed off to a Persian default rather than propagating: hreflang is a
 * refinement, and losing it must not cost the article its metadata.
 */
async function fetchPostAlternates(
  slug: string,
): Promise<{ locale: string; translations: AlternateLocale[] }> {
  try {
    const res = await fetch(
      `${apiInternalUrl()}/blog/posts/${encodeURIComponent(slug)}/alternates`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return { locale: "fa", translations: [] };
    const data = (await res.json()) as {
      self: { locale: string };
      alternates: AlternateLocale[];
    };
    return {
      locale: data.self?.locale || "fa",
      translations: (data.alternates ?? []).filter(
        (a) => a.locale !== data.self?.locale,
      ),
    };
  } catch {
    return { locale: "fa", translations: [] };
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
    visibility = (await fetchBlogPostBySlug(slug))?.visibility;
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
    post = await fetchBlogPostBySlug(slug);
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

  // Translations come from the backend, and a failure here must not take the
  // article down — a post without hreflang is still indexable.
  const { locale, translations } = await fetchPostAlternates(post.slug);

  return {
    title: `${post.title} | وبلاگ تخصصی`,
    description: post.excerpt || post.title,
    openGraph: {
      title: post.title,
      description: post.excerpt || post.title,
      type: "article",
      publishedTime: post.published_at,
      images: post.cover_image_url ? [post.cover_image_url] : [],
    },
    alternates: alternatesFor(canonical, locale, translations),
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

  const translationLinks = post.translation_group
    ? await getTranslationLinks(post.translation_group, post.id)
    : [];

  const { previous, next } = await getNeighbors(post.slug);

  // Permalink routing for the links this page renders (breadcrumbs, tag
  // chips, related posts); the canonical slug route always keeps working.
  const routing = await getRoutingConfig();

  // JSON-LD nodes need absolute URLs and the real publisher name; both were
  // hardcoded to example.com and a literal store name.
  const siteBase = routing.site_url || siteOrigin();
  const siteName = routing.blogname || "فروشگاه";

  // Generate JSON-LD Structured Data
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.excerpt,
    image: post.cover_image_url,
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
        url: `${siteBase}/logo.png`,
      },
    },
  };

  // BreadcrumbList JSON-LD: mirrors the visible trail so search engines can
  // render the same path in results. Built from the post itself rather than a
  // second fetch — the server component already has everything it needs.
  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "خانه", item: siteBase },
      { "@type": "ListItem", position: 2, name: "وبلاگ", item: `${siteBase}/blog` },
      ...(post.category
        ? [
            {
              "@type": "ListItem",
              position: 3,
              name: post.category.name,
              item: `${siteBase}${archiveHref(routing, "category", post.category.slug)}`,
            },
          ]
        : []),
      {
        "@type": "ListItem",
        position: post.category ? 4 : 3,
        name: post.title,
      },
    ],
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

      <article className="container mx-auto px-4 py-10 max-w-4xl">
        {/* Language switcher — only rendered when sibling translations exist */}
        <LanguageSwitcher
          currentLocale={post.locale || "fa"}
          translations={translationLinks}
        />

        {/* Breadcrumb Navigation */}
        <nav className="flex items-center gap-2 text-xs md:text-sm text-muted-foreground mb-8">
          <Link href="/" className="hover:text-foreground transition-colors">
            خانه
          </Link>
          <ChevronRight className="w-3.5 h-3.5 rtl:rotate-180" />
          <Link href="/blog" className="hover:text-foreground transition-colors">
            وبلاگ
          </Link>
          {post.category && (
            <>
              <ChevronRight className="w-3.5 h-3.5 rtl:rotate-180" />
              <Link
                href={archiveHref(routing, "category", post.category.slug)}
                className="hover:text-foreground transition-colors"
              >
                {post.category.name}
              </Link>
            </>
          )}
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
                <a href="/api/v1/blog/feed/rss" target="_blank" rel="noopener noreferrer">
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

        {/* Featured Cover Image */}
        {post.cover_image_url && (
          <div className="relative w-full h-[320px] md:h-[480px] rounded-3xl overflow-hidden mb-12 shadow-2xl border border-border">
            <Image
              src={post.cover_image_url}
              alt={post.title}
              fill
              priority
              className="object-cover"
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
      </article>
    </>
  );
}
