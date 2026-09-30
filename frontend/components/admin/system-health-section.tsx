"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Gauge,
  HelpCircle,
  Server,
  Zap,
} from "lucide-react";
import { UnavailableValue } from "@/components/admin/async-state";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { toPersianDigits } from "@/lib/utils";
import {
  calculateHealthScore,
  checkSloCompliance,
  componentsFromProbe,
  formatLatency,
  parseReadinessProbe,
  SERVICE_STATUS_LABELS,
  type SystemPerformanceMetrics,
} from "@/lib/system-metrics";

/**
 * System health & SLO monitoring panel (moved from the reports page when it
 * became the reporting hub; logic preserved verbatim).
 *
 * All metrics start unmeasured — nothing renders as healthy until the
 * readiness probe says so. A probe that did not answer marks every
 * dependency unmeasured instead of leaving the last good state up.
 */
export function SystemHealthSection() {
  const [perfMetrics, setPerfMetrics] = useState<SystemPerformanceMetrics>({
    avgResponseTimeMs: null,
    p95ResponseTimeMs: null,
    uptimePercent: null,
    errorRatePercent: null,
    requestsPerSecond: null,
    services: [],
    measured: false,
    lastUpdated: null,
  });

  const fetchProbe = useCallback(async () => {
    try {
      // GET /api/health/ready is outside the /api/v1 prefix, so it is
      // fetched directly; next.config.ts proxies /api/health/* to the
      // backend.
      const response = await fetch("/api/health/ready", {
        credentials: "include",
      });
      const body = await response.json().catch(() => null);
      const parsed = parseReadinessProbe(body);
      setPerfMetrics((prev) => ({
        ...prev,
        measured: parsed.measured,
        services: componentsFromProbe(parsed),
        lastUpdated: parsed.measured
          ? new Date().toLocaleTimeString("fa-IR")
          : null,
      }));
    } catch {
      setPerfMetrics((prev) => ({
        ...prev,
        measured: false,
        services: componentsFromProbe(parseReadinessProbe(null)),
        lastUpdated: null,
      }));
    }
  }, []);

  useEffect(() => {
    void fetchProbe();
  }, [fetchProbe]);

  return (
    <Card className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-foreground">
              پایش بلادرنگ سلامت سیستم و زمان پاسخ‌دهی (System Performance & SLOs)
            </h3>
            <p className="text-xs text-muted-foreground">
              مانیتورینگ تاخیر API، پایداری زیرساخت دیتابیس، کش، آبجکت استوریج و
              رعایت توافق‌نامه سطح خدمات
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {(() => {
            const score = calculateHealthScore(perfMetrics);
            if (score === null) {
              return (
                <Badge
                  variant="outline"
                  className="border-dashed border-amber-500/50 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-700 dark:text-amber-400"
                >
                  امتیاز سلامت سیستم: نامشخص
                </Badge>
              );
            }
            const healthy = score >= 80;
            return (
              <Badge
                variant="outline"
                className={`px-2.5 py-1 font-mono text-xs ${
                  healthy
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                    : "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                }`}
              >
                امتیاز سلامت سیستم: {toPersianDigits(score)}/۱۰۰
              </Badge>
            );
          })()}
          <span className="text-[11px] text-muted-foreground">
            {perfMetrics.lastUpdated
              ? `بروزرسانی: ${perfMetrics.lastUpdated}`
              : "بروزرسانی: نامشخص"}
          </span>
        </div>
      </div>

      {/* Performance metric tiles */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="space-y-1 rounded-xl border border-border bg-muted/30 p-3.5">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>میانگین زمان پاسخ</span>
            <Gauge className="h-4 w-4 text-primary" />
          </div>
          <p className="font-mono text-lg font-bold text-foreground" dir="ltr">
            {formatLatency(perfMetrics.avgResponseTimeMs)}
          </p>
          <span className="block text-[10px] text-muted-foreground">
            زمان پردازش رکوئست‌های سرور (اندازه‌گیری نشده)
          </span>
        </div>

        <div className="space-y-1 rounded-xl border border-border bg-muted/30 p-3.5">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>تأخیر صدک ۹۵ (p95)</span>
            <Zap className="h-4 w-4 text-amber-500" />
          </div>
          <p className="font-mono text-lg font-bold text-foreground" dir="ltr">
            {formatLatency(perfMetrics.p95ResponseTimeMs)}
          </p>
          <span className="block text-[10px] text-muted-foreground">
            حداکثر تاخیر ۹۵٪ درخواست‌ها
          </span>
        </div>

        <div className="space-y-1 rounded-xl border border-border bg-muted/30 p-3.5">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>پایداری و آپتایم</span>
            {perfMetrics.uptimePercent === null ? (
              <HelpCircle className="h-4 w-4 text-amber-600" />
            ) : (
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            )}
          </div>
          {perfMetrics.uptimePercent === null ? (
            <p className="text-lg font-bold">
              <UnavailableValue reason="هیچ اندازه‌گیری آپ‌تایم از سرویس دریافت نشد." />
            </p>
          ) : (
            <p className="font-mono text-lg font-bold text-emerald-600" dir="ltr">
              {toPersianDigits(perfMetrics.uptimePercent)}٪
            </p>
          )}
          <span className="block text-[10px] text-muted-foreground">
            میزان در دسترس بودن سرویس‌ها
          </span>
        </div>

        <div className="space-y-1 rounded-xl border border-border bg-muted/30 p-3.5">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>نرخ خطای درخواستها</span>
            <AlertTriangle className="h-4 w-4 text-primary" />
          </div>
          {perfMetrics.errorRatePercent === null ? (
            <p className="text-lg font-bold">
              <UnavailableValue reason="هیچ اندازه‌گیری نرخ خطا از سرویس دریافت نشد." />
            </p>
          ) : (
            <p className="font-mono text-lg font-bold text-foreground" dir="ltr">
              {toPersianDigits(perfMetrics.errorRatePercent)}٪
            </p>
          )}
          <span className="block text-[10px] text-muted-foreground">
            خطاهای وضعیت 5xx در بازه
          </span>
        </div>
      </div>

      {/* Infrastructure component health */}
      <div className="space-y-3">
        <span className="block text-xs font-bold text-foreground">
          وضعیت اجزای زیرساخت و سرویس‌های متصل:
        </span>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {perfMetrics.services.map((svc) => {
            const isHealthy = svc.status === "HEALTHY";
            const isUnmeasured = svc.status === "UNMEASURED";
            const badgeClass = isHealthy
              ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30"
              : isUnmeasured
                ? "border-dashed border-amber-500/50 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                : "bg-red-500/10 text-red-700 dark:text-red-300 border-red-500/40";
            return (
              <div
                key={svc.name}
                className="flex items-center justify-between rounded-xl border border-border/70 bg-card p-3 text-xs"
              >
                <div className="flex items-center gap-2">
                  <Server className="h-4 w-4 text-muted-foreground" />
                  <span className="font-semibold text-foreground">{svc.name}</span>
                </div>

                <div className="flex items-center gap-3">
                  {svc.latencyMs === null ? (
                    <span className="text-[10px] text-muted-foreground">
                      تأخیر نامشخص
                    </span>
                  ) : (
                    <span className="font-mono text-muted-foreground" dir="ltr">
                      {toPersianDigits(svc.latencyMs)} ms
                    </span>
                  )}
                  <Badge
                    variant={isHealthy ? "outline" : "destructive"}
                    className={`text-[10px] ${badgeClass}`}
                  >
                    {SERVICE_STATUS_LABELS[svc.status]}
                  </Badge>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* SLO compliance banner */}
      {(() => {
        const slo = checkSloCompliance(perfMetrics);
        const hasViolations = slo.violations.length > 0;
        const hasUnverified = slo.unverified.length > 0;

        const tone = hasViolations
          ? "border border-red-500/40 bg-red-500/10 text-red-800 dark:text-red-300"
          : hasUnverified
            ? "border border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300"
            : "border border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300";

        const title = hasViolations
          ? "هشدار عدم تطابق با استانداردهای سطح خدمات (SLO):"
          : hasUnverified
            ? "رعایت استانداردهای سطح خدمات (SLO) قابل تأیید نیست:"
            : "کلیه شاخص‌های عملکردی سامانه منطبق بر استانداردهای توافق‌نامه سطح خدمات (SLO) پروداکشن است.";

        return (
          <div className={`rounded-xl p-3 text-xs ${tone}`}>
            <div className="flex items-center gap-2">
              {hasViolations ? (
                <AlertTriangle className="h-4 w-4 shrink-0" />
              ) : hasUnverified ? (
                <HelpCircle className="h-4 w-4 shrink-0" />
              ) : (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
              )}
              <span className="font-bold">{title}</span>
            </div>
            {hasViolations && (
              <div className="mt-1 space-y-0.5 ps-6 opacity-90">
                {slo.violations.map((v) => (
                  <p key={v}>• {v}</p>
                ))}
              </div>
            )}
            {hasUnverified && (
              <div className="mt-1 space-y-0.5 ps-6 opacity-90">
                {slo.unverified.map((v) => (
                  <p key={v}>• {v}</p>
                ))}
              </div>
            )}
          </div>
        );
      })()}
    </Card>
  );
}
