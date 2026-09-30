import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.resolve(process.cwd()),
  // Role A builds/serve prod into an isolated dist dir (NEXT_DIST_DIR=.next-prod)
  // so a production build never corrupts the dev server's ".next" (Rule 2 of
  // COORDINATION.md — dev on :3000 must stay usable at all times).
  distDir: process.env.NEXT_DIST_DIR || ".next",

  images: {
    // Only same-origin media is rendered by next/image: product/media URLs are
    // server-generated relative paths ("/uploads/media/<uuid>.<ext>") served
    // through the same-origin rewrite below, so a wildcard remote host would
    // add SSRF/abuse surface for no functional gain. Additional CDN hosts must
    // be opted in explicitly via NEXT_PUBLIC_IMAGE_HOSTS (comma-separated
    // https hostnames) — never by widening to "**".
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.arouxpingg.com",
      },
      ...(process.env.NEXT_PUBLIC_IMAGE_HOSTS || "")
        .split(",")
        .map((h) => h.trim())
        .filter(Boolean)
        .map((hostname) => ({ protocol: "https" as const, hostname })),
    ],
    formats: ["image/avif", "image/webp"],
  },

  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "recharts",
      "framer-motion",
      "date-fns",
      "date-fns-jalali",
    ],
  },

  async rewrites() {
    const backend = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000";
    return [
      { source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` },
      // The readiness/liveness probes live at the API root, outside /api/v1.
      // Without these the admin reports page fetched /api/health/ready from
      // Next.js itself and got a 404, then fell back to fabricated service
      // health. Proxying them makes the real dependency state visible.
      {
        source: "/api/health/:path*",
        destination: `${backend}/api/health/:path*`,
      },
      { source: "/media/:path*", destination: `${backend}/media/:path*` },
      // Media assets store a relative file_url of "/uploads/media/<name>" and
      // the picker, editor previews and product images all render that path
      // directly. Nothing served it, so every asset chosen from the library
      // 404'd — the images.remotePatterns comment above already assumed this
      // rewrite existed.
      { source: "/uploads/:path*", destination: `${backend}/uploads/:path*` },
    ];
  },

  async redirects() {
    return [
      {
        source: "/admin",
        destination: "/admin/dashboard",
        permanent: false,
      },
    ];
  },

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
      // Service worker must be served from root with the correct scope
      {
        source: "/sw.js",
        headers: [
          {
            key: "Service-Worker-Allowed",
            value: "/",
          },
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
        ],
      },
      // Manifest should not be cached aggressively
      {
        source: "/manifest.json",
        headers: [
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
