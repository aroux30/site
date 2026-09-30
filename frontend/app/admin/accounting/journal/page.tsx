"use client";

import React, { useState } from "react";
import {
  Download,
  FileSpreadsheet,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { FilterSelect } from "@/components/admin/filter-select";
import { saveBlob } from "@/lib/api/data-exchange";
import { toPersianDigits } from "@/lib/utils";
import { apiErrorMessage } from "@/lib/api/error-message";
import {
  accountingApi,
  type ChainVerification,
  type JournalEntry,
  type JournalEntryStatus,
  type JournalSourceType,
} from "@/lib/api/accounting";
import { useAdminQuery } from "@/lib/api/admin-query";

const ACCOUNTING_JOURNAL_QUERY_KEY = "admin-accounting-journal" as const;

const STATUS_LABELS: Record<
  JournalEntryStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  posted: { label: "ثبت‌شده", variant: "secondary" },
  reversed: { label: "برگشت‌خورده", variant: "destructive" },
};

const SOURCE_LABELS: Record<JournalSourceType, string> = {
  order: "سفارش (درآمد)",
  payment: "پرداخت (وصول)",
  refund: "بازگشت وجه",
  wallet: "کیف پول",
  settlement: "تسویه فروشنده",
  manual: "دستی",
};

function formatRial(rial: number | undefined): string {
  if (rial === undefined || rial === null) return "—";
  return `${toPersianDigits(Math.trunc(rial).toLocaleString("en-US"))} ریال`;
}

export default function AdminAccountingJournalPage() {
  const { toast } = useToast();
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [periodFilter, setPeriodFilter] = useState("");
  const [page, setPage] = useState(1);

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [ACCOUNTING_JOURNAL_QUERY_KEY, statusFilter, sourceFilter, periodFilter, page],
    queryFn: () =>
      accountingApi.listEntries({
        status: (statusFilter || undefined) as JournalEntryStatus | undefined,
        source_type: (sourceFilter || undefined) as JournalSourceType | undefined,
        fiscal_period: periodFilter || undefined,
        page,
        page_size: 20,
      }),
    fallbackError: "دریافت اسناد دفتر روزنامه ناموفق بود",
  });
  const items: JournalEntry[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const [chain, setChain] = useState<ChainVerification | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [exporting, setExporting] = useState(false);



  const runVerify = async () => {
    setVerifying(true);
    try {
      setChain(await accountingApi.verifyChain({ fiscal_period: periodFilter || undefined }));
    } catch {
      setChain(null);
      toast({ title: "خطا", description: "بررسی زنجیره ناموفق بود", variant: "destructive" });
    } finally {
      setVerifying(false);
    }
  };

  const doExport = async () => {
    setExporting(true);
    try {
      const blob = await accountingApi.exportCsv({ fiscal_period: periodFilter || undefined });
      saveBlob(blob, periodFilter ? `journal-${periodFilter}.csv` : "journal.csv");
      toast({ title: "خروجی CSV آماده شد" });
    } catch {
      toast({ title: "خطا", description: "خروجی‌گیری ناموفق بود", variant: "destructive" });
    } finally {
      setExporting(false);
    }
  };

  const columns: DataTableColumn<JournalEntry>[] = [
    {
      key: "number",
      header: "شماره سند",
      render: (e) => (
        <a
          className="font-mono text-primary hover:underline"
          href={`/admin/accounting/journal/${e.id}`}
        >
          {e.number ?? "— (پیش‌نویس)"}
        </a>
      ),
    },
    {
      key: "date",
      header: "تاریخ",
      render: (e) =>
        e.entry_date ? new Date(e.entry_date).toLocaleDateString("fa-IR") : "—",
    },
    {
      key: "source",
      header: "منبع",
      render: (e) => (
        <Badge variant="outline">{SOURCE_LABELS[e.source_type] ?? e.source_type}</Badge>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (e) => {
        const meta = STATUS_LABELS[e.status] ?? {
          label: e.status,
          variant: "outline" as const,
        };
        return <Badge variant={meta.variant}>{meta.label}</Badge>;
      },
    },
    {
      key: "amount",
      header: "جمع بدهکار",
      render: (e) => (
        <span className="font-mono">{formatRial(e.total_debit_rial)}</span>
      ),
    },
    {
      key: "balanced",
      header: "تراز",
      hideOnMobile: true,
      render: (e) =>
        e.balanced ? (
          <Badge variant="secondary">تراز</Badge>
        ) : (
          <Badge variant="destructive">ناتراز</Badge>
        ),
    },
    {
      key: "description",
      header: "شرح",
      hideOnMobile: true,
      render: (e) => (
        <span className="line-clamp-1 text-xs text-muted-foreground">{e.description}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <ScrollText className="h-5 w-5 text-primary" />
            دفتر روزنامه (اسناد حسابداری)
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            اسناد دوطرفه ثبت‌شده از رویدادهای سفارش، پرداخت، بازگشت وجه، کیف پول و تسویه —
            با شماره‌گذاری متوالی، زنجیره ضددستکاری و خروجی برای نرم‌افزارهای حسابداری
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4 ms-1" />
            تازه‌سازی
          </Button>
          <Button variant="outline" onClick={() => void runVerify()} disabled={verifying}>
            <ShieldCheck className="h-4 w-4 ms-1" />
            {verifying ? "در حال بررسی..." : "بررسی زنجیره"}
          </Button>
          <Button onClick={() => void doExport()} disabled={exporting}>
            <Download className="h-4 w-4 ms-1" />
            {exporting ? "در حال خروجی..." : "خروجی CSV (هلو)"}
          </Button>
        </div>
      </div>

      {chain && (
        <Card
          className={`flex items-center gap-3 border p-4 ${
            chain.valid
              ? "border-green-500/40 bg-green-500/5"
              : "border-destructive/40 bg-destructive/5"
          }`}
        >
          {chain.valid ? (
            <ShieldCheck className="h-5 w-5 text-green-600" />
          ) : (
            <ShieldAlert className="h-5 w-5 text-destructive" />
          )}
          <div className="text-sm">
            {chain.valid ? (
              <>
                زنجیره سالم است — {toPersianDigits(chain.entries_checked)} سند بررسی شد و هیچ
                دستکاری‌ای یافت نشد.
              </>
            ) : (
              <>
                زنجیره شکسته است! اولین سند مخدوش:{" "}
                <span className="font-mono font-bold">{chain.first_broken?.number}</span>
                {!chain.first_broken?.own_hash_ok && " (هش خود سند نامعتبر)"}
                {!chain.first_broken?.previous_hash_ok && " (پیوند به سند قبلی شکسته)"}
              </>
            )}
          </div>
        </Card>
      )}

      <Card className="p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <FilterSelect
            id="j-status"
            label="وضعیت"
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            options={[
              { value: "", label: "همه وضعیت‌ها" },
              { value: "draft", label: "پیش‌نویس" },
              { value: "posted", label: "ثبت‌شده" },
              { value: "reversed", label: "برگشت‌خورده" },
            ]}
          />
          <FilterSelect
            id="j-source"
            label="منبع سند"
            value={sourceFilter}
            onChange={(v) => {
              setSourceFilter(v);
              setPage(1);
            }}
            options={[
              { value: "", label: "همه منابع" },
              { value: "order", label: "سفارش (درآمد)" },
              { value: "payment", label: "پرداخت (وصول)" },
              { value: "refund", label: "بازگشت وجه" },
              { value: "wallet", label: "کیف پول" },
              { value: "settlement", label: "تسویه فروشنده" },
              { value: "manual", label: "دستی" },
            ]}
          />
          <div className="space-y-1.5">
            <label
              htmlFor="j-period"
              className="block text-[11px] font-medium text-muted-foreground"
            >
              دوره مالی (سال شمسی)
            </label>
            <input
              id="j-period"
              value={periodFilter}
              onChange={(e) => {
                setPeriodFilter(e.target.value);
                setPage(1);
              }}
              placeholder="مثلاً 1404"
              className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-xs"
            />
          </div>
        </div>
      </Card>

      <DataTable
        columns={columns}
        rows={items}
        rowKey={(e) => e.id}
        loading={loading}
        error={error}
        emptyMessage="هنوز سند حسابداری ثبت نشده است"
        emptyDescription="اسناد به‌صورت خودکار از رویدادهای مالی ساخته می‌شوند؛ برای سند دستی از دکمه «سند جدید» استفاده کنید"
        onRowClick={(e) => (window.location.href = `/admin/accounting/journal/${e.id}`)}
      />

      {total > 20 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            قبلی
          </Button>
          <span className="text-muted-foreground">
            صفحه {toPersianDigits(page)} از {toPersianDigits(Math.ceil(total / 20))}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page * 20 >= total}
            onClick={() => setPage(page + 1)}
          >
            بعدی
          </Button>
        </div>
      )}

      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <FileSpreadsheet className="h-3.5 w-3.5" />
        قالب خروجی CSV با ترتیب ستون‌های قابل‌ورود در هلو (و سازگار با سپیدار و محک) است:
        شماره سند، تاریخ شمسی، کد حساب، نام حساب، شرح، بدهکار، بستانکار
      </p>
    </div>
  );
}
