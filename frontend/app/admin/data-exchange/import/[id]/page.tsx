"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, CheckCircle2, Download, Play, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { apiErrorMessage } from "@/lib/api/error-message";
import { useAdminQuery } from "@/lib/api/admin-query";
import {
  dataExchangeApi,
  saveBlob,
  type DataExchangeEntity,
  type ImportJob,
} from "@/lib/api/data-exchange";

const STATUS_LABELS: Record<string, string> = {
  draft: "پیش‌نویس",
  mapping: "نگاشت ستون‌ها",
  validating: "در حال اعتبارسنجی",
  ready: "آماده اجرا",
  importing: "در حال ورود",
  completed: "تکمیل‌شده",
  failed: "ناموفق",
};

export default function ImportWizardPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const { toast } = useToast();

  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const {
    data: detail,
    loading,
    error,
    reload: load,
  } = useAdminQuery<{ job: ImportJob; entity: DataExchangeEntity | null }>({
    queryKey: ["admin", "data-exchange", "import", jobId],
    enabled: Boolean(jobId),
    queryFn: async () => {
      const j = await dataExchangeApi.getImportJob(jobId);
      const ents = await dataExchangeApi.entities();
      const ent = ents.find((e) => e.entity_type === j.entity_type) ?? null;
      if (j.column_mapping) {
        setMapping(j.column_mapping);
      } else {
        const auto = await dataExchangeApi.autoMapping(jobId).catch(() => ({}));
        setMapping(auto ?? {});
      }
      return { job: j, entity: ent };
    },
    fallbackError: "دریافت job ناموفق بود",
  });
  const job = detail?.job ?? null;
  const entity = detail?.entity ?? null;

  const fail = (err: unknown, fallback: string) => {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    toast({ title: "خطا", description: detail ?? fallback, variant: "destructive" });
  };

  const saveMapping = async () => {
    setBusy("mapping");
    try {
      await dataExchangeApi.setMapping(jobId, mapping);
      await load();
      toast({ title: "نگاشت ذخیره شد" });
    } catch (err) {
      fail(err, "ذخیره نگاشت ناموفق بود");
    } finally {
      setBusy(null);
    }
  };

  const validate = async () => {
    setBusy("validate");
    try {
      const j = await dataExchangeApi.validateImportJob(jobId);
      await load();
      if (j.stats?.invalid) {
        toast({
          title: "اعتبارسنجی کامل شد",
          description: `${j.stats.invalid} ردیف نامعتبر — گزارش خطا را دانلود کنید`,
          variant: "destructive",
        });
      } else {
        toast({ title: "همه ردیف‌ها معتبرند", description: "job آماده اجراست" });
      }
    } catch (err) {
      fail(err, "اعتبارسنجی ناموفق بود");
    } finally {
      setBusy(null);
    }
  };

  const execute = async () => {
    setBusy("execute");
    try {
      const j = await dataExchangeApi.executeImportJob(
        jobId,
        crypto.randomUUID ? crypto.randomUUID() : undefined,
      );
      await load();
      toast({
        title: "import کامل شد",
        description: `${j.stats?.imported ?? 0} ردیف وارد شد، ${j.stats?.skipped ?? 0} رد شد`,
      });
    } catch (err) {
      fail(err, "اجرای import ناموفق بود");
    } finally {
      setBusy(null);
    }
  };

  if (error) return <div className="p-6 text-destructive" dir="rtl">{error}</div>;
  if (!job || !entity) return <div className="p-6 text-muted-foreground" dir="rtl">در حال بارگذاری...</div>;

  const stats = job.stats;
  const requiredKeys = entity.columns.filter((c) => c.required).map((c) => c.key);
  const mappedTargets = new Set(Object.values(mapping).filter(Boolean));
  const missingRequired = requiredKeys.filter((k) => !mappedTargets.has(k));
  const canValidate = missingRequired.length === 0 && ["mapping", "ready"].includes(job.status) || (job.status === "draft" && missingRequired.length === 0);
  const canExecute = ["ready", "mapping", "failed"].includes(job.status);

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/admin/data-exchange">
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h2 className="text-xl font-bold">import: {job.original_filename}</h2>
          <p className="text-sm text-muted-foreground">
            {entity.label} — وضعیت: {STATUS_LABELS[job.status] ?? job.status}
          </p>
        </div>
      </div>

      {/* Step 1: stats summary */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {[
            ["کل ردیف‌ها", stats.total],
            ["معتبر", stats.valid],
            ["نامعتبر", stats.invalid],
            ["واردشده", stats.imported],
            ["ردشده", stats.skipped],
          ].map(([label, value]) => (
            <Card key={label} className="p-4 text-center">
              <p className="text-2xl font-bold">{value}</p>
              <p className="text-xs text-muted-foreground">{label}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Step 2: mapping */}
      {["draft", "mapping", "ready"].includes(job.status) && (
        <Card className="p-6 space-y-4">
          <h3 className="text-lg font-semibold">نگاشت ستون‌ها</h3>
          <p className="text-sm text-muted-foreground">
            ستون‌های فایل را به فیلدهای موجودیت وصل کنید. نگاشت اولیه به‌صورت خودکار حدس زده شده است.
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {(job.detected_headers ?? []).map((header) => (
              <div key={header} className="flex items-center gap-2">
                <span className="w-40 truncate text-sm font-medium" title={header}>
                  {header || "(ستون بدون نام)"}
                </span>
                <select
                  className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={mapping[header] ?? ""}
                  onChange={(e) => setMapping((m) => ({ ...m, [header]: e.target.value }))}
                >
                  <option value="">— نادیده گرفتن —</option>
                  {entity.columns.map((c) => (
                    <option key={c.key} value={c.key}>
                      {c.label}
                      {c.required ? " *" : ""}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          {missingRequired.length > 0 && (
            <p className="text-sm text-destructive">
              ستون‌های الزامی نگاشت‌نشده: {missingRequired.join("، ")}
            </p>
          )}
          <div className="flex gap-2">
            <Button onClick={() => void saveMapping()} disabled={busy !== null || missingRequired.length > 0}>
              <CheckCircle2 className="h-4 w-4 ms-1" />
              {busy === "mapping" ? "در حال ذخیره..." : "ذخیره نگاشت"}
            </Button>
            <Button variant="outline" onClick={() => void validate()} disabled={!canValidate || busy !== null}>
              <ShieldCheck className="h-4 w-4 ms-1" />
              {busy === "validate" ? "در حال اعتبارسنجی..." : "اعتبارسنجی (dry-run)"}
            </Button>
            <Button
              variant="default"
              onClick={() => void execute()}
              disabled={!canExecute || busy !== null}
            >
              <Play className="h-4 w-4 ms-1" />
              {busy === "execute" ? "در حال اجرا..." : "اجرای import"}
            </Button>
          </div>
        </Card>
      )}

      {/* Step 3: result */}
      {["completed", "failed"].includes(job.status) && stats && (
        <Card className="p-6 space-y-3">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            نتیجه
            <Badge variant={job.status === "completed" ? "default" : "destructive"}>
              {STATUS_LABELS[job.status]}
            </Badge>
          </h3>
          <p className="text-sm">
            {stats.imported} ردیف وارد شد، {stats.skipped} رد شد، {stats.invalid} نامعتبر بود.
          </p>
          {job.has_error_report && (
            <Button
              variant="outline"
              onClick={async () => {
                const blob = await dataExchangeApi.downloadErrorReport(job.id);
                saveBlob(blob, `import-errors-${job.id.slice(0, 8)}.csv`);
              }}
            >
              <Download className="h-4 w-4 ms-1" />
              دانلود گزارش خطا (CSV)
            </Button>
          )}
        </Card>
      )}
    </div>
  );
}
