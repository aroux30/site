import { apiInternalUrl } from "@/lib/api/server-base";

/** Proxies the backend RSS feed.
 *
 * The nine feed routes existed and answered correctly, but nothing in the
 * Next app requested them — so a reader following the advertised /blog/feed
 * URL got a 404 while the same document sat behind /api/v1/blog/feed/rss.
 * This makes the public path the real one. */
export async function GET(): Promise<Response> {
  try {
    const upstream = await fetch(`${apiInternalUrl()}/blog/feed/rss`, {
      next: { revalidate: 900 },
    });
    if (!upstream.ok) {
      return new Response("Feed unavailable", { status: 502 });
    }
    return new Response(await upstream.text(), {
      headers: {
        "Content-Type": "application/rss+xml; charset=utf-8",
        "Cache-Control": "public, max-age=900, s-maxage=900",
      },
    });
  } catch {
    return new Response("Feed unavailable", { status: 502 });
  }
}
