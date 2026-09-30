import type { Metadata } from "next";
import { fetchPublicDiscussionOptions } from "@/lib/public-options";

/** Blog metadata.
 *
 * ``robots`` is dynamic, not a constant: WordPress's ``blog_public`` ("Search
 * engine visibility") was seeded and editable but read by nothing, so an
 * operator who set the site to private still served indexable pages. The whole
 * blog subtree inherits whatever this returns, which is what makes the switch
 * mean what it says.
 */
export async function generateMetadata(): Promise<Metadata> {
  const { searchVisible } = await fetchPublicDiscussionOptions();
  return {
    title: "مجله و بلاگ",
    description: "مقالات راهنمای خرید، بررسی تخصصی کالاها و اخبار تکنولوژی.",
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
