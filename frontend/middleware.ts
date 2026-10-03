import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify, decodeJwt } from "jose";
import { apiInternalUrl } from "@/lib/api/server-base";
import {
  DEFAULT_ROUTING,
  RESERVED_ROOTS,
  isDefaultStructure,
  matchPermalink,
  validateStructure,
  type RoutingConfig,
} from "@/lib/permalinks";

interface TokenPayload {
  sub?: string;
  roles?: string[];
  permissions?: string[];
  exp?: number;
  [key: string]: unknown;
}

// The admin/account gate below decides which UI shell a request may render.
// decodeJwt() alone would trust an attacker-forged cookie's payload (it
// base64-decodes without checking the signature), so when the signing secret
// is provisioned to this deployment the signature is verified first and a
// forged token is rejected outright. The backend re-authenticates every API
// call regardless, so this layer is defense-in-depth for pages — but it must
// not be trivially bypassable. The secret is the same JWT_SECRET_KEY the
// backend signs with; it lives only in server-side env, never in the client
// bundle, and is fetched lazily so builds do not require it.
const JWT_SECRET = process.env.JWT_SECRET_KEY || process.env.NEXTAUTH_SECRET || "";

async function readVerifiedPayload(token: string): Promise<TokenPayload | null> {
  if (JWT_SECRET) {
    try {
      const { payload } = await jwtVerify(
        token,
        new TextEncoder().encode(JWT_SECRET),
        { algorithms: ["HS256"] },
      );
      return payload as TokenPayload;
    } catch {
      // Signature/expiry verification failed — the token is not authentic.
      return null;
    }
  }
  // No secret provisioned (development without shared config): degrade to
  // decode-only so local flows keep working. Production must set the
  // secret; docs/deployment covers provisioning it.
  try {
    return decodeJwt(token) as TokenPayload;
  } catch {
    return null;
  }
}

// Edge Rate Limiter (Token Bucket / Sliding Window for Layer 7 flood defense)
const ipRequestHistory = new Map<string, number[]>();
const RATE_LIMIT_WINDOW_MS = 60 * 1000; // 1 minute
const MAX_REQUESTS_PER_WINDOW = 120; // 120 req/min per IP

function isEdgeRateLimited(ip: string): boolean {
  const now = Date.now();
  const timestamps = ipRequestHistory.get(ip) || [];
  const validTimestamps = timestamps.filter((t) => now - t < RATE_LIMIT_WINDOW_MS);

  if (validTimestamps.length >= MAX_REQUESTS_PER_WINDOW) {
    return true;
  }

  validTimestamps.push(now);
  ipRequestHistory.set(ip, validTimestamps);

  // Housekeeping: prevent memory growth
  if (ipRequestHistory.size > 5000) {
    ipRequestHistory.clear();
  }
  return false;
}

// ── Admin-managed SEO redirects (backend: /api/v1/seo/redirects) ────────────
// Rules are fetched once and cached in-process (see TTL below); matching mirrors
// the backend's redirect_service.match_redirect (exact beats wildcard, longest
// wildcard prefix wins). Fail-open: any fetch error just skips redirects.

interface RedirectRule {
  from_path: string;
  to_path: string;
  status_code: number;
}

let redirectCache: { rules: RedirectRule[]; fetchedAt: number } | null = null;
// Kept short: a rule an admin just created should take effect quickly, and the
// admin UI promises near-immediate application. The backend feed is cheap and
// its own cache is invalidated on write, so a small TTL costs one fetch per
// minute per edge instance at most.
const REDIRECT_CACHE_TTL_MS = 60 * 1000;

async function matchRedirectRule(pathname: string): Promise<RedirectRule | null> {
  try {
    if (!redirectCache || Date.now() - redirectCache.fetchedAt > REDIRECT_CACHE_TTL_MS) {
      // Same resolver the server components use, so edge and SSR can never
      // disagree about where the backend lives (they did before: three env
      // var names, two with a /api/v1 suffix and two without).
      const base = apiInternalUrl();
      if (!base) return null;
      // No Next data-cache here: the in-process cache above is the single
      // TTL authority, otherwise two different 300s layers disagree with the
      // admin UI's "within a minute" promise.
      const res = await fetch(`${base}/seo/redirects`, { cache: "no-store" } as RequestInit);
      if (!res.ok) return null;
      redirectCache = { rules: (await res.json()) as RedirectRule[], fetchedAt: Date.now() };
    }
  } catch {
    return null;
  }
  const norm = pathname.toLowerCase().replace(/\/+$/, "") || "/";
  let best: RedirectRule | null = null;
  for (const rule of redirectCache.rules) {
    if (rule.from_path.endsWith("/*")) {
      const prefix = rule.from_path.slice(0, -2);
      if (norm === prefix || norm.startsWith(prefix + "/")) {
        if (!best || prefix.length > best.from_path.length) best = rule;
      }
    } else if (norm === rule.from_path) {
      return rule;
    }
  }
  return best;
}

// ── Admin-configured permalink structure (backend: /settings/public/routing) ─
// URL resolution mirrors lib/permalinks.ts so the storefront builds and
// resolves links the same way. Cached briefly in-process; any failure falls
// back to the canonical file-tree routing, which is always valid.

let routingCache: { config: RoutingConfig; fetchedAt: number } | null = null;
const ROUTING_CACHE_TTL_MS = 60 * 1000;

async function getRoutingOptions(): Promise<RoutingConfig> {
  try {
    if (!routingCache || Date.now() - routingCache.fetchedAt > ROUTING_CACHE_TTL_MS) {
      const base = apiInternalUrl();
      if (!base) return DEFAULT_ROUTING;
      const res = await fetch(`${base}/settings/public/routing`, {
        cache: "no-store",
      } as RequestInit);
      if (!res.ok) return routingCache?.config ?? DEFAULT_ROUTING;
      routingCache = {
        config: { ...DEFAULT_ROUTING, ...((await res.json()) as Partial<RoutingConfig>) },
        fetchedAt: Date.now(),
      };
    }
  } catch {
    return routingCache?.config ?? DEFAULT_ROUTING;
  }
  return routingCache.config;
}

/**
 * Rewrite a structured post URL (e.g. ``/2026/09/my-post/``) onto the
 * canonical ``/blog/<slug>`` route — but only when the structure genuinely
 * matches AND the first segment is not a real storefront route. A structure
 * like ``/%category%/%postname%/`` must never swallow ``/account/orders``.
 */
async function resolveStructuredPost(
  pathname: string,
  routing: RoutingConfig,
): Promise<string | null> {
  // `request.nextUrl.pathname` is percent-encoded: a Persian category_base
  // ("موضوع") arrives as "%D9%85%D9%88%D8%B6%D9%88%D8%B9" and would never
  // string-match the configured base. Decoding each incoming segment makes
  // the comparison encoding-independent (the *outgoing* rewrite is re-encoded
  // by URL/NextResponse). A malformed %-sequence falls back to the raw
  // segment rather than throwing.
  const decode = (seg: string): string => {
    try {
      return decodeURIComponent(seg);
    } catch {
      return seg;
    }
  };
  const segments = pathname.split("/").filter(Boolean).map(decode);
  const first = segments[0] ?? "";

  // Custom taxonomy bases: /<cat-base>/<slug> and /<tag-base>/<slug> land on
  // the physical /blog/category|tag/<slug> archive routes. The default bases
  // need no rewrite — the file tree already serves those paths.
  const catBase = (routing.category_base || "category").toLowerCase();
  const tagBase = (routing.tag_base || "tag").toLowerCase();
  if (segments.length === 2 && !RESERVED_ROOTS.has(first.toLowerCase())) {
    const slug = segments[1] ?? "";
    if (catBase !== "category" && first.toLowerCase() === catBase) {
      return `/blog/category/${encodeURIComponent(slug)}`;
    }
    if (tagBase !== "tag" && first.toLowerCase() === tagBase) {
      return `/blog/tag/${encodeURIComponent(slug)}`;
    }
  }

  if (isDefaultStructure(routing.permalink_structure)) return null;
  if (validateStructure(routing.permalink_structure).length > 0) return null;
  if (RESERVED_ROOTS.has(first.toLowerCase())) return null;

  // The structure itself carries literal (possibly Persian) segments, so it
  // must be matched in decoded space too.
  const matched = matchPermalink(`/${segments.join("/")}`, routing.permalink_structure);
  if (!matched) return null;
  if (matched.postname) {
    // Slug-shaped structures: rewrite straight to the canonical route; a
    // nonexistent slug 404s there, which is the correct answer anyway.
    return `/blog/${encodeURIComponent(matched.postname)}`;
  }
  if (matched.post_id) {
    // Numeric structures carry no slug; resolve the identity server-side and
    // fail open (no rewrite) when it cannot be resolved.
    try {
      const base = apiInternalUrl();
      if (!base) return null;
      const res = await fetch(`${base}/blog/posts/by-id/${matched.post_id}/slug`, {
        cache: "no-store",
      } as RequestInit);
      if (!res.ok) return null;
      const data = (await res.json()) as { slug?: string };
      return data.slug ? `/blog/${data.slug}` : null;
    } catch {
      return null;
    }
  }
  return null;
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 0.5 Admin-managed redirects (only for page GETs, never for API/admin/assets)
  if (
    request.method === "GET" &&
    !pathname.startsWith("/api") &&
    !pathname.startsWith("/admin") &&
    !pathname.startsWith("/_next")
  ) {
    const rule = await matchRedirectRule(pathname);
    if (rule) {
      // Fire-and-forget hit beacon so the admin's visit counters are real.
      // Goes through this origin's own /api/v1 rewrite (the same path the
      // browser uses), NOT the internal container hostname — that name only
      // resolves inside Docker and silently failed in local dev. Bounded
      // wait so a slow beacon never delays the redirect itself.
      const beacon = fetch(new URL("/api/v1/seo/redirects/hit", request.url), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ from_paths: [rule.from_path] }),
      }).catch(() => undefined);
      await Promise.race([beacon, new Promise((r) => setTimeout(r, 300))]);
      return NextResponse.redirect(new URL(rule.to_path, request.url), rule.status_code);
    }

    // 0.6 Admin permalink structure: rewrite structured post URLs onto the
    // canonical /blog/<slug> route. Runs only for storefront page GETs (same
    // gate as redirects, minus admin/account which are physical routes).
    if (!pathname.startsWith("/account")) {
      const routing = await getRoutingOptions();
      const target = await resolveStructuredPost(pathname, routing);
      if (target && target !== pathname) {
        return NextResponse.rewrite(new URL(target, request.url));
      }
    }
  }

  // 0. Edge Rate Limiter
  const forwarded = request.headers.get("x-forwarded-for");
  const clientIp =
    (forwarded ? forwarded.split(",")[0]?.trim() : null) ||
    request.headers.get("x-real-ip") ||
    "127.0.0.1";

  // ponytail: development skips this shared page/API quota; production retains it.
  if (process.env.NODE_ENV !== "development" && isEdgeRateLimited(clientIp)) {
    return new NextResponse(
      JSON.stringify({
        error: "rate_limit_exceeded",
        message: "تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً کمی صبر کرده و مجدداً تلاش نمایید.",
      }),
      {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": "60",
        },
      }
    );
  }

  // 1. CSRF Origin Verification on state-modifying requests
  if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method)) {
    const origin = request.headers.get("origin");
    // Real requests carry a Host header; fall back to the request URL's host
    // so the check is also unit-testable (constructed Requests cannot set
    // Host — it is a forbidden fetch header).
    const host = request.headers.get("host") || request.nextUrl.host;
    if (origin && host) {
      try {
        const originHost = new URL(origin).host;
        const isLocal = host.includes("localhost") || host.includes("127.0.0.1");
        if (originHost !== host && !isLocal) {
          return new NextResponse(
            JSON.stringify({ error: "csrf_rejected", message: "Cross-site request rejected" }),
            { status: 403, headers: { "Content-Type": "application/json" } }
          );
        }
      } catch {
        // Ignored if origin URL parsing fails
      }
    }
  }

  const isAdminRoute = pathname.startsWith("/admin");
  const isAccountRoute = pathname.startsWith("/account");

  if (!isAdminRoute && !isAccountRoute) {
    return NextResponse.next();
  }

  // An email-confirmation link is the one case where /account must render for
  // someone who is not logged in. The endpoint it calls is unauthenticated by
  // design — the token, single-use, short-lived and stored hashed, is the
  // credential — so gating the page behind a session would make the flow
  // unreachable for exactly the users it serves best: someone whose session
  // expired, or who is confirming on a different device. The redirect below
  // also drops the query string, so a login round-trip would lose the token and
  // the user would land back here with nothing to redeem.
  //
  // The privacy-request confirmation link has the same shape: the subject may
  // be confirming from a phone that is not signed in, and the token is the
  // credential.
  const isEmailConfirmation = request.nextUrl.searchParams.has("email_token");
  const isPrivacyConfirmation = request.nextUrl.searchParams.has("privacy_confirm_token");
  if (isAccountRoute && (isEmailConfirmation || isPrivacyConfirmation)) {
    return NextResponse.next();
  }

  const token = request.cookies.get("access_token")?.value;
  const refreshToken = request.cookies.get("refresh_token")?.value;

  // 1. Missing Token: redirect to login — unless a refresh token exists, in
  // which case the client's silent refresh flow (lib/api/client.ts) will
  // mint a fresh access token on the first 401 and the user never sees the
  // login page just because the short-lived access cookie expired.
  if (!token) {
    if (refreshToken) {
      return NextResponse.next();
    }
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // 2. Inspect JWT payload — verify the HS256 signature whenever the secret
  // is provisioned (readVerifiedPayload returns null on verification failure);
  // fall back to decode-only only when no secret exists. A forged cookie must
  // never reach the RBAC check below, and the backend stays authoritative:
  // every privileged API call is re-authenticated server-side regardless of
  // what this edge gate decided.
  try {
    const payload = await readVerifiedPayload(token);
    if (payload === null) {
      // Verification failed → treat exactly like a malformed token: redirect
      // to login, unless a refresh token exists (silent-refresh escape hatch).
      if (refreshToken) {
        return NextResponse.next();
      }
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      const response = NextResponse.redirect(loginUrl);
      response.cookies.delete("access_token");
      return response;
    }

    // Check expiration — same refresh-token escape hatch as above.
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      if (refreshToken) {
        return NextResponse.next();
      }
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      // Clear expired cookie
      const response = NextResponse.redirect(loginUrl);
      response.cookies.delete("access_token");
      return response;
    }

    // 3. Admin Route RBAC Authorization Check
    if (isAdminRoute) {
      const userRoles = Array.isArray(payload.roles) ? payload.roles : [];
      const userPerms = Array.isArray(payload.permissions) ? payload.permissions : [];

      const isSuperAdmin = Boolean(
        payload.is_superuser ||
        userRoles.includes("super_admin") ||
        userPerms.includes("*")
      );
      // WordPress-parity staff roles (editor/author/contributor) reach the
      // admin shell; every privileged API call is still re-authorized
      // server-side per permission, so a customer role never gets data.
      const STAFF_ROLES = ["admin", "editor", "author", "contributor"];
      const isAdmin = Boolean(
        payload.is_superuser ||
        userRoles.some((role) => STAFF_ROLES.includes(role)) ||
        isSuperAdmin
      );

      if (!isSuperAdmin && !isAdmin) {
        // Logged-in customer attempting to access admin panel -> redirect to home or account
        return NextResponse.redirect(new URL("/", request.url));
      }
    }
  } catch {
    // Malformed token -> redirect to login, unless a refresh token exists
    // (same silent-refresh escape hatch as above).
    if (refreshToken) {
      return NextResponse.next();
    }
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    const response = NextResponse.redirect(loginUrl);
    response.cookies.delete("access_token");
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Storefront paths must also run middleware so admin-managed SEO
    // redirects (fetched from /api/v1/seo/redirects) actually fire — the
    // previous matcher only covered admin/account/api, so redirect rules
    // never applied to the pages they were written for.
    "/((?!_next|favicon.ico|icon|robots.txt|sitemap.xml|api/v1).*)",
  ],
};
