"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import {
  outboxApi,
  type OutboxMessageItem,
  type OutboxStatusFilter,
} from "@/lib/api/automation";
import { cn } from "@/lib/utils";

/**
 * Outbox dead letters (wave 6 #82).
 *
 * The outbox moved messages to DEAD_LETTER after exhausting retries, and had
 * four writers for that state and no reader — so a permanently failed event
 * was invisible and unreplayable. The event was simply lost.
 *
 * Requeue resets the retry counter on purpose: an operator replays after fixing
 * the cause, and a carried-forward exhausted counter would dead-letter it again
 * on the next failure.
 */

const STATUS_LABELS: Record<OutboxStatusFilter, string> = {
  dead_letter: "مرده (نیاز به بررسی)",
  failed: "ناموفق (در انتظار تلاش مجدد)",
  pending: "در صف",
  processed: "پردازش‌شده",
};

const STATUS_BADGE: Record<string, string> = {
  dead_letter: "bg-destructive/10 text-destructive border-destructive/30",
  failed: "bg-amber-500/10 text-amber-700 border-amber-500/30",
  pending: "bg-sky-500/10 text-sky-700 border-sky-500/30",
  processed: "bg-emerald-500/10 text-emerald-700 border-emerald-500/30",
};

function formatDate(value: string): string {
  try {
    // The API returns UTC ISO strings; render them in the admin's own zone so
    // an operator reading "2 ساعت پیش" is not misled by a server-time string.
    return new Intl.DateTimeFormat("fa-IR", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Tehran",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export default function OutboxDeadLettersPage() {
  const { toast } = useToast();
  const [statusFilter, setStatusFilter] = useState<OutboxStatusFilter>("dead_letter");
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<OutboxMessageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await outboxApi.list({ status: statusFilter, page, page_size: 50 });
      setRows(data.items);
      setTotal(data.total);
      setTotalPages(Math.max(1, data.total_pages));
    } catch (e) {
      // Never render a fabricated empty list on failure: "0 dead letters" and
      // "could not check" are very different facts to an operator.
      setError(e instanceof Error ? e.message : "خطا در دریافت پیام‌ها");
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleRequeue = async (row: OutboxMessageItem) => {
    setBusyId(row.id);
    try {
      await outboxApi.requeue(row.id);
      toast({ title: "پیام دوباره در صف قرار گرفت.", description: row.event_type });
      await load();
    } catch (e) {
      toast({
        title: "تلاش مجدد ناموفق بود",
        description: e instanceof Error ? e.message : "خطای ناشناخته",
        variant: "destructive",
      });
    } finally {
      setBusyId(null);
    }
  };

  const handlePurge = async (row: OutboxMessageItem) => {
    if (
      !window.confirm(
        `این پیام برای همیشه حذف می‌شود:\n\n${row.event_type}\n${row.aggregate_type} #${row.aggregate_id}\n\nاگر این رویداد باید اجرا شود، به‌جای حذف آن را دوباره در صف بگذارید.`
      )
    ) {
      return;
    }
    setBusyId(row.id);
    try {
      await outboxApi.purge(row.id);
      toast({ title: "پیام حذف شد." });
      await load();
    } catch (e) {
      toast({
        title: "حذف ناموفق بود",
        description: e instanceof Error ? e.message : "خطای ناشناخته",
        variant: "destructive",
      });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-bold">
            <AlertTriangle className="h-5 w-5 text-amber-600" />
            پیام‌های مردهٔ Outbox
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            رویدادهایی که پس از چند تلاش ناموفق متوقف شده‌اند. تا وقتی این‌ها دیده نشوند،
            رویدادها بی‌سروصدا از دست می‌روند.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={statusFilter}
            onValueChange={(v) => {
              setStatusFilter(v as OutboxStatusFilter);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-56" aria-label="فیلتر وضعیت">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(STATUS_LABELS) as OutboxStatusFilter[]).map((key) => (
                <SelectItem key={key} value={key}>
                  {STATUS_LABELS[key]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="button" variant="outline" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4" />
            تازه‌سازی
          </Button>
        </div>
      </div>

      {error ? (
        <Card className="border-destructive/40 bg-destructive/5 p-4">
          <p className="text-sm font-medium text-destructive">
            وضعیت صف را نمی‌توان خواند: {error}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            این به معنی «پیام مرده نداریم» نیست — به معنی این است که بررسی نشده است.
          </p>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-4 py-2 text-sm">
            <span>
              {total} پیام
              {statusFilter === "dead_letter" && total > 0 ? " نیازمند بررسی" : ""}
            </span>
            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  قبلی
                </Button>
                <span className="text-xs">
                  صفحه {page} از {totalPages}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  بعدی
                </Button>
              </div>
            )}
          </div>

          {loading ? (
            <p className="p-8 text-center text-sm text-muted-foreground">
              در حال دریافت پیام‌ها...
            </p>
          ) : rows.length === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">
              {statusFilter === "dead_letter"
                ? "پیام مرده‌ای وجود ندارد. همه‌چیز پردازش شده است."
                : "پیامی در این وضعیت وجود ندارد."}
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {rows.map((row) => (
                <li key={row.id} className="flex flex-wrap items-start gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium">
                        {row.event_type}
                      </span>
                      <Badge
                        variant="outline"
                        className={cn("text-[11px]", STATUS_BADGE[row.status])}
                      >
                        {STATUS_LABELS[row.status as OutboxStatusFilter] ?? row.status}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        تلاش {row.retry_count} از {row.max_retries}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {row.aggregate_type} #{row.aggregate_id} · {formatDate(row.created_at)}
                    </p>
                    {row.last_error && (
                      <pre className="mt-2 max-h-24 overflow-auto whitespace-pre-wrap rounded bg-muted/60 p-2 text-[11px] leading-relaxed text-muted-foreground">
                        {row.last_error}
                      </pre>
                    )}
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {row.status !== "processed" && row.status !== "pending" && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busyId === row.id}
                        onClick={() => void handleRequeue(row)}
                      >
                        <RotateCcw className="h-4 w-4" />
                        تلاش مجدد
                      </Button>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={busyId === row.id}
                      onClick={() => void handlePurge(row)}
                      aria-label={`حذف پیام ${row.event_type}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
