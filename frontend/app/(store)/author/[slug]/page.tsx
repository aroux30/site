import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { apiInternalUrl } from "@/lib/api/server-base";
import AuthorArchiveClient from "./author-archive-client";

/**
 * Metadata for the author archive — title/description from the operator's
 * titles-meta template (rendered by the backend), plus the self-canonical
 * the page lacked entirely (SEO audit F-03, live-verified: the sitemap
 * advertised this URL and it answered 200 with no canonical).
 *
 * `notFound()` must not run here (same trap the component documents): the
 * metadata function only reports; the component decides the 404.
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const canonical = `/author/${slug}`;
  try {
    const res = await fetch(
      `${apiInternalUrl()}/blog/authors/${encodeURIComponent(slug)}?page=1&page_size=1`,
      { next: { revalidate: 300 } },
    );
    if (res.ok) {
      const data = (await res.json()) as {
        author?: {
          name?: string;
          seo_title?: string | null;
          seo_description?: string | null;
        };
      };
      return {
        title:
          data.author?.seo_title ||
          (data.author?.name
            ? `نوشته‌های ${data.author.name}`
            : "آرشیو نویسنده"),
        description: data.author?.seo_description ?? undefined,
        alternates: { canonical },
      };
    }
  } catch {
    // Outage ≠ "author does not exist": return the safe title.
  }
  return { title: "آرشیو نویسنده", alternates: { canonical } };
}

/**
 * Author archive route — a SERVER component wrapping the client archive.
 *
 * Why the wrapper exists (soft-404 fix, 2026-10-09): the archive itself is
 * a client component, and a client component cannot set the HTTP status.
 * A missing author was handled with `router.replace("/blog")`, so the page
 * answered 200 for every guessed URL — a soft 404 that crawlers index and
 * Search Console reports as an error. A server-side existence check before
 * rendering lets `notFound()` run while headers are still open, which is
 * what makes the response a real 404.
 *
 * The check is one lightweight fetch of the same endpoint the client uses;
 * the client still fetches the full page data (author + posts + paging)
 * because the shape it needs is bigger than this probe. The extra request
 * is deliberate: it is the price of a correct status code, and it only
 * happens on this archive route.
 */
/**
 * Does the author exist? `true`/`false`/`null` (null = could not tell).
 *
 * `notFound()` is NOT called here, and must never be: it works by throwing
 * a special error, so a call inside a `try` is caught by that `try`'s own
 * `catch` — the first version of this wrapper did exactly that and the
 * route answered 200 for every guessed slug (caught in review with a live
 * probe). The decision is returned to the component, which calls
 * `notFound()` outside any try.
 */
async function authorExists(slug: string): Promise<boolean | null> {
  try {
    const res = await fetch(
      `${apiInternalUrl()}/blog/authors/${encodeURIComponent(slug)}?page=1&page_size=1`,
      { next: { revalidate: 300 } },
    );
    if (res.status === 404) return false;
    return true;
  } catch {
    // Network failure: we cannot tell. An outage must not read as
    // "author does not exist" — the client renders and surfaces its error.
    return null;
  }
}

export default async function AuthorArchiveRoute({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (!slug) notFound();

  const exists = await authorExists(slug);
  if (exists === false) notFound();

  return <AuthorArchiveClient />;
}
