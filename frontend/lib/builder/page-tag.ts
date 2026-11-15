/**
 * Cache tag helper for CMS pages.
 *
 * Separated from page.tsx because Next.js App Router validates page module
 * exports against an allow-list (default, metadata, generateMetadata…); any
 * other export trips Next's generated route types.
 */
export function pageTag(slug: string): string {
  return `cms-page:${slug}`;
}
