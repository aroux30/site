"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DirectionProvider } from "@radix-ui/react-direction";
import { Suspense, useState, useEffect, type ReactNode } from "react";
import { Toaster } from "@/components/ui/toaster";
import { SmoothScroll } from "@/components/ui/smooth-scroll";
import { TopProgressBar } from "@/components/ui/top-progress-bar";
import { initGlobalErrorHandlers } from "@/lib/observability/error-boundary";
import { initWebVitals } from "@/lib/observability/vitals";
import { initOfflineSync } from "@/lib/observability/offline-buffer";
import { SiteBrandingProvider } from "@/components/layout/site-branding-provider";
import { PWAProvider } from "@/components/shared/pwa-provider";
import { ConfirmDialogProvider } from "@/components/ui/confirm-dialog";
import { CalendarProvider } from "@/lib/calendar-context";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
            // Retry only failures that can heal on their own (network drops,
            // rate limits, server errors). A 4xx answer — 404 unknown slug,
            // 401 signed-out visitor, 403 forbidden — is final for that
            // request; retrying it just tripled the API error noise and the
            // red dev-overlay issues on every dead-link visit.
            retry: (failureCount, error) => {
              if (failureCount >= 2) return false;
              const status =
                (error as { response?: { status?: number } })?.response
                  ?.status ?? 0;
              if (status === 408 || status === 429 || status >= 500) {
                return true;
              }
              return status === 0; // network error / no response
            },
          },
        },
      }),
  );

  useEffect(() => {
    // Initialize global unhandled exception and rejection handlers
    const cleanupErrorHandlers = initGlobalErrorHandlers();

    // Initialize browser performance observers for Core Web Vitals
    const cleanupWebVitals = initWebVitals();

    // Initialize offline telemetry synchronization on network recovery
    const cleanupOfflineSync = initOfflineSync();

    return () => {
      cleanupErrorHandlers();
      cleanupWebVitals();
      cleanupOfflineSync();
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {/* Radix defaults every primitive to LTR when it sees no direction:
          `useDirection` resolves `localDir || globalDir || "ltr"`. Without
          this provider, Tabs renders its root div with dir="ltr" (which
          flipped the currency page's rows) and menus position their
          collision logic as if the page were LTR. The store is RTL-only
          (layout.tsx sets dir="rtl" on <html>), so the global direction is a
          constant — not state — and a per-component dir prop is then only
          noise. Kept in Providers rather than a server layout because
          DirectionProvider is a client context. */}
      <DirectionProvider dir="rtl">
      <SiteBrandingProvider>
      {/* In-app confirmation, available to every screen. `window.confirm` is
          silently a no-op inside a sandboxed iframe (no `allow-modals`), so a
          destructive handler that gates on it never runs in an embedded
          preview — the button just looks dead. */}
      <ConfirmDialogProvider>
      <CalendarProvider>
      <Suspense fallback={null}>
        <TopProgressBar />
      </Suspense>
      <SmoothScroll>
        {children}
        <Toaster />
        <PWAProvider />
      </SmoothScroll>
      </CalendarProvider>
      </ConfirmDialogProvider>
      </SiteBrandingProvider>
      </DirectionProvider>
    </QueryClientProvider>
  );
}