/**
 * Which hosts `next/image` is allowed to optimise.
 *
 * One source of truth, read by two places that must agree:
 *
 * 1. `next.config.ts` builds `images.remotePatterns` from it.
 * 2. `RemoteImage` checks a URL against it *before* handing it to
 *    `next/image`, which otherwise **throws** on a host that is not configured
 *    — and a throw during render takes down the whole route, not just the
 *    image.
 *
 * That throw is not hypothetical: a blog comment whose author has a Gravatar
 * address (`https://www.gravatar.com/avatar/<hash>`) made every article page
 * render Next's error boundary. `next.config.ts` deliberately keeps this list
 * narrow, so Gravatar is *not* in it — and widening the list to "make the error
 * go away" would hand an unvetted host to the optimiser, which is the surface
 * the narrow list exists to avoid. The right fix is to degrade that one image
 * to the neutral placeholder, not to trust the host.
 *
 * Same-origin paths (`/uploads/media/<uuid>.png`) are always allowed: they are
 * served through the same-origin rewrite in next.config.ts.
 */

/** Hosts always permitted, matched as a single leading `*.` wildcard label. */
export const ALWAYS_ALLOWED_IMAGE_HOSTS: readonly string[] = ["*.arouxpingg.com"];

/** Extra hosts the operator opts into, as a comma-separated list of hostnames. */
export function optInImageHosts(): string[] {
  return (process.env.NEXT_PUBLIC_IMAGE_HOSTS || "")
    .split(",")
    .map((h) => h.trim())
    .filter(Boolean);
}

/** Every host the optimiser is configured for. */
export function allowedImageHosts(): string[] {
  return [...ALWAYS_ALLOWED_IMAGE_HOSTS, ...optInImageHosts()];
}

/**
 * Whether `next/image` may be pointed at this URL.
 *
 * A relative path is allowed: same-origin media. An absolute URL is allowed
 * only on https and only for a configured host. Everything else must degrade
 * to a placeholder instead of reaching `next/image`.
 *
 * `*.example.com` matches `a.example.com` and `example.com`, matching how
 * Next interprets a leading-wildcard remote pattern.
 */
export function isAllowedImageUrl(url: string): boolean {
  const trimmed = url.trim();
  if (!trimmed) return false;
  // Relative, site-absolute paths: served by the same-origin rewrite.
  if (trimmed.startsWith("/")) return !trimmed.startsWith("//");

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return false;
  }
  // http and protocol-relative URLs are refused outright: the optimizer fetches
  // them, and an unencrypted or attacker-chosen origin has no business here.
  if (parsed.protocol !== "https:") return false;

  return allowedImageHosts().some((pattern) => matchesHost(pattern, parsed.hostname));
}

function matchesHost(pattern: string, hostname: string): boolean {
  const p = pattern.toLowerCase();
  const h = hostname.toLowerCase();
  if (p.startsWith("*.")) {
    const suffix = p.slice(1); // ".example.com"
    return h.endsWith(suffix) || h === p.slice(2);
  }
  return h === p;
}
