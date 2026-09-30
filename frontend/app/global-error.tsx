"use client";

import { useEffect } from "react";
import { logger } from "@/lib/observability/logger";
import { getActiveTraceId } from "@/lib/observability/tracer";
import { AlertOctagon, RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.fatal("Global root error caught in global-error.tsx", error, {
      digest: error.digest,
      traceId: getActiveTraceId(),
    });
  }, [error]);

  return (
    <html lang="fa" dir="rtl">
      <body className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-6 font-sans text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
        <div className="flex w-full max-w-md flex-col items-center rounded-2xl border border-red-200 bg-white p-8 text-center shadow-lg dark:border-red-950/40 dark:bg-slate-900">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100 text-red-600 dark:bg-red-950/50 dark:text-red-400">
            <AlertOctagon className="h-8 w-8" aria-hidden="true" />
          </div>

          <h1 className="mt-6 text-xl font-bold">
            خطای سیستمی در اجرای برنامه
          </h1>

          <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
            متأسفانه یک خطای پیش‌بینی نشده در سطح اصلی سامانه رخ داده است.
            اطلاعات جهت رفع خطا ثبت گردید.
          </p>

          {error.digest && (
            <div
              className="mt-4 rounded-md bg-slate-100 px-3 py-1 font-mono text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400"
              dir="ltr"
            >
              کد پیگیری: {error.digest}
            </div>
          )}

          <div className="mt-6 flex w-full flex-col gap-3">
            <button
              onClick={() => reset()}
              className="shadow-xs inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              بارگذاری مجدد برنامه
            </button>

            <button
              onClick={() => {
                if (typeof window !== "undefined") {
                  window.location.href = "/";
                }
              }}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-transparent px-4 py-2.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              انتقال به صفحه اصلی
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
