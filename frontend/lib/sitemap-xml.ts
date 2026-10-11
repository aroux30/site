/**
 * Minimal XML builders for the special sitemaps (news, video).
 *
 * Next.js's `MetadataRoute.Sitemap` cannot express the news/video XML
 * namespaces (`news:news`, `video:video`), so those two sitemaps are served
 * by route handlers that build the XML themselves. Everything here exists so
 * both handlers escape and serialize identically — a hand-built XML that
 * forgets to escape an `&` in a title is a parse error a crawler reports as
 * "sitemap could not be read", which silently drops every URL in the file.
 */

/** Escape text for use inside an XML text node or attribute value. */
export function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** A response with the sitemap content type crawlers expect. */
export function xmlResponse(body: string): Response {
  return new Response(`<?xml version="1.0" encoding="UTF-8"?>\n${body}\n`, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      // Sitemaps are read by crawlers, not people; a short cache keeps a
      // publish from waiting on a stale copy while sparing the DB per hit.
      "Cache-Control": "public, max-age=0, s-maxage=300, must-revalidate",
    },
  });
}

/** ISO date (with timezone) as Google's news sitemap requires it. */
export function newsDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString();
}
