import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RemoteImage } from "@/components/shared/remote-image";

import cleanHtml from "@/lib/sanitize-html";
import { apiInternalUrl } from "@/lib/api/server-base";
import { oembedDiscoveryUrl, siteOrigin } from "@/lib/site-url";
import { DEFAULT_OG_IMAGE } from "@/lib/seo-meta";

// CMS pages are the editable storefront copy (about, terms, returns, …). The
// backend is the source of truth; this route renders whatever slug an editor
// published under the store's public URL space.

const API_BASE = apiInternalUrl();

/**
 * The storefront's view of a page.
 *
 * Declared locally rather than imported because this page is a server
 * component and the shared type in lib/api/content.ts pulls in the axios
 * client, which has no business being in a server bundle. Only the fields
 * this page actually reads are listed — and `cover_image_url` is one of them,
 * so it is here rather than in a second, drifted copy.
 */
interface CmsPage {
  title: string;
  slug: string;
  body_html: string;
  excerpt: string | null;
  cover_image_url?: string | null;
  seo_title: string | null;
  seo_description: string | null;
  updated_at: string;
}

async function fetchPage(slug: string): Promise<CmsPage | null> {
  try {
    const res = await fetch(
      `${API_BASE}/content/pages/${encodeURIComponent(slug)}`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return null;
    return (await res.json()) as CmsPage;
  } catch {
    return null;
  }
}

// Next 15 hands route params to the page as a Promise; reading `.slug` off the
// raw object is a deprecation that logs an error per request and will stop
// working. The other dynamic routes (blog/[slug], tickets/[id], …) already
// await it — this one page was still on the old shape.
type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const page = await fetchPage(slug);
  if (!page) return {};
  // A page with no hand-written description must not ship an empty one:
  // Google fills the gap itself with body text (which is usually worse), and
  // an absent meta description is a Lighthouse "missing description" finding.
  // The first ~160 characters of the body, with tags stripped, is a better
  // fallback than nothing — same rule as the blog's excerpt. The only case a
  // page has no body text is a template stub (shortcode shells), which the
  // operator's editor is the right place to fix, not an empty meta tag.
  const fallbackDescription =
    page.body_html
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 160) || undefined;

  return {
    title: page.seo_title || page.title,
    description:
      page.seo_description || page.excerpt || fallbackDescription,
    // oEmbed discovery for this page, not just the site root.
    //
    // The root layout advertises `/oembed` with no `url`, which tells a reader
    // the site can be embedded but not *this page* — so a post shared into
    // Slack, Telegram or a chat client has nothing to attach. The discovery URL
    // is per-page by specification, and this is where it belongs.
    //
    // The absolute URL needs the canonical host: oEmbed consumers fetch the
    // link as given, with no referer to infer a base from, so a relative one
    // resolves against nothing.
    alternates: {
      canonical: `${siteOrigin()}/${slug}`,
      types: {
        "text/json+oembed": [{ url: oembedDiscoveryUrl(`/${slug}`) }],
      },
    },
    openGraph: {
      title: page.seo_title || page.title,
      description: fallbackDescription,
      type: "article",
      // og:url is the PAGE's own address, not the oembed endpoint: the first
      // version pointed every shared CMS page at /api/v1/content/oembed, so
      // Facebook's crawler showed an API URL as the canonical address.
      url: `${siteOrigin()}/${slug}`,
      // The default share image the root layout declares is shadowed by this
      // page-level object (Next.js replaces openGraph rather than merging), so
      // it is repeated here — same reason every list page repeats it.
      images: [DEFAULT_OG_IMAGE],
    },
  };
}

export default async function CmsPageRoute({ params }: Props) {
  const { slug } = await params;
  const page = await fetchPage(slug);
  if (!page) notFound();

  return (
    <article className="mx-auto max-w-3xl px-4 py-10">
      {/* Hero image. RemoteImage because a cover can point at a host that is
          not in next.config's remotePatterns; a bare next/image throws there
          and takes the page down with it. */}
      {page.cover_image_url && (
        <div className="relative mb-8 h-56 w-full overflow-hidden rounded-2xl border border-border md:h-80">
          <RemoteImage
            src={page.cover_image_url}
            alt={page.title}
            className="h-full w-full object-cover"
            sizes="(max-width: 768px) 100vw, 768px"
            priority
          />
        </div>
      )}
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">{page.title}</h1>
        {page.excerpt ? (
          <p className="mt-3 text-muted-foreground">{page.excerpt}</p>
        ) : null}
      </header>
      <div
        className="cms-content max-w-none leading-8 text-foreground [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-bold [&_h3]:mt-6 [&_h3]:text-lg [&_h3]:font-semibold [&_p]:my-4 [&_ul]:my-4 [&_ul]:list-disc [&_ul]:ps-6 [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:ps-6 [&_a]:text-primary [&_a]:underline [&_img]:my-4 [&_img]:rounded-lg [&_blockquote]:border-s-4 [&_blockquote]:border-primary/30 [&_blockquote]:ps-4 [&_blockquote]:text-muted-foreground"
        // body_html is editor-authored, but an admin account is not an XSS
        // license — sanitize before dangerouslySetInnerHTML.
        dangerouslySetInnerHTML={{ __html: cleanHtml(page.body_html) }}
      />
    </article>
  );
}
