import { apiInternalUrl } from "@/lib/api/server-base";

/** Proxies the site-wide comments feed. */
export async function GET(): Promise<Response> {
  try {
    const upstream = await fetch(`${apiInternalUrl()}/blog/feed/comments/rss`, {
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
