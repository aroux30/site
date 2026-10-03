import { notFound } from "next/navigation";
import cleanHtml from "@/lib/sanitize-html";
import { BlogComments } from "@/components/blog/blog-comments";

/**
 * CMS-backed storefront page body (server component).
 *
 * The storefront previously shipped static JSX for /about, /terms, /privacy,
 * and /returns. Next.js route precedence made those files win over the generic
 * CMS `[slug]` route, so editor changes in the admin panel never reached
 * customers. Each of those routes now renders this component: published CMS
 * content wins, and the original static layout stays as the fallback for
 * installs that have not created the page yet.
 */

import { apiInternalUrl } from "@/lib/api/server-base";

const API_BASE = apiInternalUrl();

export interface CmsPageContent {
  title: string;
  slug: string;
  body_html: string;
  excerpt: string | null;
  seo_title: string | null;
  seo_description: string | null;
  /** Needed to address the comment thread: comments are keyed by page id,
   *  and the slug alone cannot identify one. */
  id?: string;
  /** Server-owned opt-in. A page renders no thread unless its editor enabled
   *  comments, which is what keeps a legal or policy page quiet. */
  allow_comments?: boolean;
}

export async function fetchCmsPage(slug: string): Promise<CmsPageContent | null> {
  try {
    const res = await fetch(
      `${API_BASE}/content/pages/${encodeURIComponent(slug)}`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return null;
    return (await res.json()) as CmsPageContent;
  } catch {
    return null;
  }
}

interface CmsPageShellProps {
  slug: string;
  /** Rendered when no published CMS page exists for this slug. */
  fallback: React.ReactNode;
}

export default async function CmsPageShell({ slug, fallback }: CmsPageShellProps) {
  const page = await fetchCmsPage(slug);
  if (!page) return <>{fallback}</>;

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

      {/* Comments on a CMS page. The backend already accepted them on this
          resource type, but no storefront page rendered a thread, so an editor
          who turned them on saw nothing happen. Keyed by page id and typed as
          cms_page: the API addresses comments by (resource_type, resource_id),
          and a blog_post id would attach the thread to the wrong object. */}
      {page.allow_comments && page.id ? (
        <BlogComments postId={page.id} resourceType="cms_page" />
      ) : null}
    </article>
  );
}

export function cmsMetadata(
  page: CmsPageContent,
  fallbackTitle: string,
  fallbackDescription?: string,
) {
  return {
    title: page.seo_title || page.title || fallbackTitle,
    description: page.seo_description || page.excerpt || fallbackDescription,
  };
}

export { notFound };
