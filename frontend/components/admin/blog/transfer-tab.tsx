"use client";

/**
 * Blog import/export tab (WordPress parity).
 *
 * Exports the whole blog (posts, categories, tags, comments) as a JSON
 * document, and imports a previously exported document back. Existing slugs
 * are skipped by default so a re-import is safe.
 */

import { useRef, useState } from "react";
import { Download, Upload, FileJson, FileCode, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import { blogTransferApi } from "@/lib/api/wp-parity";

export function TransferTab() {
  const { toast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const wxrRef = useRef<HTMLInputElement>(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importingWxr, setImportingWxr] = useState(false);
  const [lastImport, setLastImport] = useState<{
    categories: number;
    tags: number;
    posts: number;
    skipped: number;
  } | null>(null);

  const handleExport = async () => {
    setExporting(true);
    try {
      const data = await blogTransferApi.exportAll();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `blog-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast({ title: "خروجی وبلاگ دانلود شد" });
    } catch {
      toast({ title: "خروجی گرفتن ناموفق بود", variant: "destructive" });
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async (file: File) => {
    setImporting(true);
    try {
      const text = await file.text();
      const payload = JSON.parse(text) as Record<string, unknown>;
      const stats = await blogTransferApi.importJson(payload);
      setLastImport(stats);
      toast({
        title: "وارد کردن انجام شد",
        description: `${stats.posts} نوشته، ${stats.categories} دسته، ${stats.tags} برچسب`,
      });
    } catch {
      toast({
        title: "وارد کردن ناموفق بود",
        description: "فایل باید خروجی JSON همین سامانه باشد.",
        variant: "destructive",
      });
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  /** Import a WordPress WXR file.
   *
   *  A separate path from the JSON one on purpose, and not a fallback: WXR is
   *  the only format a WordPress site can hand you, and a file that is XML
   *  cannot be `JSON.parse`d — so a shared handler would have to sniff the
   *  content and guess. Guessing wrong here means an operator watches a
   *  migration silently import nothing.
   *
   *  The parsed counts are reported next to the imported ones, because "12
   *  posts imported" out of a file holding 300 is a different outcome from
   *  300 imported out of 300 and the operator is the one who has to tell
   *  them apart.
   */
  const handleImportWxr = async (file: File) => {
    setImportingWxr(true);
    try {
      const stats = await blogTransferApi.importWxr(file);
      setLastImport(stats);
      const parsed = stats.parsed;
      const missing =
        parsed && parsed.posts > stats.posts + stats.skipped
          ? ` — فایل ${stats.posts + stats.skipped} نوشته داشت`
          : "";
      toast({
        title: "وارد کردن WXR انجام شد",
        description:
          `${stats.posts} نوشته، ${stats.categories} دسته، ${stats.tags} برچسب` +
          missing,
      });
    } catch {
      toast({
        title: "وارد کردن WXR ناموفق بود",
        description: "فایل باید خروجی XML وردپرس (WXR) باشد.",
        variant: "destructive",
      });
    } finally {
      setImportingWxr(false);
      if (wxrRef.current) wxrRef.current.value = "";
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="space-y-4 p-5">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Download className="h-4 w-4" /> خروجی گرفتن
        </h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          تمام نوشته‌ها، دسته‌بندی‌ها، برچسب‌ها و ارتباط آن‌ها به صورت یک فایل JSON
          دانلود می‌شود. این فایل برای پشتیبان‌گیری یا انتقال به نصب دیگر قابل
          استفاده است.
        </p>
        <Button onClick={() => void handleExport()} disabled={exporting} className="w-full">
          <FileJson className="h-4 w-4" />
          {exporting ? "در حال آماده‌سازی…" : "دانلود خروجی JSON"}
        </Button>
      </Card>

      <Card className="space-y-4 p-5">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Upload className="h-4 w-4" /> وارد کردن
        </h3>
        <p className="text-xs leading-relaxed text-muted-foreground">
          فایل JSON خروجی‌گرفته‌شده را انتخاب کنید. مواردی که نامک (slug) آن‌ها
          از قبل وجود دارد نادیده گرفته می‌شوند تا داده تکراری ساخته نشود.
        </p>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleImport(file);
          }}
        />
        <Button
          variant="outline"
          className="w-full"
          onClick={() => fileRef.current?.click()}
          disabled={importing}
        >
          <Upload className="h-4 w-4" />
          {importing ? "در حال وارد کردن…" : "انتخاب فایل JSON"}
        </Button>

        {lastImport && (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-[11px] text-emerald-700 dark:text-emerald-300">
            آخرین وارد کردن: {lastImport.posts} نوشته، {lastImport.categories} دسته،{" "}
            {lastImport.tags} برچسب، {lastImport.skipped} مورد نادیده‌گرفته‌شده
          </div>
        )}

        {/* WordPress migration, beside the JSON import and not folded into it.
            WXR is the only format a WordPress install can produce, and it is
            XML: `JSON.parse` on it throws, so the JSON path cannot serve it and
            the alternative is a paragraph telling the operator to convert the
            file by hand first. */}
        <div className="space-y-2 rounded-lg border border-dashed border-border p-4">
          <p className="text-xs leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">انتقال از وردپرس:</span>{" "}
            در وردپرس به «ابزار ← درون‌ریزی ← همهٔ محتوا» بروید، فایل XML را
            بگیرید و همین‌جا انتخاب کنید. دسته‌ها، برچسب‌ها، نوشته‌ها، دیدگاه‌ها و
            وضعیت پیش‌نویس‌ها همراه فایل منتقل می‌شوند.
          </p>
          <input
            ref={wxrRef}
            type="file"
            accept="text/xml,application/xml,.xml"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleImportWxr(file);
            }}
          />
          <Button
            variant="outline"
            className="w-full"
            onClick={() => wxrRef.current?.click()}
            disabled={importingWxr || importing}
          >
            <FileCode className="h-4 w-4" />
            {importingWxr ? "در حال وارد کردن…" : "انتخاب فایل WXR (XML)"}
          </Button>
        </div>

        <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-[11px] text-amber-700 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            وارد کردن محتوا را حذف نمی‌کند؛ فقط اضافه می‌کند. پیش از وارد کردن روی
            نصب فعال، از داده فعلی خروجی بگیرید.
          </span>
        </div>
      </Card>
    </div>
  );
}
