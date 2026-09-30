import { apiInternalUrl } from "@/lib/api/server-base";

/** Public RSS for one tag, proxied off the API prefix. */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ slug: string }> },
): Promise<Response> {
  const { slug } = await params;
  return proxy(await fetch(`${apiInternalUrl()}/blog/feed/rss/tag/${encodeURIComponent(slug)}`));
}

async function proxy(upstream: Response): Promise<Response> {
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: {
      "content-type": "application/rss+xml; charset=utf-8",
      "cache-control": "public, max-age=300",
    },
  });
}
