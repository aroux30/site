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
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { SiteHealthInfoTab } from "@/components/admin/site-health-info-tab";
import { siteHealthApi, type SiteHealthReport } from "@/lib/api/wp-parity";

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

export default function SystemHealthPage() {
  const { toast } = useToast();
  const [report, setReport] = useState<SiteHealthReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [optimizing, setOptimizing] = useState(false);
  const [recoveryPaused, setRecoveryPaused] = useState(false);
  // The info tab is a support tool, not a health signal, so it starts closed
  // rather than pushing the actual check results below the fold.
  const [showInfo, setShowInfo] = useState(false);
  const [resuming, setResuming] = useState(false);

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
  }, [load]);

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
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> بررسی مجدد
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
            <Button
              size="sm"
              onClick={() => void handleResume()}
              disabled={resuming}
            >
              {resuming ? "در حال ادامه…" : "ادامهٔ سایت"}
            </Button>
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
