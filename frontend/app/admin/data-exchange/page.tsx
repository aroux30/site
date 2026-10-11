"use client";

import React, { useRef, useState } from "react";
import Link from "next/link";
import { Download, FileUp, Globe, RefreshCw, Rss, Upload } from "lucide-react";
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
  type WxrPreview,
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
  // Cards the "start import" card can route a document to. When it does, the
  // page scrolls there so the preview is visible instead of appearing below
  // the fold with only a toast to hint at it.
  const wxrCardRef = useRef<HTMLDivElement>(null);
  const feedCardRef = useRef<HTMLDivElement>(null);

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

  // WordPress WXR (XML) import — the export WordPress itself writes under
  // Tools → Export. Its own card rather than an RSS variant: a WXR file holds
  // posts, pages (with hierarchy), categories, tags AND comments, and the
  // preview shows each of those counts separately so "this file is empty"
  // is visible before the irreversible step.
  const [wxrBusy, setWxrBusy] = useState(false);
  const [wxrPreview, setWxrPreview] = useState<WxrPreview | null>(null);
  const wxrFileRef = useRef<HTMLInputElement>(null);
  const wxrFileRefState = useRef<File | null>(null);

  async function previewWxr(file: File) {
    setWxrBusy(true);
    setWxrPreview(null);
    try {
      const preview = await dataExchangeApi.previewWxr(file);
      wxrFileRefState.current = file;
      setWxrPreview(preview);
    } catch {
      toast({
        title: "خواندن فایل WXR ناموفق بود",
        description: "فایل باید خروجی XML وردپرس (ابزارها ← خروجی) باشد.",
        variant: "destructive",
      });
    } finally {
      setWxrBusy(false);
    }
  }

  async function runWxrImport() {
    const file = wxrFileRefState.current;
    if (!file) return;
    setWxrBusy(true);
    try {
      const stats = await dataExchangeApi.importWxr(file);
      toast({
        title: "ایمپورت WXR انجام شد",
        description:
          `${toPersianDigits(String(stats.posts))} نوشته، ` +
          `${toPersianDigits(String(stats.pages_created))} برگه و ` +
          `${toPersianDigits(String(stats.comments))} دیدگاه وارد شد؛ ` +
          `${toPersianDigits(String(stats.skipped))} تکراری رد شد.` +
          (stats.images_imported > 0
            ? ` ${toPersianDigits(String(stats.images_imported))} تصویر دانلود و به کتابخانهٔ رسانه منتقل شد.`
            : "") +
          (stats.images_failed > 0
            ? ` (${toPersianDigits(String(stats.images_failed))} تصویر دانلود نشد و نشانی اصلی حفظ شد.)`
            : "") +
          (stats.pages_skipped > 0
            ? ` (${toPersianDigits(String(stats.pages_skipped))} برگه رد شد — نامک رزروشدهٔ فروشگاه، مثل cart)`
            : ""),
      });
      setWxrPreview(null);
      wxrFileRefState.current = null;
      void load();
    } catch {
      toast({ title: "ایمپورت WXR ناموفق بود", variant: "destructive" });
    } finally {
      setWxrBusy(false);
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
    // XML is a document, not a table: an operator who selects the WordPress
    // export in this card must not be told "only CSV or XLSX". Route it by
    // content — WXR carries the `wp:` export namespace, anything else XML
    // gets the feed path (which validates its own root element).
    const lowerName = file.name.toLowerCase();
    if (
      lowerName.endsWith(".xml") ||
      lowerName.endsWith(".rss") ||
      lowerName.endsWith(".atom")
    ) {
      const head = await file.slice(0, 4096).text().catch(() => "");
      if (
        head.includes("wp:wxr_version") ||
        head.includes("wordpress.org/export")
      ) {
        await previewWxr(file);
        toast({
          title: "فایل خروجی وردپرس شناسایی شد",
          description: "پیش‌نمایش در کارت «ایمپورت از خروجی وردپرس» پایین صفحه آماده است.",
        });
        wxrCardRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      } else {
        await previewFeed(file);
        feedCardRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      if (fileRef.current) fileRef.current.value = "";
      return;
    }

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
            // XML/RSS/Atom included on purpose: an operator picking their
            // WordPress export in this card is routed to the WXR card by
            // doUpload instead of being told "only CSV or XLSX".
            accept=".csv,.txt,.tsv,.xlsx,.xlsm,.xml,.rss,.atom"
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

      <Card ref={feedCardRef} className="p-6 space-y-4">
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

      <Card ref={wxrCardRef} className="p-6 space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Globe className="h-5 w-5 text-primary" />
          ایمپورت از خروجی وردپرس (XML / WXR)
        </h3>
        <p className="text-sm text-muted-foreground">
          فایل خروجی وردپرس (ابزارها ← خروجی ← همهٔ محتوا) را بارگذاری کنید.
          نوشته‌ها، برگه‌ها با ساختار والد/فرزند، دسته‌ها، برچسب‌ها و دیدگاه‌ها
          با هم وارد می‌شوند. ابتدا پیش‌نمایش می‌گیرید تا ببینید فایل چه دارد،
          و بعد از دکمهٔ ایمپورت استفاده کنید.
        </p>
        <p className="text-xs text-muted-foreground">
          وضعیت هر آیتم از خود فایل خوانده می‌شود: پیش‌نویس پیش‌نویس می‌ماند و
          منتشرشده منتشر می‌شود. نوشته‌های تکراری (بر اساس نامک) رد می‌شوند.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={wxrFileRef}
            type="file"
            accept=".xml,text/xml,application/xml"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void previewWxr(f);
            }}
          />
          <Button
            variant="outline"
            onClick={() => wxrFileRef.current?.click()}
            disabled={wxrBusy}
          >
            <Upload className="h-4 w-4 ms-1" />
            {wxrBusy ? "در حال خواندن..." : "انتخاب فایل XML وردپرس"}
          </Button>
        </div>

        {wxrPreview && (
          <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-4">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Badge variant="outline">WXR</Badge>
              <span>{toPersianDigits(String(wxrPreview.counts.posts))} نوشته</span>
              <span className="text-muted-foreground">
                {toPersianDigits(String(wxrPreview.counts.pages))} برگه
              </span>
              <span className="text-muted-foreground">
                {toPersianDigits(String(wxrPreview.counts.categories))} دسته
              </span>
              <span className="text-muted-foreground">
                {toPersianDigits(String(wxrPreview.counts.tags))} برچسب
              </span>
              <span className="text-muted-foreground">
                {toPersianDigits(String(wxrPreview.counts.comments))} دیدگاه
              </span>
            </div>
            {wxrPreview.counts.posts === 0 && wxrPreview.counts.pages === 0 && (
              <p className="text-xs text-amber-600 dark:text-amber-500">
                این فایل هیچ نوشته یا برگه‌ای ندارد. در وردپرس هنگام خروجی
                گرفتن، محتوا را انتخاب کنید و دوباره export بگیرید.
              </p>
            )}
            {wxrPreview.sample.length > 0 && (
              <ul className="space-y-1 text-xs text-muted-foreground">
                {wxrPreview.sample.map((p, i) => (
                  <li key={`${p.slug}-${i}`} className="truncate">
                    • {p.title}
                    {p.category_slugs && p.category_slugs.length > 0
                      ? ` — ${p.category_slugs.join("، ")}`
                      : ""}
                  </li>
                ))}
              </ul>
            )}
            {wxrPreview.sample_pages.length > 0 && (
              <ul className="space-y-1 text-xs text-muted-foreground">
                {wxrPreview.sample_pages.map((p, i) => (
                  <li key={`${p.slug}-${i}`} className="truncate">
                    • [برگه] {p.title}
                    {p.parent_slug ? ` (زیرِ ${p.parent_slug})` : ""}
                  </li>
                ))}
              </ul>
            )}
            <Button
              onClick={() => void runWxrImport()}
              disabled={
                wxrBusy ||
                (wxrPreview.counts.posts === 0 && wxrPreview.counts.pages === 0)
              }
            >
              <FileUp className="h-4 w-4 ms-1" />
              {wxrBusy ? "در حال ایمپورت..." : "ایمپورت نوشته‌ها، برگه‌ها و دیدگاه‌ها"}
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
