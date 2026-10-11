import type { Metadata } from "next";
import { fetchPublicDiscussionOptions } from "@/lib/public-options";
import { siteOrigin } from "@/lib/site-url";
import { openGraphBase } from "@/lib/seo-meta";

/** Blog metadata.
 *
 * ``robots`` is dynamic, not a constant: WordPress's ``blog_public`` ("Search
 * engine visibility") was seeded and editable but read by nothing, so an
 * operator who set the site to private still served indexable pages. The whole
 * blog subtree inherits whatever this returns, which is what makes the switch
 * mean what it says.
 *
 * A canonical is declared here for the LIST page only. The blog index is a
 * client component (filters/paging are interactive), so it cannot export
 * `generateMetadata` itself — and without a canonical the indexable listing
 * page had none at all (Lighthouse flagged the gap). Children override this
 * with their own canonical: an article's `generateMetadata` and the archive
 * pages' both set one, so the inherited value only ever reaches `/blog`
 * itself and its query-string variants (`?page=2`), which canonical to the
 * clean path — the documented treatment for paginated listings.
 */
export async function generateMetadata(): Promise<Metadata> {
  const { searchVisible } = await fetchPublicDiscussionOptions();
  // Single source for the site origin: NEXT_PUBLIC_SITE_URL (siteOrigin()).
  // The DB value (routing.site_url) is used by backend-built URLs (feeds,
  // IndexNow); reading it here too meant two sources could disagree and the
  // blog would canonical to a different domain than the rest of the site
  // (SEO audit F-15, 2026-10-10).
  const base = siteOrigin();
  const canonical = `${base.replace(/\/$/, "")}/blog`;
  return {
    title: "مجله و بلاگ",
    description: "مقالات راهنمای خرید، بررسی تخصصی کالاها و اخبار تکنولوژی.",
    alternates: { canonical },
    openGraph: openGraphBase({ url: canonical }),
    ...(searchVisible ? {} : { robots: { index: false, follow: true } }),
  };
}

export default function BlogLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
