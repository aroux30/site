import { fetchBlogPosts } from "@/lib/api/blog";
import { getRoutingConfig } from "@/lib/routing";
import { postHref } from "@/lib/permalinks";
import { CrawlableLinks } from "@/components/shared/crawlable-links";
import BlogListClient from "./blog-list-client";

/**
 * Thin server shell: the client list body + a server-rendered link block.
 *
 * The list itself is a client component; its raw HTML had zero links to any
 * post (live-verified 2026-10-10), so a JS-less crawler could not discover
 * a single article. The block below puts the first page of posts into the
 * initial HTML. Metadata stays in `blog/layout.tsx` (canonical /blog);
 * this file exports none.
 */
export default async function BlogPage() {
  let links: { href: string; label: string }[] = [];
  try {
    const routing = await getRoutingConfig();
    const res = await fetchBlogPosts({ page: 1, page_size: 50 });
    links = res.items.map((p) => ({
      href: postHref(routing.permalink_structure, {
        slug: p.slug,
        id: p.id,
        published_at: p.published_at,
        category_slug: p.category?.slug ?? null,
        author_slug: p.author_slug ?? null,
      }),
      label: p.title,
    }));
  } catch {
    // An API outage must not take the page down; the block renders empty
    // and the client body surfaces the error state as before.
    links = [];
  }
  return (
    <>
      <BlogListClient />
      <CrawlableLinks title="نوشته‌های وبلاگ" links={links} />
    </>
  );
}
