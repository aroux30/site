import Link from "next/link";

/**
 * Server-rendered links for client-rendered list pages.
 *
 * The /blog and /products list pages are client components; their raw HTML
 * contains zero links to the content they list (live-verified 2026-10-10),
 * so a crawler that does not run JavaScript has no path to discover any
 * article or product. This block sits at the bottom of those two pages and
 * puts real <a> tags into the initial HTML.
 *
 * Deliberately no <h2>: the heading structure of the pages must not change
 * (SEO audit F-17). A <nav> with aria-label is enough for accessibility.
 */
export function CrawlableLinks({
  title,
  links,
}: {
  title: string;
  links: { href: string; label: string }[];
}) {
  if (links.length === 0) return null;
  return (
    <nav aria-label={title} className="container mx-auto max-w-5xl px-4 pb-10">
      <div className="mb-3 text-sm font-bold text-muted-foreground">{title}</div>
      <ul className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
        {links.map((l) => (
          <li key={l.href}>
            <Link
              href={l.href}
              className="text-primary underline-offset-4 hover:underline"
            >
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
