/**
 * Runtime routing config (permalink structure, category/tag bases, locales).
 *
 * ONE loader for both callers the settings screen promises to affect:
 *  - the middleware resolves structured URLs from it,
 *  - components build links through it.
 * Both used to ignore the options entirely, so editing "permalink structure"
 * changed nothing the storefront did.
 *
 * Fetch policy: never throws, always falls back to DEFAULT_ROUTING — a dead
 * backend must not break link generation or the edge matcher. Server-side
 * callers hit the backend directly; the browser goes through the same-origin
 * /api/v1 rewrite.
 */

import {
  DEFAULT_ROUTING,
  type RoutingConfig,
} from "@/lib/permalinks";
import { apiInternalUrl } from "@/lib/api/server-base";

export type { RoutingConfig };
export { DEFAULT_ROUTING };

/** Client-side cache TTL; the middleware keeps its own short cache. */
const CLIENT_CACHE_TTL_MS = 60 * 1000;

let clientCache: { config: RoutingConfig; fetchedAt: number } | null = null;
let inflight: Promise<RoutingConfig> | null = null;

/** Load the routing config. Safe to call from server components and the
 *  browser; errors resolve to the defaults rather than rejecting. */
export async function getRoutingConfig(): Promise<RoutingConfig> {
  const base = typeof window === "undefined" ? apiInternalUrl() : "/api/v1";
  try {
    const res = await fetch(`${base}/settings/public/routing`, {
      cache: "no-store",
    } as RequestInit);
    if (!res.ok) return clientCache?.config ?? DEFAULT_ROUTING;
    const data = (await res.json()) as Partial<RoutingConfig>;
    const config: RoutingConfig = { ...DEFAULT_ROUTING, ...data };
    clientCache = { config, fetchedAt: Date.now() };
    return config;
  } catch {
    return clientCache?.config ?? DEFAULT_ROUTING;
  }
}

/** Browser-side variant with a small in-process cache; an already-warm
 *  config is served without a round trip. */
export async function getCachedRoutingConfig(): Promise<RoutingConfig> {
  if (clientCache && Date.now() - clientCache.fetchedAt < CLIENT_CACHE_TTL_MS) {
    return clientCache.config;
  }
  if (!inflight) {
    inflight = getRoutingConfig().finally(() => {
      inflight = null;
    });
  }
  return inflight;
}
