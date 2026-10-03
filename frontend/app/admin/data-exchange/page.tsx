"use client";

import React, { useRef, useState } from "react";
import Link from "next/link";
import { Download, FileUp, RefreshCw, Rss, Upload } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { toPersianDigits } from "@/lib/utils";
import {
  dataExchangeApi,
  saveBlob,
  type DataExchangeEntity,
  type FeedPreview,
  type ImportJob,
} from "@/lib/api/data-exchange";

const DATA_EXCHANGE_QUERY_KEY = "admin-data-exchange" as const;

const STATUS_LABELS: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  mapping: { label: "نگاشت ستون‌ها", variant: "secondary" },
  validating: { label: "در حال اعتبارسنجی", variant: "secondary" },
  ready: { label: "آماده اجرا", variant: "default" },
  importing: { label: "در حال ورود", variant: "secondary" },
  completed: { label: "تکمیل‌شده", variant: "default" },
  failed: { label: "ناموفق", variant: "destructive" },
};

export default function DataExchangeImportPage() {
  const { toast } = useToast();
  const [entityType, setEntityType] = useState("product");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Feed import, kept apart from the job pipeline above: a feed is a document
  // rather than a table, so it has no job, no column mapping and no row-level
  // error report — and its entries are posts, which the CSV path cannot express.
  const [feedBusy, setFeedBusy] = useState(false);
  const [feedPreview, setFeedPreview] = useState<FeedPreview | null>(null);
  const feedFileRef = useRef<HTMLInputElement>(null);
  const feedFileRefState = useRef<File | null>(null);

  async function previewFeed(file: File) {
    setFeedBusy(true);
    setFeedPreview(null);
    try {
      const preview = await dataExchangeApi.previewFeed(file);
      feedFileRefState.current = file;
      setFeedPreview(preview);
    } catch {
      toast({
        title: "خواندن فید ناموفق بود",
        description: "فایل باید یک فید RSS 2.0 یا Atom معتبر باشد.",
        variant: "destructive",
      });
    } finally {
      setFeedBusy(false);
    }
  }

  async function runFeedImport() {
    const file = feedFileRefState.current;
    if (!file) return;
    setFeedBusy(true);
    try {
      const stats = await dataExchangeApi.importFeed(file);
      toast({
        title: "ایمپورت فید انجام شد",
        description: `${toPersianDigits(String(stats.posts))} نوشته پیش‌نویس ساخته شد، ${toPersianDigits(String(stats.skipped))} تکراری رد شد.`,
      });
      setFeedPreview(null);
      feedFileRefState.current = null;
      void load();
    } catch {
      toast({ title: "ایمپورت فید ناموفق بود", variant: "destructive" });
    } finally {
      setFeedBusy(false);
    }
  }

  // The entity list and the recent import jobs always come from the same
  // fetch, so the entity labels in the jobs table can never disagree with the
  // picker above it.
  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [DATA_EXCHANGE_QUERY_KEY],
    queryFn: async () => {
      const [entities, list] = await Promise.all([
        dataExchangeApi.entities(),
        dataExchangeApi.listImportJobs({ page_size: 50 }),
      ]);
      return { entities, jobs: list.items };
    },
    fallbackError: "دریافت اطلاعات ناموفق بود",
  });
  const entities: DataExchangeEntity[] = data?.entities ?? [];
  const jobs: ImportJob[] = data?.jobs ?? [];

  const runMutation = useAdminMutation();

  const doUpload = async (file: File) => {
    setUploading(true);
    const result = await runMutation(
      () => dataExchangeApi.createImportJob(entityType, file),
      { fallbackError: "بارگذاری فایل ناموفق بود" },
    );
    if (result.ok) {
      toast({ title: "فایل بارگذاری شد", description: `${result.data.stats?.total ?? 0} ردیف شناسایی شد` });
      window.location.href = `/admin/data-exchange/import/${result.data.id}`;
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const columns: DataTableColumn<ImportJob>[] = [
    {
      key: "file",
      header: "فایل",
      render: (j) => (
        <a className="text-primary hover:underline" href={`/admin/data-exchange/import/${j.id}`}>
          {j.original_filename}
        </a>
      ),
    },
    { key: "entity", header: "موجودیت", render: (j) => entities.find((e) => e.entity_type === j.entity_type)?.label ?? j.entity_type },
    {
      key: "status",
      header: "وضعیت",
      render: (j) => {
        const s = STATUS_LABELS[j.status] ?? { label: j.status, variant: "outline" as const };
        return <Badge variant={s.variant}>{s.label}</Badge>;
      },
    },
    {
      key: "stats",
      header: "کل/معتبر/واردشده",
      hideOnMobile: true,
      render: (j) =>
        j.stats ? `${j.stats.total} / ${j.stats.valid} / ${j.stats.imported}` : "—",
    },
    {
      key: "created",
      header: "ایجاد",
      hideOnMobile: true,
      render: (j) => (j.created_at ? new Date(j.created_at).toLocaleString("fa-IR") : "—"),
    },
    {
      key: "errors",
      header: "گزارش خطا",
      render: (j) =>
        j.has_error_report ? (
          <Button
            size="sm"
            variant="outline"
            onClick={async (e) => {
              e.stopPropagation();
              const blob = await dataExchangeApi.downloadErrorReport(j.id);
              saveBlob(blob, `import-errors-${j.id.slice(0, 8)}.csv`);
            }}
          >
            <Download className="h-3.5 w-3.5 ms-1" />
            دانلود
          </Button>
        ) : (
          "—"
        ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <FileUp className="h-5 w-5 text-primary" />
            ورود داده (Import)
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            بارگذاری CSV یا XLSX، نگاشت ستون‌ها، اعتبارسنجی خشک (dry-run) و اجرای import با گزارش خطای ردیفی
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href="/admin/data-exchange/export">
            <Download className="h-4 w-4 ms-1" />
            خروجی داده (Export)
          </Link>
        </Button>
      </div>

      <Card className="p-6 space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Upload className="h-5 w-5 text-primary" />
          شروع import جدید
        </h3>
        <div className="flex flex-wrap items-center gap-3">
          <select
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
          >
            {entities.map((e) => (
              <option key={e.entity_type} value={e.entity_type}>
                {e.label}
              </option>
            ))}
          </select>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.txt,.tsv,.xlsx,.xlsm"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void doUpload(f);
            }}
          />
          <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
            <Upload className="h-4 w-4 ms-1" />
            {uploading ? "در حال بارگذاری..." : "انتخاب فایل و شروع"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </Card>

      <Card className="p-6 space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Rss className="h-5 w-5 text-primary" />
          ایمپورت از فید RSS یا Atom
        </h3>
        <p className="text-sm text-muted-foreground">
          نشانی فید را نریزید — فایل XML فید را بارگذاری کنید. ابتدا پیش‌نمایش
          می‌گیرید تا ببینید چند نوشته و چه دسته‌هایی در آن هست، و بعد از دکمهٔ
          ایمپورت استفاده کنید.
        </p>
        <p className="text-xs text-muted-foreground">
          هر نوشته به‌صورت <strong>پیش‌نویس</strong> وارد می‌شود. انتشار یک
          تصمیم جداگانه برای هر نوشته است.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={feedFileRef}
            type="file"
            accept=".xml,.rss,.atom"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void previewFeed(f);
            }}
          />
          <Button
            variant="outline"
            onClick={() => feedFileRef.current?.click()}
            disabled={feedBusy}
          >
            <Upload className="h-4 w-4 ms-1" />
            {feedBusy ? "در حال خواندن..." : "انتخاب فایل فید"}
          </Button>
        </div>

        {feedPreview && (
          <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-4">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Badge variant="outline">
                {feedPreview.format === "atom" ? "Atom" : "RSS"}
              </Badge>
              <span>
                {toPersianDigits(String(feedPreview.counts.posts))} نوشته
              </span>
              <span className="text-muted-foreground">
                {toPersianDigits(String(feedPreview.counts.categories))} دسته
              </span>
              <span className="text-muted-foreground">
                {toPersianDigits(String(feedPreview.counts.tags))} برچسب
              </span>
            </div>
            {feedPreview.sample.length > 0 && (
              <ul className="space-y-1 text-xs text-muted-foreground">
                {feedPreview.sample.map((p, i) => (
                  <li key={`${p.title}-${i}`} className="truncate">
                    • {p.title}
                    {p.category_slug ? ` — ${p.category_slug}` : ""}
                  </li>
                ))}
              </ul>
            )}
            <Button onClick={() => void runFeedImport()} disabled={feedBusy}>
              <FileUp className="h-4 w-4 ms-1" />
              {feedBusy ? "در حال ایمپورت..." : "ایمپورت همهٔ نوشته‌ها"}
            </Button>
          </div>
        )}
      </Card>

      <DataTable
        columns={columns}
        rows={jobs}
        rowKey={(j) => j.id}
        loading={loading}
        error={error}
        emptyMessage="هنوز هیچ import انجام نشده است"
        emptyDescription="یک فایل CSV یا XLSX بارگذاری کنید تا اولین job ساخته شود"
        onRowClick={(j) => (window.location.href = `/admin/data-exchange/import/${j.id}`)}
      />
    </div>
  );
}
