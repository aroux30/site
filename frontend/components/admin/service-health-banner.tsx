"use client";

import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  MessageSquareOff,
  RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  checkNotificationGuard,
  type ProviderHealthStatus,
} from "@/lib/ops-exceptions";

export interface ServiceHealthBannerProps {
  providers: ProviderHealthStatus[];
  onRefresh?: () => void;
  isLoading?: boolean;
}

/**
 * Communications service banner.
 *
 * Three states, not two: outage, unconfigured/unverified, and verified-healthy.
 * The distinction that matters is that a provider with configuration but no
 * runtime health signal is reported as *unverified*, never as healthy. The
 * banner previously derived `isHealthy` from the provider's `is_active` setting
 * and announced "all services operational" — a claim the settings value cannot
 * support.
 */
export function ServiceHealthBanner({
  providers,
  onRefresh,
  isLoading = false,
}: ServiceHealthBannerProps) {
  const guardResult = checkNotificationGuard(providers);

  const isClear =
    !guardResult.hasOutage &&
    guardResult.unconfiguredCount === 0 &&
    guardResult.unverifiedCount === 0;

  if (isClear) {
    return (
      <div
        className="flex items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-800 dark:text-emerald-300"
        dir="rtl"
        role="status"
      >
        <div className="flex items-center gap-2.5">
          <CheckCircle2
            className="h-4 w-4 shrink-0 text-emerald-600"
            aria-hidden="true"
          />
          <span className="font-semibold">
            {providers.length === 0
              ? "سرویس‌دهنده اعلانی برای بررسی گزارش نشده است."
              : "سلامت زمان اجرای سرویس‌های اعلان تأیید شده است."}
          </span>
        </div>
        {onRefresh && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
            className="h-7 shrink-0 gap-1 text-[11px] text-emerald-700 hover:bg-emerald-500/20"
          >
            <RefreshCw
              className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            بررسی مجدد
          </Button>
        )}
      </div>
    );
  }

  const isOutage = guardResult.hasOutage;

  return (
    <div
      className={`space-y-2 rounded-xl p-4 text-xs ${
        isOutage
          ? "border border-red-500/40 bg-red-500/10 text-red-800 dark:text-red-300"
          : "border border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300"
      }`}
      dir="rtl"
      role="alert"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {isOutage ? (
            <MessageSquareOff
              className="h-5 w-5 shrink-0 text-red-600"
              aria-hidden="true"
            />
          ) : (
            <AlertTriangle
              className="h-5 w-5 shrink-0 text-amber-600"
              aria-hidden="true"
            />
          )}
          <span className="text-sm font-bold">
            {isOutage
              ? "هشدار بحرانی: اختلال تأییدشده در سرویس‌دهنده اعلان"
              : "توجه: وضعیت کامل سرویس‌های اعلان تأیید نشده است"}
          </span>
        </div>

        {onRefresh && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
            className="h-7 shrink-0 gap-1 text-xs"
          >
            <RefreshCw
              className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            بروزرسانی وضعیت
          </Button>
        )}
      </div>

      <div className="space-y-1 ps-7 pt-1">
        {guardResult.warnings.map((warn, index) => (
          // Index-qualified: two providers can raise byte-identical warnings,
          // and a duplicated key makes React drop one of the lines.
          <p key={`${index}:${warn}`} className="leading-relaxed opacity-90">
            • {warn}
          </p>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 ps-7 pt-2">
        {providers.map((provider, index) => {
          const serviceTitle =
            provider.service === "sms" ? "پیامک (SMS)" : "ایمیل (Email)";

          let label: string;
          let variant: "outline" | "destructive" | "secondary" | "warning";

          if (!provider.isConfigured) {
            label = "غیرفعال (پیکربندی نشده)";
            variant = "secondary";
          } else if (!provider.healthVerified) {
            label = "سلامت تأییدنشده";
            variant = "warning";
          } else if (provider.status === "FAILED") {
            label = "خطای اتصال";
            variant = "destructive";
          } else if (provider.status === "DEGRADED") {
            label = "کیفیت کاهشیافته";
            variant = "warning";
          } else {
            label = "سالم (تأییدشده)";
            variant = "outline";
          }

          return (
            // Keyed by service+provider: several SMS providers share one
            // service, so `service` alone produced duplicate keys and React
            // dropped badges. The provider name is shown for the same reason —
            // four "sms" badges in a row were indistinguishable.
            // data-testid carries the key so a test can prove uniqueness.
            <Badge
              key={`${provider.service}:${provider.provider}:${index}`}
              data-testid="provider-health-badge"
              variant={variant}
              className="gap-1 text-[11px]"
            >
              {provider.healthVerified ? (
                <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
              ) : (
                <HelpCircle className="h-3 w-3" aria-hidden="true" />
              )}
              {provider.provider} ({serviceTitle}): {label}
            </Badge>
          );
        })}
      </div>
    </div>
  );
}

export default ServiceHealthBanner;
