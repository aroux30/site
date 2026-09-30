"use client";

import { useState } from "react";
import { FileText, RefreshCw, ShieldCheck, ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { FilterSelect } from "@/components/admin/filter-select";
import { toPersianDigits } from "@/lib/utils";
import { useAdminQuery } from "@/lib/api/admin-query";
import {
  invoicingApi,
  type ChainVerification,
  type Invoice,
  type InvoiceStatus,
  type InvoiceType,
} from "@/lib/api/invoicing";

const INVOICES_QUERY_KEY = "admin-invoices" as const;

const STATUS_LABELS: Record<InvoiceStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  posted: { label: "صادرشده", variant: "secondary" },
  paid: { label: "پرداخت‌شده", variant: "default" },
  cancelled: { label: "باطل", variant: "destructive" },
};

const TYPE_LABELS: Record<InvoiceType, string> = {
  invoice: "فاکتور",
  credit_note: "سند اعتباری",
};

function formatToman(rial: number | undefined): string {
  if (rial === undefined || rial === null) return "—";
  return `${toPersianDigits(Math.trunc(rial / 10).toLocaleString("en-US"))} تومان`;
}

export default function AdminInvoicesPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [periodFilter, setPeriodFilter] = useState("");
  const [page, setPage] = useState(1);
  const [chain, setChain] = useState<ChainVerification | null>(null);
  const [verifying, setVerifying] = useState(false);

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [INVOICES_QUERY_KEY, statusFilter, typeFilter, periodFilter, page],
    queryFn: () =>
      invoicingApi.list({
        status: (statusFilter || undefined) as InvoiceStatus | undefined,
        type: (typeFilter || undefined) as InvoiceType | undefined,
        fiscal_period: periodFilter || undefined,
        page,
        page_size: 20,
      }),
    fallbackError: "دریافت فهرست اسناد ناموفق بود",
  });
  const items: Invoice[] = data?.items ?? [];
  const total = data?.total ?? 0;

  const runVerify = async () => {
    setVerifying(true);
    try {
      const report = await invoicingApi.verifyChain({
        type: (typeFilter || undefined) as InvoiceType | undefined,
        fiscal_period: periodFilter || undefined,
      });
      setChain(report);
    } catch {
      setChain(null);
    } finally {
      setVerifying(false);
    }
  };

  const columns: DataTableColumn<Invoice>[] = [
    {
      key: "number",
      header: "شماره سند",
      render: (inv) => (
        <a className="font-mono text-primary hover:underline" href={`/admin/invoices/${inv.id}`}>
          {inv.number ?? "— (پیش‌نویس)"}
        </a>
      ),
    },
    {
      key: "type",
      header: "نوع",
      render: (inv) => (
        <Badge variant={inv.type === "credit_note" ? "destructive" : "secondary"}>
          {TYPE_LABELS[inv.type] ?? inv.type}
        </Badge>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (inv) => {
        const s = STATUS_LABELS[inv.status] ?? { label: inv.status, variant: "outline" as const };
        return <Badge variant={s.variant}>{s.label}</Badge>;
      },
    },
    {
      key: "total",
      header: "مبلغ",
      render: (inv) => <span className="font-mono">{formatToman(inv.totals?.total)}</span>,
    },
    {
      key: "customer",
      header: "مشتری",
      hideOnMobile: true,
      render: (inv) => inv.customer?.name ?? "—",
    },
    {
      key: "period",
      header: "دوره مالی",
      hideOnMobile: true,
      render: (inv) => (inv.fiscal_period ? toPersianDigits(inv.fiscal_period) : "—"),
    },
    {
      key: "issued",
      header: "تاریخ صدور",
      hideOnMobile: true,
      render: (inv) => (inv.issued_at ? new Date(inv.issued_at).toLocaleString("fa-IR") : "—"),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            اسناد مالی (فاکتورها و اسناد اعتباری)
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            شماره‌گذاری متوالی بر اساس سال مالی شمسی، زنجیره رمزنگاری‌شده ضددستکاری و بایگانی سند
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4 ms-1" />
            تازه‌سازی
          </Button>
          <Button onClick={() => void runVerify()} disabled={verifying}>
            <ShieldCheck className="h-4 w-4 ms-1" />
            {verifying ? "در حال بررسی..." : "بررسی زنجیره"}
          </Button>
        </div>
      </div>

      {chain && (
        <Card
          className={`p-4 flex items-center gap-3 border ${
            chain.valid ? "border-green-500/40 bg-green-500/5" : "border-destructive/40 bg-destructive/5"
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
                زنجیره سالم است — {toPersianDigits(chain.documents_checked)} سند بررسی شد و هیچ
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
            id="status"
            label="وضعیت"
            value={statusFilter}
            onChange={(v) => { setStatusFilter(v); setPage(1); }}
            options={[
              { value: "", label: "همه وضعیت‌ها" },
              { value: "draft", label: "پیش‌نویس" },
              { value: "posted", label: "صادرشده" },
              { value: "paid", label: "پرداخت‌شده" },
              { value: "cancelled", label: "باطل" },
            ]}
          />
          <FilterSelect
            id="type"
            label="نوع سند"
            value={typeFilter}
            onChange={(v) => { setTypeFilter(v); setPage(1); }}
            options={[
              { value: "", label: "همه انواع" },
              { value: "invoice", label: "فاکتور" },
              { value: "credit_note", label: "سند اعتباری" },
            ]}
          />
          <div className="space-y-1.5">
            <label htmlFor="period" className="block text-[11px] font-medium text-muted-foreground">
              دوره مالی (سال شمسی)
            </label>
            <input
              id="period"
              value={periodFilter}
              onChange={(e) => { setPeriodFilter(e.target.value); setPage(1); }}
              placeholder="مثلاً 1404"
              className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-xs"
            />
          </div>
        </div>
      </Card>

      <DataTable
        columns={columns}
        rows={items}
        rowKey={(inv) => inv.id}
        loading={loading}
        error={error}
        emptyMessage="هنوز سندی ثبت نشده است"
        emptyDescription="فاکتورهای پیش‌نویس از سفارش‌های پرداخت‌شده (backfill) یا به‌صورت دستی ساخته می‌شوند"
        onRowClick={(inv) => (window.location.href = `/admin/invoices/${inv.id}`)}
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
    </div>
  );
}
