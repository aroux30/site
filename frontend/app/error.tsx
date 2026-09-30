"use client";

import { useEffect } from "react";
import { logger } from "@/lib/observability/logger";
import { getActiveTraceId } from "@/lib/observability/tracer";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Route error boundary caught exception", error, {
      digest: error.digest,
      traceId: getActiveTraceId(),
    });
  }, [error]);

  return (
    <div className="flex min-h-[70vh] w-full flex-col items-center justify-center p-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-destructive/10 text-destructive shadow-xs">
        <AlertTriangle className="h-8 w-8" aria-hidden="true" />
      </div>

      <h1 className="mt-6 text-2xl font-bold tracking-tight text-foreground">
        خطایی در بارگذاری صفحه رخ داده است
      </h1>

      <p className="mt-3 max-w-md text-sm leading-relaxed text-muted-foreground">
        متأسفانه در پردازش درخواست شما مشکلی پیش آمده است. سیستم به طور خودکار گزارش این خطا را جهت بررسی تیم فنی ثبت کرد.
      </p>

      {error.digest && (
        <div className="mt-4 rounded-md bg-muted px-3 py-1 font-mono text-xs text-muted-foreground" dir="ltr">
          کد پیگیری خطا: {error.digest}
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
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
          بازگشت به صفحه اصلی
        </Link>
      </div>
    </div>
  );
}