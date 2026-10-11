// Service Worker — فروشگاه آنلاین PWA
// Cache versioning: bump these when deploying new assets
const CACHE_STATIC = "v1-static";
const CACHE_API = "v1-api";
const CACHE_PAGES = "v1-pages";
const ALL_CACHES = [CACHE_STATIC, CACHE_API, CACHE_PAGES];

// Assets to pre-cache on install
const PRECACHE_URLS = ["/", "/offline.html"];

// ─── Install ─────────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_STATIC)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// ─── Activate ────────────────────────────────────────────
// Clean up old caches that don't match current version
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => !ALL_CACHES.includes(key))
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

// ─── Fetch strategies ────────────────────────────────────

/**
 * Determine which strategy to use based on the request.
 *
 * - Static assets (CSS, JS, fonts, images): cache-first
 * - API calls (/api/): network-first with cache fallback
 * - Pages (navigations): stale-while-revalidate
 */
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin requests and GET
  if (url.origin !== self.location.origin || request.method !== "GET") return;

  // Skip Next.js HMR / dev requests
  if (url.pathname.startsWith("/_next/webpack-hmr")) return;

  // API calls — network-first
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request, CACHE_API));
    return;
  }

  // Static assets — cache-first
  if (isStaticAsset(url.pathname)) {
    event.respondWith(cacheFirst(request, CACHE_STATIC));
    return;
  }

  // Pages (navigation requests) — stale-while-revalidate
  if (request.mode === "navigate" || request.headers.get("accept")?.includes("text/html")) {
    event.respondWith(staleWhileRevalidate(request, CACHE_PAGES));
    return;
  }

  // Everything else — network with cache fallback
  event.respondWith(networkFirst(request, CACHE_STATIC));
});

// ─── Strategy implementations ────────────────────────────

/**
 * Cache-first: serve from cache, fall back to network.
 * Best for versioned static assets that rarely change.
 */
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response("", { status: 503 });
  }
}

/**
 * Network-first: try network, fall back to cache.
 * Best for API data that needs to be fresh.
 */
async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || new Response(JSON.stringify({ error: "آفلاین" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

/**
 * Stale-while-revalidate: serve cache immediately, update in background.
 * Best for product/category pages.
 */
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const fetchPromise = fetch(request)
    .then((response) => {
      if (response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  // If we have a cached version, return it immediately and revalidate
  if (cached) {
    fetchPromise; // fire-and-forget revalidation
    return cached;
  }

  // No cache — wait for network, fall back to offline page
  const response = await fetchPromise;
  if (response) return response;

  return caches.match("/offline.html") || new Response("آفلاین", { status: 503 });
}

// ─── Helpers ─────────────────────────────────────────────

/** Check if a pathname points to a static asset. */
function isStaticAsset(pathname) {
  return /\.(?:js|css|woff2?|ttf|otf|eot|ico|svg|png|jpe?g|webp|avif|gif)$/.test(pathname)
    || pathname.startsWith("/_next/static/");
}
