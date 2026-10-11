"use client";

/**
 * SEO Status & Tools (Rank Math's Status & Tools page).
 *
 * Three panels: the status checks (pass/warn/fail with a fix per row), the
 * incomplete-data read-out (counts + sample ids; nothing is written from
 * here), and settings export/import as JSON so a setup can move between
 * environments.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Download,
  Loader2,
  Upload,
  XCircle,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import {
  exportSeoSettings,
  fetchIncompleteData,
  fetchSeoStatus,
  importSeoSettings,
  type IncompleteData,
  type SeoStatusResult,
} from "@/lib/api/seo";
import { toPersianDigits } from "@/lib/utils";

const STATUS_ICON = {
  pass: <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />,
  warn: <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />,
  fail: <XCircle className="h-4 w-4 shrink-0 text-red-600" />,
} as const;

export default function SeoStatusPage() {
  const { toast } = useToast();
  const [status, setStatus] = useState<SeoStatusResult | null>(null);
  const [incomplete, setIncomplete] = useState<IncompleteData | null>(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const importRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, inc] = await Promise.all([fetchSeoStatus(), fetchIncompleteData()]);
      setStatus(s);
      setIncomplete(inc);
    } catch {
      toast({ title: "خواندن وضعیت سئو ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const exportSettings = async () => {
    try {
      const settings = await exportSeoSettings();
      const blob = new Blob([JSON.stringify(settings, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "seo-settings.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast({ title: "خروجی تنظیمات ناموفق بود", variant: "destructive" });
    }
  };

  const importSettings = async (file: File) => {
    setImporting(true);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as Record<string, string>;
      const result = await importSeoSettings(parsed);
      toast({
        title: `${toPersianDigits(String(result.written))} از ${toPersianDigits(String(result.total))} تنظیم ذخیره شد`,
        description:
          result.errors.length > 0
            ? `خطاها: ${result.errors.map((e) => e.key).join("، ")}`
            : undefined,
        variant: result.errors.length > 0 ? "destructive" : undefined,
      });
      await load();
    } catch {
      toast({ title: "ایمپورت ناموفق بود — فایل JSON معتبر است؟", variant: "destructive" });
    } finally {
      setImporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <ClipboardCheck className="h-5 w-5 text-primary" />
            وضعیت و ابزارهای سئو
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            بررسی سلامت تنظیمات، داده‌های ناقص، و پشتیبان‌گیری تنظیمات
          </p>
        </div>
        {status && (
          <div className="flex items-center gap-3 text-xs">
            <span className="text-emerald-600">
              {toPersianDigits(String(status.pass_count))} سالم
            </span>
            <span className="text-amber-600">
              {toPersianDigits(String(status.warn_count))} هشدار
            </span>
            <span className="text-red-600">
              {toPersianDigits(String(status.fail_count))} خطا
            </span>
          </div>
        )}
      </div>

      <Card className="p-6">
        <h2 className="mb-4 text-base font-bold">بررسی‌ها</h2>
        <div className="space-y-3">
          {(status?.checks ?? []).map((check) => (
            <div key={check.key} className="flex items-start gap-3 rounded-lg border p-3">
              {STATUS_ICON[check.status]}
              <div className="min-w-0">
                <div className="text-sm font-medium">{check.label}</div>
                <div className="text-xs text-muted-foreground">{check.detail}</div>
                {check.fix && check.status !== "pass" && (
                  <div className="mt-1 text-[11px] text-primary">راه‌حل: {check.fix}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="mb-4 text-base font-bold">دادهٔ ناقص</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border p-4">
            <div className="text-xs text-muted-foreground">نوشته‌های بدون فراداده سئو</div>
            <div className="mt-1 text-2xl font-black tabular-nums">
              {toPersianDigits(String(incomplete?.blog_posts_without_seo_metadata ?? 0))}
            </div>
          </div>
          <div className="rounded-lg border p-4">
            <div className="text-xs text-muted-foreground">محصولات بدون عنوان سئو</div>
            <div className="mt-1 text-2xl font-black tabular-nums">
              {toPersianDigits(String(incomplete?.products_without_seo_title ?? 0))}
            </div>
          </div>
        </div>
        <p className="mt-3 text-[11px] text-muted-foreground">
          این ابزار فقط می‌خواند. برای پرکردن، از ویرایش گروهی نوشته‌ها یا پنل سئوی هر
          محصول استفاده کنید.
        </p>
      </Card>

      <Card className="p-6">
        <h2 className="mb-4 text-base font-bold">پشتیبان‌گیری تنظیمات</h2>
        <p className="mb-4 text-xs text-muted-foreground">
          همهٔ تنظیمات سئو (عنوان‌ها، تصویر، robots، ایندکس، مسیر) در یک فایل JSON.
          برای انتقال بین محیط‌ها یا بازگردانی پس از تغییرات.
        </p>
        <input
          ref={importRef}
          type="file"
          accept=".json,application/json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void importSettings(file);
            e.target.value = "";
          }}
        />
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void exportSettings()}>
            <Download className="h-4 w-4 ms-2" />
            خروجی JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => importRef.current?.click()}
            disabled={importing}
          >
            {importing ? (
              <Loader2 className="h-4 w-4 ms-2 animate-spin" />
            ) : (
              <Upload className="h-4 w-4 ms-2" />
            )}
            ایمپورت JSON
          </Button>
        </div>
      </Card>
    </div>
  );
}
