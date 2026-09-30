"use client";

import React, { useState } from "react";
import { CalendarCheck, Download, Lock, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { saveBlob } from "@/lib/api/data-exchange";
import { toPersianDigits } from "@/lib/utils";
import { accountingApi, type AccountingPeriod } from "@/lib/api/accounting";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const ACCOUNTING_PERIODS_QUERY_KEY = "admin-accounting-periods" as const;
import { apiErrorMessage } from "@/lib/api/error-message";

function formatRial(rial: number): string {
  return `${toPersianDigits(Math.trunc(rial).toLocaleString("en-US"))} ریال`;
}

export default function AdminAccountingPeriodsPage() {
  const { toast } = useToast();
  const [closing, setClosing] = useState(false);
  const [target, setTarget] = useState("");
  const [exporting, setExporting] = useState<string | null>(null);

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [ACCOUNTING_PERIODS_QUERY_KEY],
    queryFn: () => accountingApi.listPeriods(),
    fallbackError: "دریافت فهرست دوره‌های مالی ناموفق بود",
  });
  const periods: AccountingPeriod[] = data?.items ?? [];
  const runMutation = useAdminMutation();

  const doClose = async () => {
    const period = target.trim();
    if (!period) {
      toast({ title: "شماره دوره مالی الزامی است", variant: "destructive" });
      return;
    }
    setClosing(true);
    const result = await runMutation(
      () => accountingApi.closePeriod(period),
      {
        fallbackError: "بستن دوره ناموفق بود",
        invalidateKeys: [[ACCOUNTING_PERIODS_QUERY_KEY]],
      },
    );
    if (result.ok) {
      toast({
        title: `دوره مالی ${period} بسته شد`,
        description: `${toPersianDigits(result.data.entry_count)} سند قفل شد`,
      });
      setTarget("");
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
    setClosing(false);
  };

  const doExport = async (period: string) => {
    setExporting(period);
    try {
      const blob = await accountingApi.exportCsv({ fiscal_period: period });
      saveBlob(blob, `journal-${period}.csv`);
      toast({ title: "خروجی CSV آماده شد" });
    } catch {
      toast({ title: "خطا", description: "خروجی‌گیری ناموفق بود", variant: "destructive" });
    } finally {
      setExporting(null);
    }
  };

  const columns: DataTableColumn<AccountingPeriod>[] = [
    {
      key: "period",
      header: "دوره مالی (شمسی)",
      render: (p) => <span className="font-mono">{toPersianDigits(p.fiscal_period)}</span>,
    },
    {
      key: "status",
      header: "وضعیت",
      render: (p) =>
        p.status === "closed" ? (
          <Badge variant="destructive" className="flex w-fit items-center gap-1">
            <Lock className="h-3 w-3" />
            بسته‌شده
          </Badge>
        ) : (
          <Badge variant="secondary">باز</Badge>
        ),
    },
    {
      key: "entries",
      header: "تعداد اسناد",
      render: (p) => toPersianDigits(p.entry_count),
    },
    {
      key: "debit",
      header: "جمع بدهکار",
      hideOnMobile: true,
      render: (p) => <span className="font-mono">{formatRial(p.debit_total_rial)}</span>,
    },
    {
      key: "credit",
      header: "جمع بستانکار",
      hideOnMobile: true,
      render: (p) => <span className="font-mono">{formatRial(p.credit_total_rial)}</span>,
    },
    {
      key: "closed_at",
      header: "زمان بستن",
      hideOnMobile: true,
      render: (p) =>
        p.closed_at ? new Date(p.closed_at).toLocaleString("fa-IR") : "—",
    },
    {
      key: "actions",
      header: "",
      render: (p) => (
        <Button
          variant="outline"
          size="sm"
          disabled={exporting === p.fiscal_period}
          onClick={() => void doExport(p.fiscal_period)}
        >
          <Download className="h-3.5 w-3.5 ms-1" />
          خروجی
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <CalendarCheck className="h-5 w-5 text-primary" />
            بستن دوره مالی
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            با بستن یک دوره مالی شمسی، اسناد ثبت‌شده آن قفل می‌شوند و هیچ ثبت یا تغییری در آن
            دوره مجاز نیست. سند اصلاحی پس از بستن، در دوره جاری با ارجاع به سند اصلی ثبت می‌شود.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()}>
          <RefreshCw className="h-4 w-4 ms-1" />
          تازه‌سازی
        </Button>
      </div>

      <Card className="p-4">
        <h3 className="mb-3 text-sm font-bold">بستن دوره جدید</h3>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <label
              htmlFor="close-period"
              className="block text-[11px] font-medium text-muted-foreground"
            >
              دوره مالی (سال شمسی)
            </label>
            <input
              id="close-period"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="مثلاً 1404"
              className="h-10 w-48 rounded-md border border-input bg-background px-3 py-2 text-xs"
            />
          </div>
          <Button variant="destructive" onClick={() => void doClose()} disabled={closing}>
            <Lock className="h-4 w-4 ms-1" />
            {closing ? "در حال بستن..." : "بستن دوره مالی"}
          </Button>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          جمع بدهکار و بستانکار در لحظه بستن به‌عنوان تصویر کنترلی ثبت می‌شود؛ خود اسناد دست
          نمی‌خورند.
        </p>
      </Card>

      <DataTable
        columns={columns}
        rows={periods}
        rowKey={(p) => p.id}
        loading={loading}
        error={error}
        emptyMessage="هنوز دوره مالی بسته نشده است"
        emptyDescription="دوره‌ها با اولین بستن ایجاد می‌شوند؛ دوره‌های باز نیز در همین فهرست نمایش داده می‌شوند"
      />
    </div>
  );
}
