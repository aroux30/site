"use client";

import { useCallback, useEffect, useState } from "react";
import { Copy, Info, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import {
  siteHealthApi,
  type SiteHealthInfo,
  type SiteHealthInfoSection,
} from "@/lib/api/wp-parity";
import { toPersianDigits } from "@/lib/utils";

/**
 * Site Health → Info (wave 6 #84).
 *
 * WordPress's info tab is what an operator copies into a support thread:
 * versions, database, disk, and the handful of settings that change behaviour.
 * We had the checks but not this, so a support question needed a shell.
 *
 * The copy button exists because the whole point is to paste it. It copies the
 * raw JSON rather than a rendered table, so what lands in the ticket is what
 * the server actually reported.
 */

const SECTION_LABELS: Record<string, string> = {
  server: "سرور",
  database: "پایگاه داده",
  storage: "فضای ذخیره‌سازی",
  settings: "تنظیمات برنامه",
  modules: "ماژول‌ها",
  migrations: "مهاجرت‌های پایگاه داده",
  options: "تنظیمات سایت",
  scheduled_jobs: "کارهای زمان‌بندی‌شده",
};

const FIELD_LABELS: Record<string, string> = {
  os: "سیستم‌عامل",
  python: "نسخهٔ پایتون",
  architecture: "معماری",
  cpu_count: "تعداد هستهٔ CPU",
  dialect: "دیالکت",
  driver_version: "نسخهٔ درایور",
  server_version: "نسخهٔ سرور",
  table_count: "تعداد جدول‌ها",
  upload_dir: "مسیر آپلود",
  total_gb: "حجم کل (GB)",
  free_gb: "حجم آزاد (GB)",
  app_name: "نام برنامه",
  environment: "محیط اجرا",
  debug: "حالت اشکال‌زدایی",
  timezone: "منطقهٔ زمانی",
  default_currency: "واحد پول",
  api_docs_enabled: "مستندات API فعال",
  enabled_count: "تعداد ماژول‌های فعال",
  registered: "روش ثبت ماژول‌ها",
  // The three rows below are what a support thread asks for first: which
  // revision is stamped, how many options load on every request, and what the
  // beat is configured to fire.
  current_revision: "مرحلهٔ فعلی (revision)",
  in_consistent_state: "در وضعیت ناسازگار (مهاجرت نیمه‌کاره)",
  autoloaded_count: "تنظیمات autoload",
  total_count: "کل تنظیمات",
  count: "تعداد",
  error: "خطا",
};

function labelFor(section: string, field: string): string {
  return FIELD_LABELS[field] ?? field;
}

function formatValue(value: SiteHealthInfoSection[string]): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "بله" : "خیر";
  if (typeof value === "number") return toPersianDigits(String(value));
  if (Array.isArray(value)) {
    // String(value) on a list of objects renders "[object Object]". The
    // scheduled-jobs row is the only list in this payload, and it is the one
    // a reader most wants to read.
    return value
      .map((entry) =>
        entry && typeof entry === "object"
          ? Object.entries(entry as Record<string, unknown>)
              .map(([k, v]) => `${FIELD_LABELS[k] ?? k}: ${String(v)}`)
              .join(" · ")
          : String(entry),
      )
      .join(String.fromCharCode(10));
  }
  return String(value);
}

export function SiteHealthInfoTab() {
  const { toast } = useToast();
  const [info, setInfo] = useState<SiteHealthInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setInfo(await siteHealthApi.info());
    } catch (e) {
      // An empty table would read as "there is nothing to report", which is a
      // different claim from "we could not read it".
      setError(e instanceof Error ? e.message : "خطا در دریافت اطلاعات");
      setInfo(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const copyAll = async () => {
    if (!info) return;
    const text = JSON.stringify(info, null, 2);
    try {
      await navigator.clipboard.writeText(text);
      toast({ title: "اطلاعات کپی شد.", description: "برای ارسال در تیکت پشتیبانی استفاده کنید." });
    } catch {
      // clipboard is unavailable over plain HTTP and in some browsers; a
      // selectable fallback beats a button that silently does nothing.
      toast({
        title: "کپی خودکار ممکن نشد",
        description: "متن را دستی انتخاب و کپی کنید.",
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return (
      <Card className="p-8 text-center text-sm text-muted-foreground">
        در حال خواندن اطلاعات سیستم...
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive/40 bg-destructive/5 p-4">
        <p className="text-sm font-medium text-destructive">
          اطلاعات سیستم خوانده نشد: {error}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          این به معنی نبودِ اطلاعات نیست — یعنی بررسی انجام نشده است.
        </p>
        <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => void load()}>
          <RefreshCw className="h-4 w-4" />
          تلاش دوباره
        </Button>
      </Card>
    );
  }

  if (!info) return null;

  const sectionNames = Object.keys(info.sections);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Info className="h-4 w-4" />
          این اطلاعات برای تشخیص مشکل است. هیچ رمز یا کلید محرمانه‌ای در آن نیست.
        </p>
        <Button type="button" variant="outline" size="sm" onClick={() => void copyAll()}>
          <Copy className="h-4 w-4" />
          کپی کل اطلاعات
        </Button>
      </div>

      {sectionNames.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          هیچ بخشی برای نمایش وجود ندارد.
        </Card>
      ) : (
        sectionNames.map((name) => {
          // noUncheckedIndexedAccess: a Record lookup is `| undefined`, and a
          // section that vanished between render and read should render nothing
          // rather than crash the whole health page.
          const section = info.sections[name];
          if (!section) return null;
          return (
            <Card key={name} className="overflow-hidden">
              <h2 className="border-b border-border bg-muted/40 px-4 py-2 text-sm font-semibold">
                {SECTION_LABELS[name] ?? name}
              </h2>
              <dl className="divide-y divide-border">
                {Object.entries(section).map(([field, value]) => (
                  <div
                    key={field}
                    className="grid grid-cols-1 gap-1 px-4 py-2 text-sm sm:grid-cols-[minmax(0,14rem)_1fr]"
                  >
                    <dt className="text-muted-foreground">{labelFor(name, field)}</dt>
                    {/* whitespace-pre-line: a list value (the scheduled jobs)
                        is joined with newlines, and without it all 25 jobs
                        render on one unreadable line. */}
                    <dd className="break-all whitespace-pre-line font-mono text-xs sm:text-sm">
                      {formatValue(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </Card>
          );
        })
      )}
    </div>
  );
}
