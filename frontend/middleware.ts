import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { decodeJwt } from "jose";

interface TokenPayload {
  sub?: string;
  roles?: string[];
  permissions?: string[];
  exp?: number;
  [key: string]: unknown;
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

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 0. Edge Rate Limiter
  const forwarded = request.headers.get("x-forwarded-for");
  const clientIp =
    (forwarded ? forwarded.split(",")[0]?.trim() : null) ||
    request.headers.get("x-real-ip") ||
    "127.0.0.1";

  if (isEdgeRateLimited(clientIp)) {
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
    const host = request.headers.get("host");
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

  const token = request.cookies.get("access_token")?.value;

  // 1. Missing Token: Immediate redirect to login
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // 2. Inspect JWT payload
  try {
    const payload = decodeJwt(token) as TokenPayload;

    // Check expiration
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
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
      const isAdmin = Boolean(
        payload.is_superuser ||
        userRoles.includes("admin") ||
        isSuperAdmin
      );

      if (!isSuperAdmin && !isAdmin) {
        // Logged-in customer attempting to access admin panel -> redirect to home or account
        return NextResponse.redirect(new URL("/", request.url));
      }
    }
  } catch {
    // Malformed token -> redirect to login
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
    "/admin/:path*",
    "/account/:path*",
  ],
};
