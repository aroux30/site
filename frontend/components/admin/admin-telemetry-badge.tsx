"use client";

import React, { useState, useEffect } from "react";
import {
  Activity,
  Wifi,
  Copy,
  Check,
  RefreshCw,
  Clock,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { metrics, type LatencySummary } from "@/lib/observability/metrics";
import { getActiveTraceId } from "@/lib/observability/tracer";
import { toPersianDigits } from "@/lib/utils";

// ponytail: in-memory admin telemetry polling -> skipped: websocket live push, add when real-time backend agent metrics are streamed.

export function AdminTelemetryBadge() {
  const [summary, setSummary] = useState<LatencySummary>(() =>
    metrics.getApiLatencySummary(),
  );
  const [traceId, setTraceId] = useState<string>("");
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const refresh = () => {
    setSummary(metrics.getApiLatencySummary());
    setTraceId(getActiveTraceId());
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleCopyTrace = async () => {
    if (!traceId) return;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(traceId);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch {
      // Ignore clipboard write restrictions
    }
  };

  // Health classification based on P50 latency and error rate
  let statusColor = "text-muted-foreground bg-muted border-border";
  let dotColor = "bg-slate-400";
  let statusText = "در انتظار داده";

  if (summary.count > 0) {
    if (summary.p50 < 250 && summary.errorRatePercent === 0) {
      statusColor =
        "text-emerald-700 bg-emerald-500/10 border-emerald-500/20 dark:text-emerald-400";
      dotColor = "bg-emerald-500";
      statusText = `پایدار (${toPersianDigits(Math.round(summary.p50))}ms)`;
    } else if (summary.p50 < 600 && summary.errorRatePercent < 5) {
      statusColor =
        "text-amber-700 bg-amber-500/10 border-amber-500/20 dark:text-amber-400";
      dotColor = "bg-amber-500";
      statusText = `متوسط (${toPersianDigits(Math.round(summary.p50))}ms)`;
    } else {
      statusColor =
        "text-red-700 bg-red-500/10 border-red-500/20 dark:text-red-400";
      dotColor = "bg-red-500";
      statusText = `کند (${toPersianDigits(Math.round(summary.p50))}ms)`;
    }
  }

  return (
    <div className="relative inline-block text-right" dir="rtl">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`focus:outline-hidden inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-all hover:opacity-90 ${statusColor}`}
        title="وضعیت رصدپذیری و تاخیر کلاینت"
        aria-expanded={isOpen}
      >
        <span className={`h-2 w-2 animate-pulse rounded-full ${dotColor}`} />
        <Activity className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="hidden font-sans sm:inline">{statusText}</span>
      </button>

      {isOpen && (
        <>
          {/* Backdrop for closing */}
          <div
            className="fixed inset-0 z-40 bg-transparent"
            onClick={() => setIsOpen(false)}
          />

          <div className="absolute left-0 top-full z-50 mt-2 w-72 rounded-2xl border border-border bg-popover p-4 text-popover-foreground shadow-xl">
            <div className="flex items-center justify-between border-b border-border pb-2.5">
              <div className="flex items-center gap-1.5 text-xs font-bold">
                <Wifi className="h-4 w-4 text-primary" />
                <span>رصدپذیری کلاینت و تاخیر شبکه</span>
              </div>
              <button
                onClick={refresh}
                className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                title="بروزرسانی شاخص‌ها"
              >
                <RefreshCw className="h-3 w-3" />
              </button>
            </div>

            <div className="mt-3 space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">
                  تاخیر میانه (P50):
                </span>
                <span className="font-semibold text-foreground" dir="ltr">
                  {toPersianDigits(Math.round(summary.p50))} ms
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">
                  تاخیر صدک ۹۵ (P95):
                </span>
                <span className="font-semibold text-foreground" dir="ltr">
                  {toPersianDigits(Math.round(summary.p95))} ms
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">
                  نرخ خطای درخواست‌ها:
                </span>
                <span
                  className={`font-semibold ${summary.errorRatePercent > 0 ? "text-destructive" : "text-emerald-600"}`}
                >
                  {toPersianDigits(summary.errorRatePercent)}٪
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">
                  تعداد درخواست‌های ثبت‌شده:
                </span>
                <span className="font-semibold text-foreground">
                  {toPersianDigits(summary.count)}
                </span>
              </div>

              {summary.slowRequestsCount > 0 && (
                <div className="flex items-center justify-between text-amber-600 dark:text-amber-400">
                  <span className="flex items-center gap-1">
                    <AlertCircle className="h-3.5 w-3.5" />
                    درخواست‌های کند:
                  </span>
                  <span className="font-semibold">
                    {toPersianDigits(summary.slowRequestsCount)}
                  </span>
                </div>
              )}
            </div>

            {/* Trace ID Box */}
            <div className="mt-3 border-t border-border pt-2.5">
              <div className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>شناسه ردگیری فعال (Trace ID):</span>
                <button
                  onClick={handleCopyTrace}
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-emerald-500" />
                      کپی شد
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      کپی
                    </>
                  )}
                </button>
              </div>
              <div
                className="select-all break-all rounded-lg bg-muted px-2 py-1 text-left font-mono text-[10px] text-muted-foreground"
                dir="ltr"
              >
                {traceId || "—"}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default AdminTelemetryBadge;
