/**
 * Video sitemap (Rank Math Pro parity).
 *
 * Served by a route handler because Next's metadata sitemap API cannot emit
 * the `video:` namespace. Source data comes from the shared public payload
 * (`GET /content/sitemap-entries` → `videos` key); the backend already skips
 * posts without a thumbnail (an entry without one is invalid for Google).
 *
 * Google requires a `video:content_loc` or `video:player_loc`; this store
 * hosts video as an embedded/attached asset rather than a streamable file, so
 * `video:player_loc` points at the post page itself — the documented fallback
 * when the video lives inside a page a crawler can render.
 */

import { apiInternalUrl } from "@/lib/api/server-base";
import { escapeXml, xmlResponse } from "@/lib/sitemap-xml";
import { siteOrigin } from "@/lib/site-url";

interface VideoRow {
  loc: string;
  title: string;
  description: string;
  thumbnail_url: string;
  published_at?: string | null;
}

async function fetchVideos(): Promise<VideoRow[]> {
  try {
    const res = await fetch(`${apiInternalUrl()}/content/sitemap-entries`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) {
      console.error(`video-sitemap: sitemap-entries returned ${res.status}`);
      return [];
    }
    const data = (await res.json()) as { videos?: VideoRow[] };
    return Array.isArray(data.videos) ? data.videos : [];
  } catch (error) {
    console.error("video-sitemap: fetch failed; serving empty file", error);
    return [];
  }
}

/** Stored media path → absolute URL (relative URLs are ignored by crawlers). */
function absoluteMedia(baseUrl: string, src: string): string {
  if (/^https?:\/\//i.test(src)) return src;
  return `${baseUrl}${src.startsWith("/") ? src : `/${src}`}`;
}

export async function GET(): Promise<Response> {
  // Same resolver as the news sitemap and JSON-LD (see site-url.ts): a
  // deployment that sets only SITE_URL must not get localhost URLs here.
  const baseUrl = siteOrigin();
  const rows = await fetchVideos();

  const entries = rows
    .filter((row) => row.loc && row.title && row.description && row.thumbnail_url)
    .map((row) => {
      const pageUrl = `${baseUrl}${row.loc}`;
      return [
        "  <url>",
        `    <loc>${escapeXml(pageUrl)}</loc>`,
        "    <video:video>",
        `      <video:thumbnail_loc>${escapeXml(absoluteMedia(baseUrl, row.thumbnail_url))}</video:thumbnail_loc>`,
        `      <video:title>${escapeXml(row.title)}</video:title>`,
        `      <video:description>${escapeXml(row.description)}</video:description>`,
        `      <video:player_loc>${escapeXml(pageUrl)}</video:player_loc>`,
        "    </video:video>",
        "  </url>",
      ].join("\n");
    })
    .join("\n");

  const body = [
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
    '        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">',
    entries,
    "</urlset>",
  ]
    .filter(Boolean)
    .join("\n");

  return xmlResponse(body);
}
