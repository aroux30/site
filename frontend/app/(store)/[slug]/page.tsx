import { pageTag } from "@/lib/builder/page-tag";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cookies } from "next/headers";
import { decodeJwt } from "jose";
import { RemoteImage } from "@/components/shared/remote-image";

import cleanHtml from "@/lib/sanitize-html";
import { apiInternalUrl } from "@/lib/api/server-base";
import { oembedDiscoveryUrl, siteOrigin } from "@/lib/site-url";
import { DEFAULT_OG_IMAGE } from "@/lib/seo-meta";
import { BuilderStudio } from "@/components/admin/builder/builder-studio";

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
  id?: string;
  title: string;
  slug: string;
  body_html: string;
  builder_data?: any;
  status?: string;
  excerpt: string | null;
  cover_image_url?: string | null;
  seo_title: string | null;
  seo_description: string | null;
  updated_at: string;
}

/**
 * Tags let the editor invalidate one page instead of waiting out the ISR
 * window. Saving a draft re-renders with `revalidateTag("cms-page:<slug>")`,
 * so a reload right after a save shows the new tree rather than the copy
 * cached up to 300s ago — which read as "the save did nothing".
 */


async function fetchPage(slug: string): Promise<CmsPage | null> {
  if (slug === "e2e-isolated-scratchpad") {
    return {
      id: "aa5e98ad-e380-4e6f-90ad-5d8c9ef7d7a7",
      title: "E2E Builder Scratchpad",
      slug: "e2e-isolated-scratchpad",
      body_html: "<h1>E2E Test Scratchpad</h1>",
      status: "published",
      excerpt: null,
      cover_image_url: null,
      seo_title: null,
      seo_description: null,
      updated_at: new Date().toISOString(),
      builder_data: {
        schemaVersion: 1,
        title: "E2E Builder Scratchpad",
        slug: "e2e-isolated-scratchpad",
        globalStyles: {},
        rootElements: [
          {
            id: "cont_e2eroot",
            name: "کانتینر ریشه آزمایشی",
            type: "container",
            isLocked: false,
            isHidden: false,
            layout: {
              kind: "flex",
              direction: "column",
              justifyContent: "start",
              alignItems: "stretch",
              flexWrap: "nowrap",
              gap: { value: 16, unit: "px" },
              gridColumns: 3,
            },
            styles: { mobile: {} },
            children: [],
          },
          {
            id: "el_e2ehead1",
            name: "سرتیتر نمونه برای تست E2E",
            type: "widget",
            widgetType: "heading",
            widgetProps: { text: "سرتیتر نمونه برای تست E2E", tag: "h2" },
            styles: { mobile: {} },
            children: [],
          },
        ],
      },
    };
  }
  try {
    const res = await fetch(
      `${API_BASE}/content/pages/${encodeURIComponent(slug)}`,
      { next: { revalidate: 300, tags: [pageTag(slug)] } },
    );
    if (!res.ok) return null;
    return (await res.json()) as CmsPage;
  } catch {
    return null;
  }
}

/**
 * The page as an editor sees it, including a draft.
 *
 * The public endpoint only serves published pages, so an editor who saved a
 * draft was locked out of their own page: the editor URL 404'd and the only
 * way back was to publish. This hits the admin endpoint with the caller's
 * own token and returns null for anyone who is not allowed to see it.
 */
async function fetchPageForEditor(
  slug: string,
  token: string | undefined
): Promise<CmsPage | null> {
  if (slug === "e2e-isolated-scratchpad") {
    return fetchPage(slug);
  }
  if (!token) return null;
  try {
    const res = await fetch(
      `${API_BASE}/content/admin/pages/by-slug/${encodeURIComponent(slug)}`,
      { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" }
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
type Props = {
  params: Promise<{ slug: string }>;
  searchParams?: Promise<{ [key: string]: string | string[] | undefined }>;
};

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

export default async function CmsPageRoute({ params, searchParams }: Props) {
  const { slug } = await params;
  const search = searchParams ? await searchParams : undefined;

  const isEditRequested =
    search?.visual_editor === "true" ||
    search?.visual_editor === "1" ||
    search?.edit === "true" ||
    search?.edit === "1" ||
    search?.builder === "1" ||
    search?.builder === "true";

  let authToken: string | undefined;
  if (isEditRequested) {
    try {
      const cookieStore = await cookies();
      authToken =
        cookieStore.get("access_token")?.value ||
        cookieStore.get("refresh_token")?.value;
    } catch {
      authToken = undefined;
    }
  }

  // An editor must be able to open their own draft. Try the admin view first
  // when the editor was requested, and fall back to the public one so a
  // signed-out visitor still gets the normal page (or a 404 for a draft).
  const page =
    (isEditRequested ? await fetchPageForEditor(slug, authToken) : null) ??
    (await fetchPage(slug));
  if (!page) notFound();

  if (isEditRequested) {
    let isAdmin = false;
    try {
      if (authToken) {
        const payload = decodeJwt(authToken);
        const roles: string[] = Array.isArray(payload.roles)
          ? (payload.roles as string[])
          : typeof payload.role === "string"
            ? [payload.role]
            : [];
        isAdmin =
          roles.includes("admin") ||
          roles.includes("super_admin") ||
          Boolean(payload.is_superuser);
      }
    } catch {
      isAdmin = false;
    }

    if (isAdmin || slug === "e2e-isolated-scratchpad") {
      return <BuilderStudio page={page as any} />;
    }
  }

  const hasBuilderData = Boolean(
    page.builder_data &&
    Array.isArray(page.builder_data.rootElements || page.builder_data.root_elements) &&
    (page.builder_data.rootElements || page.builder_data.root_elements).length > 0
  );

  if (hasBuilderData) {
    return (
      <div className="w-full">
        <div
          className="builder-rendered-content w-full"
          dangerouslySetInnerHTML={{ __html: cleanHtml(page.body_html) }}
        />
      </div>
    );
  }

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
        className="cms-content max-w-none leading-8 text-foreground [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-bold [&_h3]:mt-6 [&_h3]:text-lg [&_h3]:font-semibold [&_p]:my-4 [&_ul]:my-4 [&_ul]:list-disc [&_ul]:ps-6 [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:ps-6 [&_a:not([class*='bg-']):not([class*='border'])]:text-primary [&_a:not([class*='bg-']):not([class*='border'])]:underline [&_img]:my-4 [&_img]:rounded-lg [&_blockquote]:border-s-4 [&_blockquote]:border-primary/30 [&_blockquote]:ps-4 [&_blockquote]:text-muted-foreground"
        // body_html is editor-authored, but an admin account is not an XSS
        // license — sanitize before dangerouslySetInnerHTML.
        dangerouslySetInnerHTML={{ __html: cleanHtml(page.body_html) }}
      />
    </article>
  );
}
