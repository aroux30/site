"use client";

/**
 * Site health dashboard (WordPress Site Health parity).
 *
 * Runs server-side diagnostics (database, Redis, media storage, migrations,
 * table stats) and shows the result, plus a one-click database ANALYZE.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  HardDrive,
  RefreshCw,
  Server,
  XCircle,
  Wrench,
  Info,
  History,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { SiteHealthInfoTab } from "@/components/admin/site-health-info-tab";
import { siteHealthApi, type SiteHealthReport, type SiteHealthRun } from "@/lib/api/wp-parity";
import { toPersianDigits } from "@/lib/utils";
import { formatJalaliDateTime } from "@/lib/date";

const statusMeta = {
  good: {
    label: "سالم",
    icon: CheckCircle2,
    className: "text-emerald-600 dark:text-emerald-400",
    badge: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  },
  warning: {
    label: "هشدار",
    icon: AlertTriangle,
    className: "text-amber-600 dark:text-amber-400",
    badge: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  },
  critical: {
    label: "بحرانی",
    icon: XCircle,
    className: "text-rose-600 dark:text-rose-400",
    badge: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  },
} as const;

function checkIcon(name: string) {
  if (name.includes("Database") && !name.includes("Stats")) return Database;
  if (name.includes("Redis")) return Server;
  if (name.includes("Media")) return HardDrive;
  return Activity;
}

/** A run's length, in the unit a reader would say out loud.
 *
 * Under a second it reads as a number with a unit appended, because "0.4 ثانیه"
 * is harder to scan across a column than "۴۰۰ میلی‌ثانیه"; above it, seconds
 * with one decimal; above ten, whole seconds — past that the tenth of a second
 * is not what anyone is looking for.
 *
 * The boundary rounds rather than truncating, so nothing falls through the gap
 * between the two branches: 9.999s would otherwise print as "10.0 ثانیه" from
 * the first and as "10 ثانیه" from the second, and one run would render two
 * different strings depending on which line looked at it.
 */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} میلی‌ثانیه`;
  const seconds = ms / 1000;
  if (seconds < 9.95) return `${seconds.toFixed(1)} ثانیه`;
  return `${Math.round(seconds)} ثانیه`;
}

export default function SystemHealthPage() {
  const { toast } = useToast();
  const [report, setReport] = useState<SiteHealthReport | null>(null);
  const [loading, setLoading] = useState(true);
  // The recorded history. Loaded on mount, not on every check: a manual run
  // appends to it rather than refetching, so the list does not flicker.
  const [history, setHistory] = useState<SiteHealthRun[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [recoveryPaused, setRecoveryPaused] = useState(false);
  // Busy flag for the recovery-key email, so a double-click does not mint and
  // send two keys.
  const [sendingKey, setSendingKey] = useState(false);
  // The info tab is a support tool, not a health signal, so it starts closed
  // rather than pushing the actual check results below the fold.
  const [showInfo, setShowInfo] = useState(false);
  const [resuming, setResuming] = useState(false);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      setHistory(await siteHealthApi.history(20));
    } catch {
      // The history is supplementary: the current reading above is what the
      // operator came for, and a failure here must not replace it with an
      // error.
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  /** Run the checks and keep the result.
   *
   *  This is the button, so it records: WordPress's Site Health screen runs on
   *  demand and keeps a page of what ran, and the GET-only version left no
   *  trace — a disk that filled at 3am was invisible the next morning because
   *  the evidence had vanished with the request. */
  const runAndRecord = useCallback(async () => {
    setLoading(true);
    try {
      const recorded = await siteHealthApi.runAndRecord();
      setReport(recorded);
      await loadHistory();
    } catch {
      toast({ title: "اجرای بررسی سلامت ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [loadHistory]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setReport(await siteHealthApi.run());
    } catch {
      toast({ title: "اجرای بررسی سلامت ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
    // Read separately: while the site is paused this endpoint serves the 503
    // page, so `run` above is exactly the call that will have failed.
    try {
      setRecoveryPaused((await siteHealthApi.recoveryMode()).paused);
    } catch {
      setRecoveryPaused(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
    void loadHistory();
  }, [load, loadHistory]);

  const handleOptimize = async () => {
    setOptimizing(true);
    try {
      const res = await siteHealthApi.optimizeDatabase();
      toast({
        title: res.status === "success" ? "بهینه‌سازی انجام شد" : "بهینه‌سازی ناموفق بود",
        description: res.message,
        variant: res.status === "success" ? "default" : "destructive",
      });
    } catch {
      toast({ title: "بهینه‌سازی ناموفق بود", variant: "destructive" });
    } finally {
      setOptimizing(false);
    }
  };

  const handleResume = async () => {
    setResuming(true);
    try {
      const res = await siteHealthApi.resumeRecoveryMode();
      setRecoveryPaused(res.paused);
      toast({
        title: res.paused ? "سایت همچنان متوقف است" : "سایت ادامه یافت",
        variant: res.paused ? "destructive" : "default",
      });
      if (!res.paused) void load();
    } catch {
      toast({ title: "ادامه دادن سایت ناموفق بود", variant: "destructive" });
    } finally {
      setResuming(false);
    }
  };

  const handleSendRecoveryKey = async () => {
    setSendingKey(true);
    try {
      const res = await siteHealthApi.sendRecoveryInvitation();
      if (res.sent) {
        toast({
          title: "کلید بازیابی ارسال شد",
          description: `به ${res.recipient ?? "ایمیل مدیر"} — کوتاه‌عمر است و پس از رفع مشکل منقضی می‌شود.`,
        });
      } else {
        toast({
          title: "ارسال کلید بازیابی ناموفق بود",
          description: res.reason ?? undefined,
          variant: "destructive",
        });
      }
    } catch {
      toast({ title: "ارسال کلید بازیابی ناموفق بود", variant: "destructive" });
    } finally {
      setSendingKey(false);
    }
  };

  const overall = report ? statusMeta[report.overall_status] : null;
  const OverallIcon = overall?.icon ?? Activity;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold">سلامت سامانه</h1>
          <p className="text-xs text-muted-foreground">
            بررسی اتصال دیتابیس، کش، فضای رسانه و وضعیت مهاجرت‌ها
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {/* Records the run — see runAndRecord. */}
          <Button variant="outline" size="sm" onClick={() => void runAndRecord()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> بررسی و ثبت
          </Button>
          {/* Read-only: the same checks with no record, for a glance that must
              not add a row to the history. */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void load()}
            disabled={loading}
            title="اجرای بررسی بدون ثبت در تاریخچه"
          >
            فقط نمایش
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowHistory((v) => !v)}
            aria-expanded={showHistory}
          >
            <History className="h-4 w-4" />
            تاریخچه ({toPersianDigits(String(history.length))})
          </Button>
          <Button size="sm" onClick={() => void handleOptimize()} disabled={optimizing}>
            <Wrench className="h-4 w-4" />
            {optimizing ? "در حال بهینه‌سازی…" : "بهینه‌سازی دیتابیس"}
          </Button>
          <Button
            variant={showInfo ? "default" : "outline"}
            size="sm"
            onClick={() => setShowInfo((v) => !v)}
            aria-expanded={showInfo}
          >
            <Info className="h-4 w-4" />
            اطلاعات سیستم
          </Button>
        </div>
      </div>

      {showInfo && <SiteHealthInfoTab />}

      {/* Run history. WordPress keeps a page of what Site Health found; without
          it this screen could only answer "is it broken right now", so a disk
          that filled overnight and a store that had already recovered looked
          identical. */}
      {showHistory && (
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <History className="h-5 w-5 text-primary" />
            <h3 className="text-sm font-bold">تاریخچه‌ی بررسی‌ها</h3>
            <span className="text-xs text-muted-foreground">
              روزانه ساعت ۶:۱۲ اجرا می‌شود و هر بار «بررسی و ثبت» هم یک ردیف می‌سازد.
            </span>
          </div>
          {historyLoading ? (
            <p className="text-sm text-muted-foreground">در حال خواندن تاریخچه...</p>
          ) : history.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              هنوز اجرایی ثبت نشده. دکمه‌ی «بررسی و ثبت» اولین ردیف را می‌سازد.
            </p>
          ) : (
            <div className="space-y-2">
              {history.map((run) => (
                <details
                  key={run.id}
                  className="rounded-lg border border-border bg-muted/30 px-3 py-2"
                >
                  <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-xs">
                    <Badge
                      variant="outline"
                      className={
                        run.worst_status === "critical"
                          ? "border-destructive/50 text-destructive"
                          : run.worst_status === "warning"
                            ? "border-amber-500/50 text-amber-700 dark:text-amber-400"
                            : "border-emerald-500/50 text-emerald-700 dark:text-emerald-400"
                      }
                    >
                      {run.worst_status === "critical"
                        ? "بحرانی"
                        : run.worst_status === "warning"
                          ? "هشدار"
                          : run.worst_status === "good"
                            ? "سالم"
                            : "نامشخص"}
                    </Badge>
                    <span className="font-medium">
                      {run.started_at
                        ? formatJalaliDateTime(run.started_at)
                        : "زمان نامشخص"}
                    </span>
                    <span className="text-muted-foreground">
                      {run.trigger === "scheduled" ? "خودکار" : "دستی"}
                    </span>
                    <span className="text-muted-foreground">
                      {toPersianDigits(String(run.checks.length))} بررسی
                    </span>
                    {/* How long the run took. Without it a check that passes
                        after 12 seconds looks identical to one that returns in
                        milliseconds, which is the difference between "the disk
                        is slow" and "the site is fine". */}
                    {run.duration_ms !== null && (
                      <span className="text-muted-foreground">
                        {toPersianDigits(formatDuration(run.duration_ms))}
                      </span>
                    )}
                    {/* The question a support thread opens with is "what broke?",
                        not "was it critical?". Naming the checks in the collapsed
                        row answers it without expanding every entry. */}
                    {run.failing_checks.length > 0 && (
                      <span className="text-destructive">
                        {toPersianDigits(String(run.failing_checks.length))} بررسی
                        ناموفق: {run.failing_checks.join("، ")}
                      </span>
                    )}
                    {run.error && (
                      <span className="text-destructive">اجرا ناموفق بود</span>
                    )}
                  </summary>
                  <ul className="mt-2 space-y-0.5 text-[11px]">
                    {run.error ? (
                      <li className="text-destructive">{run.error}</li>
                    ) : (
                      run.checks.map((c, i) => (
                        <li key={`${run.id}-${i}`} className="flex gap-2">
                          <span
                            className={
                              c.status === "good"
                                ? "text-emerald-600"
                                : c.status === "warning"
                                  ? "text-amber-600"
                                  : "text-destructive"
                            }
                          >
                            {c.status}
                          </span>
                          <span className="text-muted-foreground">{c.name}</span>
                        </li>
                      ))
                    )}
                  </ul>
                </details>
              ))}
            </div>
          )}
        </Card>
      )}

      {recoveryPaused && (
        <Card className="border-destructive/50 bg-destructive/5 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              <div>
                <p className="text-sm font-bold text-foreground">
                  سایت در حالت بازیابی متوقف است
                </p>
                <p className="text-xs text-muted-foreground">
                  یک خطای مدیریت‌نشده رخ داده و سایت به‌جای صفحهٔ ۵۰۳ متوقف شده است. تا
                  زمانی که ادامه ندهید، مشتریان چیزی نمی‌بینند.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* Email a one-time recovery key. The whole point of recovery
                  mode is that the panel may be the broken thing — a key in
                  the operator's mailbox is a way back that does not depend on
                  this page rendering. */}
              <Button
                size="sm"
                variant="outline"
                onClick={() => void handleSendRecoveryKey()}
                disabled={sendingKey}
              >
                {sendingKey ? "در حال ارسال…" : "ارسال کلید بازیابی به ایمیل مدیر"}
              </Button>
              <Button
                size="sm"
                onClick={() => void handleResume()}
                disabled={resuming}
              >
                {resuming ? "در حال ادامه…" : "ادامهٔ سایت"}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {loading && !report ? (
        <Card className="p-10 text-center text-xs text-muted-foreground">
          در حال اجرای بررسی‌ها…
        </Card>
      ) : report ? (
        <>
          <Card className="flex items-center gap-4 p-5">
            <OverallIcon className={`h-9 w-9 ${overall?.className ?? ""}`} />
            <div className="flex-1">
              <div className="text-sm font-semibold">
                وضعیت کلی: {overall?.label ?? report.overall_status}
              </div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                {report.summary.good} سالم · {report.summary.warning} هشدار ·{" "}
                {report.summary.critical} بحرانی — آخرین بررسی:{" "}
                {new Date(report.checked_at).toLocaleString("fa-IR")}
              </div>
            </div>
          </Card>

          <div className="grid gap-3 md:grid-cols-2">
            {report.checks.map((check) => {
              const meta = statusMeta[check.status];
              const Icon = checkIcon(check.name);
              const StatusIcon = meta.icon;
              return (
                <Card key={check.name} className="space-y-2 p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs font-medium">{check.name}</span>
                    </div>
                    <Badge variant="outline" className={`gap-1 text-[10px] ${meta.badge}`}>
                      <StatusIcon className="h-3 w-3" />
                      {meta.label}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground" dir="auto">
                    {check.description}
                  </div>
                  <div className="rounded-md bg-muted/50 px-2.5 py-1.5 text-[11px]" dir="ltr">
                    {check.value}
                  </div>
                  {Array.isArray(check.details) && check.details.length > 0 && (
                    <details className="text-[11px]">
                      <summary className="cursor-pointer text-muted-foreground">
                        جزئیات جداول
                      </summary>
                      <ul className="mt-1.5 space-y-0.5">
                        {(check.details as Array<{ table: string; rows: number }>).map((t) => (
                          <li key={t.table} className="flex justify-between" dir="ltr">
                            <span>{t.table}</span>
                            <span className="text-muted-foreground">
                              {t.rows.toLocaleString()}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </Card>
              );
            })}
          </div>
        </>
      ) : (
        <Card className="p-10 text-center text-xs text-muted-foreground">
          گزارشی دریافت نشد.
        </Card>
      )}
    </div>
  );
}
