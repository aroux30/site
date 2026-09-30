"use client";

import React from "react";
import {
  AlertTriangle,
  Inbox,
  Loader2,
  RefreshCw,
  WifiOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, toPersianDigits } from "@/lib/utils";

/**
 * Shared request-state primitives for the operational admin views.
 *
 * The distinction that matters here is *empty* versus *unavailable*:
 *
 * - Empty means the backend answered and reported zero records. That is an
 *   operational fact and is rendered as such.
 * - Unavailable means we could not read the data, or the backend did not report
 *   the field at all. The peak financial-safety failure mode in these views is
 *   rendering an unavailable value as `0`, which reads as "nothing wrong" when
 *   the truth is "we do not know". `UnavailableValue` exists so a missing field
 *   can never be mistaken for a clean count.
 */

export type AsyncPhase = "loading" | "ready" | "error";

export interface LoadingStateProps {
  label?: string;
  rows?: number;
  className?: string;
}

export function LoadingState({
  label = "در حال دریافت داده‌ها...",
  rows = 3,
  className,
}: LoadingStateProps) {
  const rowKeys = React.useMemo(
    () => Array.from({ length: rows }, (_, i) => `skeleton-${i}`),
    [rows],
  );

  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={cn("space-y-3", className)}
    >
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        <span>{label}</span>
      </div>
      <div className="space-y-2">
        {rowKeys.map((key) => (
          <Skeleton key={key} className="h-9 w-full" />
        ))}
      </div>
    </div>
  );
}

export interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  isRetrying?: boolean;
  title?: string;
  className?: string;
}

export function ErrorState({
  message,
  onRetry,
  isRetrying = false,
  title = "دریافت داده‌ها ناموفق بود",
  className,
}: ErrorStateProps) {
  return (
    <Card
      role="alert"
      className={cn(
        "flex flex-col gap-3 border-red-500/40 bg-red-500/5 p-4 text-xs sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="flex items-start gap-2.5">
        <WifiOff
          className="mt-0.5 h-4 w-4 shrink-0 text-red-600"
          aria-hidden="true"
        />
        <div className="space-y-1">
          <p className="font-bold text-red-700 dark:text-red-300">{title}</p>
          <p className="leading-relaxed text-muted-foreground">{message}</p>
        </div>
      </div>
      {onRetry && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onRetry}
          disabled={isRetrying}
          className="shrink-0 gap-1.5 text-xs"
        >
          <RefreshCw
            className={cn("h-3.5 w-3.5", isRetrying && "animate-spin")}
            aria-hidden="true"
          />
          تلاش مجدد
        </Button>
      )}
    </Card>
  );
}

export interface EmptyStateProps {
  title: string;
  description?: string;
  className?: string;
}

export function EmptyState({ title, description, className }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        "flex flex-col items-center gap-2 px-4 py-10 text-center",
        className,
      )}
    >
      <Inbox
        className="h-6 w-6 text-muted-foreground opacity-60"
        aria-hidden="true"
      />
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {description && (
        <p className="max-w-md text-xs leading-relaxed text-muted-foreground">
          {description}
        </p>
      )}
    </div>
  );
}

export interface UnavailableValueProps {
  /** Explains *why* the value is unavailable, so it cannot read as a zero. */
  reason?: string;
  className?: string;
}

/**
 * Renders an explicitly unavailable value. Use this instead of `0`, `-`, or an
 * empty cell whenever the backend did not report a number.
 */
export function UnavailableValue({ reason, className }: UnavailableValueProps) {
  return (
    <span
      title={reason ?? "این مقدار از سرویس دریافت نشد."}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-dashed border-amber-500/50 bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-400",
        className,
      )}
    >
      <AlertTriangle className="h-3 w-3" aria-hidden="true" />
      نامشخص
    </span>
  );
}

export interface PartialDataNoticeProps {
  count: number;
  label: string;
  className?: string;
}

/** Shown when some backend records could not be read as contract records. */
export function PartialDataNotice({
  count,
  label,
  className,
}: PartialDataNoticeProps) {
  if (count <= 0) return null;

  return (
    <div
      role="status"
      className={cn(
        "flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300",
        className,
      )}
    >
      <AlertTriangle
        className="mt-0.5 h-3.5 w-3.5 shrink-0"
        aria-hidden="true"
      />
      <span>
        {toPersianDigits(count)} مورد از {label} با ساختار شناخته‌شده این نسخه
        از رابط برنامه‌نویسی مطابقت نداشت و نمایش داده نشد. این موارد نادیده
        گرفته نشده‌اند؛ برای بررسی به گزارش‌های سرور مراجعه کنید.
      </span>
    </div>
  );
}

export interface MissingDataNoticeProps {
  count: number;
  label: string;
  className?: string;
}

/**
 * Shown when the backend holds more records than this view loaded.
 *
 * A table that renders 20 of 38 findings without saying so reads as complete,
 * and the findings it hides are the ones the operator most needs to see. This
 * states the shortfall plainly rather than implying full coverage.
 */
export function MissingDataNotice({
  count,
  label,
  className,
}: MissingDataNoticeProps) {
  if (count <= 0) return null;

  return (
    <div
      role="status"
      className={cn(
        "flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300",
        className,
      )}
    >
      <AlertTriangle
        className="mt-0.5 h-3.5 w-3.5 shrink-0"
        aria-hidden="true"
      />
      <span>
        {toPersianDigits(count)} مورد دیگر از {label} در سرویس موجود است که در
        این نمایش بارگذاری نشد. فهرست بالا کامل نیست؛ برای دیدن همهٔ موارد
        فیلترها را محدود کنید.
      </span>
    </div>
  );
}
