"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, useState, useEffect, type ReactNode } from "react";
import { Toaster } from "@/components/ui/toaster";
import { SmoothScroll } from "@/components/ui/smooth-scroll";
import { TopProgressBar } from "@/components/ui/top-progress-bar";
import { initGlobalErrorHandlers } from "@/lib/observability/error-boundary";
import { initWebVitals } from "@/lib/observability/vitals";
import { initOfflineSync } from "@/lib/observability/offline-buffer";
import { SiteBrandingProvider } from "@/components/layout/site-branding-provider";
import { PWAProvider } from "@/components/shared/pwa-provider";
import { loadCatalogue, DEFAULT_LOCALE } from "@/lib/i18n";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
            retry: 2,
          },
        },
      }),
  );

  useEffect(() => {
    // The UI-string catalogue, once for the whole app. It lived in a database
    // table with a public endpoint and no reader, so every string an operator
    // wrote was stored and never rendered. Not awaited: `t` falls back to the
    // key, and a page must not wait for a translation to render.
    void loadCatalogue(DEFAULT_LOCALE);

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
      <SiteBrandingProvider>
      <Suspense fallback={null}>
        <TopProgressBar />
      </Suspense>
      <SmoothScroll>
        {children}
        <Toaster />
        <PWAProvider />
      </SmoothScroll>
      </SiteBrandingProvider>
    </QueryClientProvider>
  );
}