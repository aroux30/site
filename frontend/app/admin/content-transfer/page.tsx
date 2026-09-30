"use client";

import React, { useRef, useState } from "react";
import { Download, Upload, ArrowLeftRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { contentTransferApi } from "@/lib/api/cms-admin";

export default function AdminContentTransferPage() {
  const { toast } = useToast();
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<Record<string, number> | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const doExport = async () => {
    setExporting(true);
    try {
      const doc = await contentTransferApi.export();
      const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cms-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast({ title: "خروجی گرفته شد", description: `${doc.pages?.length ?? 0} صفحه و ${doc.faqs?.length ?? 0} سوال` });
    } catch {
      toast({ title: "خطا", description: "خروجی گرفتن ناموفق بود", variant: "destructive" });
    } finally {
      setExporting(false);
    }
  };

  const doImport = async (file: File) => {
    setImporting(true);
    setImportResult(null);
    try {
      const text = await file.text();
      const doc = JSON.parse(text);
      const result = await contentTransferApi.import(doc);
      setImportResult(result as Record<string, number>);
      toast({ title: "ورود انجام شد", description: "صفحات بر اساس نامک به‌روزرسانی یا ساخته شدند (idempotent)" });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({
        title: "خطا",
        description: detail ?? "فایل JSON معتبر نیست یا فرمت ناشناخته است",
        variant: "destructive",
      });
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div>
        <h2 className="text-xl font-bold flex items-center gap-2">
          <ArrowLeftRight className="h-5 w-5 text-primary" />
          انتقال محتوا (ورود / خروج)
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          خروجی JSON کامل صفحات و سوالات متداول؛ ورود idempotent بر اساس نامک
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card className="p-6 space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Download className="h-5 w-5 text-primary" />
            خروجی گرفتن
          </h3>
          <p className="text-sm text-muted-foreground">
            یک سند JSON نسخه‌دار از همه‌ی صفحات CMS و سوالات متداول دانلود می‌شود.
          </p>
          <Button onClick={doExport} disabled={exporting}>
            <Download className="h-4 w-4 ms-1" />
            {exporting ? "در حال آماده‌سازی..." : "دانلود خروجی JSON"}
          </Button>
        </Card>

        <Card className="p-6 space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Upload className="h-5 w-5 text-primary" />
            ورود محتوا
          </h3>
          <p className="text-sm text-muted-foreground">
            فایل JSON خروجی را انتخاب کنید. ورودی بر اساس نامک صفحه به‌روزرسانی یا ساخته می‌شود و
            اجرای مجدد همان فایل هیچ تغییر تازه‌ای نمی‌دهد.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept="application/json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void doImport(f);
            }}
          />
          <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={importing}>
            <Upload className="h-4 w-4 ms-1" />
            {importing ? "در حال ورود..." : "انتخاب فایل JSON"}
          </Button>
          {importResult && (
            <div className="rounded-lg border bg-muted/30 p-3 text-sm">
              <p>صفحات ساخته‌شده: {importResult.pages_created}</p>
              <p>صفحات به‌روزشده: {importResult.pages_updated}</p>
              <p>سوالات ساخته‌شده: {importResult.faqs_created}</p>
              <p>سوالات ردشده (موجود): {importResult.faqs_skipped}</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
