import type { Metadata } from "next";
import { notFound } from "next/navigation";

import cleanHtml from "@/lib/sanitize-html";
import { apiInternalUrl } from "@/lib/api/server-base";
import { alternatesFor, type AlternateLocale } from "@/lib/hreflang";

// CMS pages are the editable storefront copy (about, terms, returns, …). The
// backend is the source of truth; this route renders whatever slug an editor
// published under the store's public URL space.

const API_BASE = apiInternalUrl();

interface CmsPage {
  title: string;
  slug: string;
  body_html: string;
  excerpt: string | null;
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

interface PageAlternates {
  self: { locale: string; slug: string };
  alternates: AlternateLocaleWithSlug[];
}

interface AlternateLocaleWithSlug extends AlternateLocale {
  slug: string;
}

// Translation siblings come from the backend rather than being guessed, and
// a failure here must not take the page down: a page without hreflang is
// still indexable, a page that 500s is not.
async function fetchAlternates(slug: string): Promise<{
  locale: string;
  translations: AlternateLocale[];
}> {
  try {
    const res = await fetch(
      `${API_BASE}/content/pages/${encodeURIComponent(slug)}/alternates`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return { locale: "fa", translations: [] };
    const data = (await res.json()) as PageAlternates;
    return {
      locale: data.self?.locale || "fa",
      translations: (data.alternates ?? [])
        .filter((a) => a.locale !== data.self?.locale)
        .map((a) => ({ locale: a.locale, path: a.path })),
    };
  } catch {
    return { locale: "fa", translations: [] };
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
  const { locale, translations } = await fetchAlternates(slug);
  return {
    title: page.seo_title || page.title,
    description: page.seo_description || page.excerpt || undefined,
    alternates: alternatesFor(`/${slug}`, locale, translations),
    openGraph: {
      title: page.seo_title || page.title,
      description: page.seo_description || page.excerpt || undefined,
      type: "article",
    },
  };
}

export default async function CmsPageRoute({ params }: Props) {
  const { slug } = await params;
  const page = await fetchPage(slug);
  if (!page) notFound();

  return (
    <article className="mx-auto max-w-3xl px-4 py-10">
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
