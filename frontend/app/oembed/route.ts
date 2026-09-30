import { apiInternalUrl } from "@/lib/api/server-base";

/**
 * Public oEmbed discovery, proxied.
 *
 * The provider itself (`/api/v1/content/oembed/1.0/embed`) has been public
 * and correct, but a third-party site only finds an oEmbed provider by
 * following `<link rel="alternate" type="text/json+oembed">` on the page it
 * wants to embed. Nothing advertised it, so the capability was unreachable
 * from the outside — the definition of an endpoint without a consumer.
 *
 * Proxied rather than linked directly so the URL carries no API prefix, which
 * is an internal detail that changes on rename.
 */
export async function GET(request: Request): Promise<Response> {
  const incoming = new URL(request.url);
  const target = new URL(`${apiInternalUrl()}/content/oembed`);
  // WordPress's oEmbed discovery takes the embeddable resource as a query
  // parameter; everything else is passed through untouched.
  target.search = incoming.search;

  const upstream = await fetch(target, {
    headers: { accept: "application/json" },
    cache: "no-store",
  });
  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "public, max-age=300",
    },
  });
}
