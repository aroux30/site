"use client";

import { useMemo, useState } from "react";
import {
  CalendarDays,
  RefreshCw,
  AlertTriangle,
  Clock,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  calendarApi,
  type CalendarEvent,
  type CalendarResponse,
} from "@/lib/api/calendar";
import { useAdminQuery } from "@/lib/api/admin-query";
import { toPersianDigits } from "@/lib/utils";

const CALENDAR_QUERY_KEY = "admin-calendar" as const;

const SOURCE_LABELS: Record<string, string> = {
  content: "انتشار محتوا",
  discounts: "تخفیف",
  notifications: "اعلان",
  messaging: "کمپین",
  subscriptions: "اشتراک",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  cms_publish: "انتشار صفحه",
  cms_unpublish: "پایان انتشار",
  discount_window: "بازه تخفیف",
  notice_window: "اعلان زمان‌دار",
  campaign_send: "ارسال کمپین",
  subscription_billing: "صورتحساب اشتراک",
};

const SOURCE_COLORS: Record<string, string> = {
  content: "bg-sky-500/15 text-sky-700 dark:text-sky-400",
  discounts: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  notifications: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  messaging: "bg-violet-500/15 text-violet-700 dark:text-violet-400",
  subscriptions: "bg-rose-500/15 text-rose-700 dark:text-rose-400",
};

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function jalaliDayLabel(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString("fa-IR", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function isRunningNow(event: CalendarEvent, now: Date): boolean {
  const start = new Date(event.start_at);
  if (!event.end_at) {
    return start.toDateString() === now.toDateString();
  }
  const end = new Date(event.end_at);
  return start <= now && now <= end;
}

export default function AdminCalendarPage() {
  const [fromDate, setFromDate] = useState(() => toISODate(new Date()));
  const [toDate, setToDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return toISODate(d);
  });
  const [activeSources, setActiveSources] = useState<Set<string>>(new Set());

  // Stable string key for the source set: a sorted join keeps the query key a
  // stable array of primitives instead of an inline array that changes
  // identity every render.
  const sourcesKey = useMemo(
    () => [...activeSources].sort().join(","),
    [activeSources],
  );

  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery<CalendarResponse>({
    queryKey: [CALENDAR_QUERY_KEY, fromDate, toDate, sourcesKey],
    queryFn: () =>
      calendarApi.list({
        from_date: `${fromDate}T00:00:00Z`,
        to_date: `${toDate}T00:00:00Z`,
        sources: activeSources.size > 0 ? [...activeSources].sort() : undefined,
      }),
    fallbackError: "خطا در دریافت تقویم: دسترسی calendar:read لازم است، یا بازه نامعتبر است.",
    toastOnError: true,
  });

  const grouped = useMemo(() => {
    const byDay = new Map<string, CalendarEvent[]>();
    for (const event of data?.events ?? []) {
      const day = event.start_at.slice(0, 10);
      const list = byDay.get(day) ?? [];
      list.push(event);
      byDay.set(day, list);
    }
    return [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [data]);

  const now = new Date();
  const brokenSources = Object.entries(data?.sources ?? {}).filter(
    ([, report]) => !report.ok,
  );

  const toggleSource = (module: string) => {
    setActiveSources((prev) => {
      const next = new Set(prev);
      if (next.has(module)) next.delete(module);
      else next.add(module);
      return next;
    });
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <CalendarDays className="h-5 w-5 text-primary" />
            تقویم عملیاتی
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            نمای یکجا از هر چیزی که زمان‌بندی شده است — انتشار محتوا، بازه‌های
            تخفیف، اعلان‌ها، کمپین‌ها و صورتحساب اشتراک‌ها.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="ms-2 h-4 w-4" />
          بروزرسانی
        </Button>
      </div>

      {brokenSources.length > 0 && (
        <Card className="border-destructive/40 bg-destructive/5 p-3">
          <div className="flex items-start gap-2 text-xs">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <p className="text-muted-foreground">
              این منابع پاسخ ندادند و رویدادهایشان در نمای زیر نیست:{" "}
              {brokenSources.map(([name]) => SOURCE_LABELS[name] ?? name).join("، ")}
              . نمودار ناقص است، نه خالی.
            </p>
          </div>
        </Card>
      )}

      <Card className="p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Label htmlFor="cal-from">از تاریخ</Label>
            <Input
              id="cal-from"
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              dir="ltr"
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="cal-to">تا تاریخ</Label>
            <Input
              id="cal-to"
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              dir="ltr"
              className="mt-1"
            />
          </div>
          <div className="sm:col-span-2">
            <Label>منابع</Label>
            <div className="mt-1 flex flex-wrap gap-2">
              <button
                onClick={() => setActiveSources(new Set())}
                className={`rounded-full px-3 py-1 text-xs transition-colors ${
                  activeSources.size === 0
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/80"
                }`}
              >
                همه
              </button>
              {Object.keys(SOURCE_LABELS).map((m) => (
                <button
                  key={m}
                  onClick={() => toggleSource(m)}
                  className={`rounded-full px-3 py-1 text-xs transition-colors ${
                    activeSources.has(m)
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted hover:bg-muted/80"
                  }`}
                >
                  {SOURCE_LABELS[m]}
                  {data?.sources[m] ? (
                    <span className="ms-1 text-[10px] opacity-75">
                      ({toPersianDigits(String(data.sources[m].count))})
                    </span>
                  ) : null}
                </button>
              ))}
            </div>
          </div>
        </div>
        <p className="mt-3 text-[11px] text-muted-foreground">
          تقویم فقط می‌خواند؛ برای تغییر هر رویداد از صفحه همان ماژول اقدام
          کنید تا دو مسیر نوشتن برای یک واقعیت ایجاد نشود.
        </p>
      </Card>

      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : grouped.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          در این بازه رویدادی زمان‌بندی نشده است.
        </Card>
      ) : (
        <div className="space-y-4">
          {grouped.map(([day, events]) => (
            <div key={day}>
              <div className="mb-2 flex items-center gap-2">
                <h3 className="text-sm font-semibold">{jalaliDayLabel(day)}</h3>
                <Badge variant="outline" className="text-[10px]">
                  {toPersianDigits(String(events.length))} رویداد
                </Badge>
              </div>
              <div className="space-y-1.5">
                {events.map((event) => {
                  const running = isRunningNow(event, now);
                  return (
                    <Card
                      key={`${event.source_module}-${event.entity_id}-${event.event_type}-${event.start_at}`}
                      className={`p-3 ${running ? "border-primary/40 bg-primary/5" : ""}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex min-w-0 items-center gap-2">
                          <span
                            className={`rounded px-2 py-0.5 text-[10px] font-medium ${
                              SOURCE_COLORS[event.source_module] ?? "bg-muted"
                            }`}
                          >
                            {SOURCE_LABELS[event.source_module] ??
                              event.source_module}
                          </span>
                          <span className="truncate text-sm">{event.title}</span>
                          {running && (
                            <span className="flex shrink-0 items-center gap-1 text-[10px] text-primary">
                              <Zap className="h-3 w-3" />
                              در جریان
                            </span>
                          )}
                        </div>
                        <div className="flex shrink-0 items-center gap-3 text-[11px] text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {toPersianDigits(
                              new Date(event.start_at).toLocaleTimeString("fa-IR", {
                                hour: "2-digit",
                                minute: "2-digit",
                              }),
                            )}
                          </span>
                          {event.end_at && (
                            <span>
                              تا{" "}
                              {toPersianDigits(
                                new Date(event.end_at).toLocaleDateString("fa-IR"),
                              )}
                            </span>
                          )}
                          <span className="text-[10px]">
                            {EVENT_TYPE_LABELS[event.event_type] ?? event.event_type}
                          </span>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
