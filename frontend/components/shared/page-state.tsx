"use client";

import { Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * Canonical loading / empty / error states for data pages (audit R8).
 *
 * Pages previously re-implemented the `Loader2 + animate-spin + caption`
 * block per surface with divergent captions; use these instead so the
 * feedback language is one design system, not per-page improvisation.
 */

export function PageLoader({
  message = "در حال بارگذاری...",
  className,
}: {
  message?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex min-h-[200px] w-full flex-col items-center justify-center gap-3 text-muted-foreground",
        className
      )}
    >
      <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden="true" />
      <span className="text-sm">{message}</span>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-[200px] w-full flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border bg-muted/20 p-8 text-center",
        className
      )}
    >
      {icon && <div className="text-muted-foreground/70">{icon}</div>}
      <h3 className="text-base font-bold text-foreground">{title}</h3>
      {description && (
        <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "خطایی رخ داد",
  description,
  action,
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex min-h-[160px] w-full flex-col items-center justify-center gap-2 rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center",
        className
      )}
    >
      <AlertCircle className="h-8 w-8 text-destructive" />
      <h3 className="text-base font-bold text-destructive">{title}</h3>
      {description && (
        <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="mt-3 gap-1.5 border-destructive/30 hover:bg-destructive/10 text-destructive"
        >
          <RefreshCw className="h-4 w-4" />
          تلاش مجدد
        </Button>
      )}
      {action && !onRetry && <div className="mt-3">{action}</div>}
    </div>
  );
}
