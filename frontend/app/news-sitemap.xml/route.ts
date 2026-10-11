/**
 * Google News sitemap (Rank Math Pro parity).
 *
 * Next.js's metadata sitemap API cannot emit the `news:` namespace, so this
 * is a route handler. The source data comes from the same public payload the
 * main sitemap uses (`GET /content/sitemap-entries` → `news` key), which
 * already applies Google's hard rules server-side: published within 48 hours,
 * publication name and language present, capped at 1,000 URLs.
 *
 * The file is always served, even when empty: Google reads a 404 as "no news
 * sitemap declared" and a 200 with an empty <urlset> as "nothing recent",
 * and only the second is true when the site simply has no new posts.
 */

import { apiInternalUrl } from "@/lib/api/server-base";
import { escapeXml, newsDate, xmlResponse } from "@/lib/sitemap-xml";
import { siteOrigin } from "@/lib/site-url";

interface NewsRow {
  loc: string;
  title: string;
  published_at: string;
  publication_name: string;
  language: string;
}

async function fetchNews(): Promise<NewsRow[]> {
  try {
    const res = await fetch(`${apiInternalUrl()}/content/sitemap-entries`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) {
      console.error(`news-sitemap: sitemap-entries returned ${res.status}`);
      return [];
    }
    const data = (await res.json()) as { news?: NewsRow[] };
    return Array.isArray(data.news) ? data.news : [];
  } catch (error) {
    console.error("news-sitemap: fetch failed; serving empty file", error);
    return [];
  }
}

export async function GET(): Promise<Response> {
  // siteOrigin() reads NEXT_PUBLIC_SITE_URL → SITE_URL → localhost, the same
  // resolver JSON-LD and the rest of the storefront use. Reading only
  // NEXT_PUBLIC_SITE_URL here would ship localhost URLs whenever a deployment
  // configures just SITE_URL — the exact mismatch this helper exists to stop.
  const baseUrl = siteOrigin();
  const rows = await fetchNews();

  const entries = rows
    .filter((row) => row.loc && row.title && row.published_at)
    .map((row) => {
      const date = newsDate(row.published_at);
      if (!date) return "";
      return [
        "  <url>",
        `    <loc>${escapeXml(`${baseUrl}${row.loc}`)}</loc>`,
        "    <news:news>",
        "      <news:publication>",
        `        <news:name>${escapeXml(row.publication_name)}</news:name>`,
        `        <news:language>${escapeXml(row.language || "fa")}</news:language>`,
        "      </news:publication>",
        `      <news:publication_date>${escapeXml(date)}</news:publication_date>`,
        `      <news:title>${escapeXml(row.title)}</news:title>`,
        "    </news:news>",
        "  </url>",
      ].join("\n");
    })
    .filter(Boolean)
    .join("\n");

  // xmlResponse adds the XML declaration; do not repeat it here.
  const body = [
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
    '        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">',
    entries,
    "</urlset>",
  ]
    .filter(Boolean)
    .join("\n");

  return xmlResponse(body);
}
