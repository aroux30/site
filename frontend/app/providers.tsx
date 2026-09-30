"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, useState, useEffect, type ReactNode } from "react";
import { Toaster } from "@/components/ui/toaster";
import { SmoothScroll } from "@/components/ui/smooth-scroll";
import { TopProgressBar } from "@/components/ui/top-progress-bar";
import { initGlobalErrorHandlers } from "@/lib/observability/error-boundary";
import { initWebVitals } from "@/lib/observability/vitals";
import { initOfflineSync } from "@/lib/observability/offline-buffer";
import { PWAProvider } from "@/components/shared/pwa-provider";

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
      <Suspense fallback={null}>
        <TopProgressBar />
      </Suspense>
      <SmoothScroll>
        {children}
        <Toaster />
        <PWAProvider />
      </SmoothScroll>
    </QueryClientProvider>
  );
}