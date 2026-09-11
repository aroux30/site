"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect, type ReactNode } from "react";
import { Toaster } from "@/components/ui/toaster";
import { SmoothScroll } from "@/components/ui/smooth-scroll";

export function Providers({ children }: { children: ReactNode }) {
  useEffect(() => {
    const flush = () => {
      if (typeof window !== "undefined") {
        const w = window as unknown as { $RV?: (_a: unknown[]) => void; $RB?: unknown[] };
        if (typeof w.$RV === "function" && Array.isArray(w.$RB) && w.$RB.length > 0) {
          w.$RV(w.$RB);
        }
      }
    };
    flush();
    const t1 = setTimeout(flush, 50);
    const t2 = setTimeout(flush, 200);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []);

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

  return (
    <QueryClientProvider client={queryClient}>
      <SmoothScroll>
        {children}
        <Toaster />
      </SmoothScroll>
    </QueryClientProvider>
  );
}
