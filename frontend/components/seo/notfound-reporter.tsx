"use client";

/**
 * Report a 404 hit to the SEO monitor (Rank Math's 404 Monitor parity).
 *
 * The not-found page is a server component; the browser is the only place
 * that knows the full path the reader actually requested (including the
 * query string the server strips). This component fires one `keepalive`
 * POST on mount — keepalive so the request survives the reader navigating
 * away immediately, which is the normal behaviour on a 404.
 *
 * Failures are silent by design: the reader is already on an error page,
 * and a monitoring outage must not add a second error. The endpoint never
 * raises either — the two halves agree that this is best-effort.
 */

import { useEffect } from "react";

export function NotFoundReporter() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const payload = JSON.stringify({
        path: window.location.pathname.slice(0, 500),
        referrer: document.referrer ? document.referrer.slice(0, 500) : null,
        user_agent: navigator.userAgent ? navigator.userAgent.slice(0, 300) : null,
      });
      void fetch("/api/v1/seo/404/hit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true,
      }).catch(() => {
        // Silent: see the component docstring.
      });
    } catch {
      // JSON.stringify or fetch unavailable — nothing to report, nothing to do.
    }
  }, []);

  return null;
}
