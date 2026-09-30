"use client";

import React, { useState } from "react";
import {
  FolderOpen,
  Archive,
  RefreshCw,
  Search,
  FileText,
  Link as LinkIcon,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { useToast } from "@/components/ui/use-toast";
import {
  dmsApi,
  type ArchivedDocument,
  type ArchivedDocumentKind,
  type Attachment,
} from "@/lib/api/dms";
import { toPersianDigits } from "@/lib/utils";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const ARCHIVE_QUERY_KEY = "admin-documents-archive" as const;
const ATTACHABLE_TYPES_QUERY_KEY = "admin-documents-attachable-types" as const;
const ATTACHMENTS_QUERY_KEY = "admin-documents-attachments" as const;

const ARCHIVE_KIND_LABELS: Record<ArchivedDocumentKind, string> = {
  invoice: "فاکتور فروش",
  credit_note: "اعتبارنامه (برگشت)",
  receipt: "رسید دریافت",
  settlement: "تسویه",
  other: "سایر",
};

const ATTACHMENT_KIND_LABELS: Record<string, string> = {
  general: "عمومی",
  contract: "قرارداد",
  invoice: "فاکتور",
  receipt: "رسید",
  shipping_label: "برچسب ارسال",
  inspection: "بازرسی",
  return_form: "فرم مرجوعی",
  other: "سایر",
};

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${toPersianDigits(String(bytes))} بایت`;
  if (bytes < 1024 * 1024)
    return `${toPersianDigits((bytes / 1024).toFixed(1))} کیلوبایت`;
  return `${toPersianDigits((bytes / (1024 * 1024)).toFixed(1))} مگابایت`;
}

export default function AdminDocumentsPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<"archive" | "record">("archive");

  const [periodFilter, setPeriodFilter] = useState("");
  const [keyFilter, setKeyFilter] = useState("");
  const [includeSuperseded, setIncludeSuperseded] = useState(false);

  // Record-attachments state
  const [entityType, setEntityType] = useState("order");
  const [entityId, setEntityId] = useState("");

  // Archive search refetches automatically when a filter changes; the
  // failure toast from the old hand-written load is preserved via
  // toastOnError instead of an inline catch.
  const {
    data: documentsData,
    loading: archiveLoading,
    reload: loadArchive,
  } = useAdminQuery({
    queryKey: [ARCHIVE_QUERY_KEY, periodFilter, keyFilter, includeSuperseded],
    queryFn: () =>
      dmsApi.searchArchive({
        fiscal_period: periodFilter.trim() || undefined,
        document_key: keyFilter.trim() || undefined,
        include_superseded: includeSuperseded,
        limit: 200,
      }),
    fallbackError: "خطا در جست‌وجوی بایگانی",
    toastOnError: true,
  });
  const documents: ArchivedDocument[] = documentsData ?? [];

  const { data: attachableTypesData } = useAdminQuery({
    queryKey: [ATTACHABLE_TYPES_QUERY_KEY],
    queryFn: () => dmsApi.attachableTypes(),
    fallbackError: "دریافت نوع‌های رکورد ناموفق بود",
  });
  const attachableTypes: string[] = attachableTypesData?.entity_types ?? [];

  const {
    data: attachmentsData,
    loading: attachLoading,
    reload: reloadAttachments,
  } = useAdminQuery({
    queryKey: [ATTACHMENTS_QUERY_KEY, entityType, entityId.trim()],
    queryFn: () => dmsApi.listAttachments(entityType, entityId.trim()),
    fallbackError: "خطا در دریافت پیوست‌ها",
    enabled: false,
    toastOnError: true,
  });
  const attachments: Attachment[] = attachmentsData ?? [];

  const loadAttachments = async () => {
    if (!entityId.trim()) {
      toast({ title: "شناسه رکورد را وارد کنید", variant: "destructive" });
      return;
    }
    await reloadAttachments();
  };

  const runMutation = useAdminMutation();

  const removeAttachment = async (attachment: Attachment) => {
    const result = await runMutation(() => dmsApi.deleteAttachment(attachment.id), {
      fallbackError: "حذف پیوست ناموفق بود",
      invalidateKeys: [[ATTACHMENTS_QUERY_KEY]],
    });
    if (result.ok) {
      toast({
        title: "پیوست حذف شد",
        description: "فایل اصلی در کتابخانه رسانه باقی می‌ماند.",
        variant: "success",
      });
      await reloadAttachments();
    } else {
      toast({ title: result.error, variant: "destructive" });
    }
  };

  const archiveColumns: DataTableColumn<ArchivedDocument>[] = [
    {
      key: "key",
      header: "شماره سند",
      render: (d) => (
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs" dir="ltr">
            {d.document_key}
          </span>
          {d.is_superseded && (
            <Badge variant="outline" className="text-[10px]">
              جایگزین‌شده
            </Badge>
          )}
        </div>
      ),
    },
    {
      key: "kind",
      header: "نوع",
      render: (d) => (
        <Badge variant="secondary">{ARCHIVE_KIND_LABELS[d.kind] ?? d.kind}</Badge>
      ),
    },
    {
      key: "period",
      header: "دوره مالی",
      render: (d) => (d.fiscal_period ? toPersianDigits(d.fiscal_period) : "—"),
    },
    {
      key: "entity",
      header: "رکورد مرتبط",
      render: (d) => (
        <span className="text-xs text-muted-foreground" dir="ltr">
          {d.entity_type}/{d.entity_id.slice(0, 8)}…
        </span>
      ),
    },
    {
      key: "hash",
      header: "اثر انگشت",
      render: (d) =>
        d.content_hash ? (
          <span className="font-mono text-[10px] text-muted-foreground" dir="ltr">
            {d.content_hash.slice(0, 12)}…
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "path",
      header: "فایل",
      render: (d) => (
        <a
          href={d.archive_path.startsWith("/") ? d.archive_path : `/${d.archive_path}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-primary hover:underline"
          dir="ltr"
        >
          {d.archive_path}
        </a>
      ),
    },
    {
      key: "at",
      header: "تاریخ ثبت",
      render: (d) => toPersianDigits(new Date(d.created_at).toLocaleDateString("fa-IR")),
    },
  ];

  const attachmentColumns: DataTableColumn<Attachment>[] = [
    {
      key: "name",
      header: "فایل",
      render: (a) => (
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <p className="truncate text-sm">{a.title ?? a.file_name}</p>
            <p className="font-mono text-[10px] text-muted-foreground" dir="ltr">
              {a.file_name}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "kind",
      header: "نوع",
      render: (a) => (
        <Badge variant="outline">
          {ATTACHMENT_KIND_LABELS[a.kind] ?? a.kind}
        </Badge>
      ),
    },
    {
      key: "size",
      header: "حجم",
      render: (a) => formatBytes(a.file_size),
    },
    {
      key: "link",
      header: "لینک",
      render: (a) => (
        <a
          href={a.file_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-primary hover:underline"
        >
          <LinkIcon className="h-3 w-3" />
          مشاهده
        </a>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (a) => (
        <Button
          variant="ghost"
          size="sm"
          className="text-destructive hover:text-destructive"
          onClick={() => removeAttachment(a)}
        >
          حذف
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <FolderOpen className="h-5 w-5 text-primary" />
            اسناد و پیوست‌ها
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            بایگانی اسناد مالی (فاکتور، اعتبارنامه) و پیوست فایل به
            رکوردهای کسب‌وکار (سفارش، مرجوعی، سفارش خرید، تسویه).
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadArchive}>
          <RefreshCw className="ms-2 h-4 w-4" />
          بروزرسانی
        </Button>
      </div>

      <div className="flex gap-2 border-b">
        <button
          onClick={() => setTab("archive")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            tab === "archive"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Archive className="ms-1.5 inline h-4 w-4" />
          بایگانی اسناد مالی
        </button>
        <button
          onClick={() => setTab("record")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            tab === "record"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <FileText className="ms-1.5 inline h-4 w-4" />
          پیوست‌های یک رکورد
        </button>
      </div>

      {tab === "archive" ? (
        <>
          <Card className="p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <Label htmlFor="period">دوره مالی (شمسی)</Label>
                <Input
                  id="period"
                  value={periodFilter}
                  onChange={(e) => setPeriodFilter(e.target.value)}
                  placeholder="مثلاً 1404"
                  dir="ltr"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="dockey">شماره سند</Label>
                <Input
                  id="dockey"
                  value={keyFilter}
                  onChange={(e) => setKeyFilter(e.target.value)}
                  placeholder="INV-1404-000001"
                  dir="ltr"
                  className="mt-1"
                />
              </div>
              <label className="flex items-end gap-2 pb-2 text-sm">
                <input
                  type="checkbox"
                  checked={includeSuperseded}
                  onChange={(e) => setIncludeSuperseded(e.target.checked)}
                  className="h-4 w-4"
                />
                نمایش نسخه‌های جایگزین‌شده
              </label>
            </div>
            <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5" />
              اسناد بایگانی‌شده از طریق API حذف نمی‌شوند — این جدول سند
              اثباتی است.
            </div>
          </Card>

          {archiveLoading ? (
            <div className="flex justify-center py-10">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Card className="p-1">
              <DataTable
                columns={archiveColumns}
                rows={documents}
                rowKey={(d) => d.id}
                loading={archiveLoading}
                emptyMessage="سندی در بایگانی نیست"
                emptyDescription="با ثبت (post) فاکتور در ماژول اسناد مالی، سند به‌صورت خودکار اینجا ایندکس می‌شود."
              />
            </Card>
          )}
        </>
      ) : (
        <>
          <Card className="p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[200px_1fr_auto]">
              <div>
                <Label htmlFor="etype">نوع رکورد</Label>
                <select
                  id="etype"
                  value={entityType}
                  onChange={(e) => setEntityType(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  dir="ltr"
                >
                  {(attachableTypes.length
                    ? attachableTypes
                    : ["order", "return", "purchase_order", "vendor_settlement"]
                  ).map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="eid">شناسه رکورد (UUID)</Label>
                <Input
                  id="eid"
                  value={entityId}
                  onChange={(e) => setEntityId(e.target.value)}
                  dir="ltr"
                  className="mt-1"
                />
              </div>
              <div className="flex items-end">
                <Button onClick={loadAttachments}>
                  <Search className="ms-2 h-4 w-4" />
                  جست‌وجو
                </Button>
              </div>
            </div>
          </Card>

          {attachLoading ? (
            <div className="flex justify-center py-10">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Card className="p-1">
              <DataTable
                columns={attachmentColumns}
                rows={attachments}
                rowKey={(a) => a.id}
                loading={attachLoading}
                emptyMessage="پیوستی برای این رکورد یافت نشد"
                emptyDescription="پیوست‌ها پس از بارگذاری فایل در کتابخانه رسانه، از طریق API ثبت می‌شوند."
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
