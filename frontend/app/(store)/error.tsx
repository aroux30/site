"use client";

import { useEffect } from "react";
import { logger } from "@/lib/observability/logger";
import { getActiveTraceId } from "@/lib/observability/tracer";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function StoreError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Store route error boundary caught exception", error, {
      digest: error.digest,
      traceId: getActiveTraceId(),
    });
  }, [error]);

  return (
    <div className="flex min-h-[50vh] w-full flex-col items-center justify-center p-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
        <AlertTriangle className="h-7 w-7" aria-hidden="true" />
      </div>

      <h2 className="mt-5 text-xl font-bold tracking-tight text-foreground">
        مشکلی در نمایش این صفحه پیش آمد
      </h2>

      <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        لطفاً دوباره تلاش کنید. در صورت تکرار مشکل، تیم فنی مطلع شده است.
      </p>

      {error.digest && (
        <div
          className="mt-3 rounded-md bg-muted px-3 py-1 font-mono text-xs text-muted-foreground"
          dir="ltr"
        >
          {error.digest}
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <button
          onClick={() => reset()}
          className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-xs transition-colors hover:bg-primary/90 focus:outline-hidden focus:ring-2 focus:ring-primary/20"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          تلاش مجدد
        </button>

        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-xl border border-input bg-background px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-accent focus:outline-hidden focus:ring-2 focus:ring-ring/20"
        >
          <Home className="h-4 w-4" aria-hidden="true" />
          صفحه اصلی
        </Link>
      </div>
    </div>
  );
}
