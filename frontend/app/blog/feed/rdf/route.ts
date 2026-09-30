import { apiInternalUrl } from "@/lib/api/server-base";

/** Proxies the backend RDF feed.
 *
 * The autodiscovery link pointed straight at /api/v1 for this one format.
 * That works only because next.config.mjs proxies the prefix — an
 * implementation detail that breaks the moment the service is renamed, and a
 * feed URL that 404s then breaks every existing reader. */
export async function GET(): Promise<Response> {
  try {
    const upstream = await fetch(`${apiInternalUrl()}/blog/feed/rdf`, {
      next: { revalidate: 900 },
    });
    if (!upstream.ok) {
      return new Response("Feed unavailable", { status: 502 });
    }
    return new Response(await upstream.text(), {
      headers: {
        "Content-Type": "application/rdf+xml; charset=utf-8",
        "Cache-Control": "public, max-age=900, s-maxage=900",
      },
    });
  } catch {
    return new Response("Feed unavailable", { status: 502 });
  }
}
