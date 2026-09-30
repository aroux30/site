"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  BarChart3,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  biApi,
  type ComparisonMode,
  type ComparisonResult,
  type MetricDelta,
} from "@/lib/api/bi";
import { useAdminQuery } from "@/lib/api/admin-query";

const BI_OPTIONS_QUERY_KEY = "admin-bi-options" as const;

function biCompareKey(
  reportType: string,
  fromDate: string,
  toDate: string,
  mode: string,
  groupBy: string,
  rowKey: string,
): string {
  return `${reportType}|${fromDate}|${toDate}|${mode}|${groupBy}|${rowKey}`;
}
import { toPersianDigits, formatPrice } from "@/lib/utils";

const REPORT_LABELS: Record<string, string> = {
  sales: "فروش",
  stock: "موجودی انبار",
  vendor_settlement: "تسویه فروشندگان",
  tax_vat: "مالیات بر ارزش افزوده",
};

const MODE_LABELS: Record<ComparisonMode, string> = {
  previous_period: "دوره قبل (هم‌طول)",
  same_period_last_year: "همین دوره، سال قبل",
};

const METRIC_LABELS: Record<string, string> = {
  gross: "فروش ناخالص",
  gross_sales_rial: "فروش ناخالص",
  net: "درآمد خالص",
  net_revenue_rial: "درآمد خالص",
  discount: "تخفیف",
  discount_rial: "تخفیف",
  refund: "بازپرداخت",
  refund_rial: "بازپرداخت",
  tax: "مالیات",
  tax_rial: "مالیات",
  order_count: "تعداد سفارش",
  orders: "تعداد سفارش",
  units_sold: "تعداد فروش‌رفته",
};

function metricLabel(key: string): string {
  return METRIC_LABELS[key] ?? key;
}

function isMoneyMetric(key: string): boolean {
  return key.includes("rial") || key.includes("gross") || key.includes("net");
}

function formatMetric(key: string, value: number): string {
  // The reporting layer returns money in Rial (gross_sales_rial, net_revenue_rial,
  // …), while formatPrice expects Toman.
  return isMoneyMetric(key)
    ? formatPrice(Math.trunc(value / 10))
    : toPersianDigits(String(value));
}

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** A delta chip: direction, magnitude, and an honest "—" when undefined. */
function DeltaChip({ delta }: { delta: MetricDelta }) {
  const Icon =
    delta.direction === "up"
      ? TrendingUp
      : delta.direction === "down"
        ? TrendingDown
        : Minus;

  const tone =
    delta.direction === "up"
      ? "text-emerald-600"
      : delta.direction === "down"
        ? "text-rose-600"
        : "text-muted-foreground";

  return (
    <span className={`flex items-center gap-1 text-xs ${tone}`}>
      <Icon className="h-3.5 w-3.5" />
      {delta.change_pct === null ? (
        // A percentage against zero is undefined; say so rather than print 100%.
        <span className="text-muted-foreground">
          {delta.previous === 0 && delta.current !== 0 ? "جدید" : "—"}
        </span>
      ) : (
        <span dir="ltr">
          {delta.pct_capped ? ">" : ""}
          {toPersianDigits(Math.abs(delta.change_pct).toFixed(1))}٪
        </span>
      )}
    </span>
  );
}

export default function AdminBiPage() {
  const { toast } = useToast();
  const [reportType, setReportType] = useState("sales");
  const [mode, setMode] = useState<ComparisonMode>("previous_period");
  const [groupBy, setGroupBy] = useState("day");
  const [rowKey, setRowKey] = useState("");
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return toISODate(d);
  });
  const [toDate, setToDate] = useState(() => toISODate(new Date()));

  // Query 1: the allow-list of comparable reports and modes. Independent of
  // the comparison inputs, fetched once.
  const {
    data: options,
    error: optionsError,
  } = useAdminQuery({
    queryKey: [BI_OPTIONS_QUERY_KEY],
    queryFn: () => biApi.comparableReports(),
    fallbackError: "دریافت فهرست گزارش‌ها ناموفق بود",
  });
  const reports: string[] = options?.reports ?? [];
  const modes: ComparisonMode[] = options?.modes ?? [];

  // The old effect defaulted reportType to the first comparable report once the
  // allow-list arrived. Preserve that, guarded so it only runs when the
  // current selection is not in the list.
  useEffect(() => {
    const first = reports[0];
    if (first !== undefined && !reports.includes(reportType)) {
      setReportType(first);
    }
  }, [reports, reportType]);

  // Query 2: the comparison itself. Parameterised on six inputs, and gated on
  // the allow-list having loaded — mirroring the old `if (reports.length > 0)`.
  const compareQuery = useAdminQuery({
    queryKey: [BI_OPTIONS_QUERY_KEY, biCompareKey(reportType, fromDate, toDate, mode, groupBy, rowKey.trim())],
    enabled: reports.length > 0,
    queryFn: () =>
      biApi.compare({
        report_type: reportType,
        from: fromDate,
        to: toDate,
        mode,
        group_by: groupBy || undefined,
        row_key: rowKey.trim() || undefined,
      }),
    fallbackError: "مقایسه ناموفق بود",
  });

  // The comparison error used to arrive as a toast (not an inline message);
  // keep that, and keep the "permission or bad range" hint operators rely on.
  const shownCompareError = useRef<string | null>(null);
  useEffect(() => {
    if (compareQuery.error === null) {
      shownCompareError.current = null;
      return;
    }
    if (shownCompareError.current === compareQuery.error) return;
    shownCompareError.current = compareQuery.error;
    toast({
      title: "مقایسه ناموفق بود",
      description: "دسترسی reports:read لازم است یا بازه نامعتبر است.",
      variant: "destructive",
    });
  }, [compareQuery.error, toast]);

  const run = useCallback(async () => {
    await compareQuery.reload();
  }, [compareQuery]);

  const result: ComparisonResult | null = compareQuery.data ?? null;
  const loading = compareQuery.loading;

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <BarChart3 className="h-5 w-5 text-primary" />
            مقایسه دوره‌ای گزارش‌ها
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            هر گزارش را در دو بازه اجرا می‌کند و تفاوت را نشان می‌دهد — روی
            همان لایه گزارش موجود، بدون تعریف دوبارهٔ هیچ شاخصی.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={run} disabled={loading}>
          <RefreshCw className={`ms-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          اجرای مقایسه
        </Button>
      </div>

      <Card className="p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <Label htmlFor="bi-report">گزارش</Label>
            <select
              id="bi-report"
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {reports.map((r) => (
                <option key={r} value={r}>
                  {REPORT_LABELS[r] ?? r}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="bi-mode">مبنای مقایسه</Label>
            <select
              id="bi-mode"
              value={mode}
              onChange={(e) => setMode(e.target.value as ComparisonMode)}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {modes.map((m) => (
                <option key={m} value={m}>
                  {MODE_LABELS[m] ?? m}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="bi-group">گروه‌بندی</Label>
            <select
              id="bi-group"
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="day">روزانه</option>
              <option value="week">هفتگی</option>
              <option value="month">ماهانه</option>
              <option value="category">دسته‌بندی</option>
              <option value="vendor">فروشنده</option>
            </select>
          </div>
          <div>
            <Label htmlFor="bi-from">از تاریخ</Label>
            <Input
              id="bi-from"
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              dir="ltr"
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="bi-to">تا تاریخ</Label>
            <Input
              id="bi-to"
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              dir="ltr"
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="bi-rowkey">مقایسه ردیفی بر اساس (اختیاری)</Label>
            <Input
              id="bi-rowkey"
              value={rowKey}
              onChange={(e) => setRowKey(e.target.value)}
              placeholder="category یا vendor"
              dir="ltr"
              className="mt-1"
            />
          </div>
        </div>
      </Card>

      {result && (
        <>
          <Card className="p-3">
            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <Badge variant="outline">
                دوره جاری:{" "}
                {toPersianDigits(
                  new Date(result.current_window.from).toLocaleDateString("fa-IR"),
                )}{" "}
                تا{" "}
                {toPersianDigits(
                  new Date(result.current_window.to).toLocaleDateString("fa-IR"),
                )}
              </Badge>
              <Badge variant="secondary">
                مقایسه با:{" "}
                {toPersianDigits(
                  new Date(result.previous_window.from).toLocaleDateString("fa-IR"),
                )}{" "}
                تا{" "}
                {toPersianDigits(
                  new Date(result.previous_window.to).toLocaleDateString("fa-IR"),
                )}
              </Badge>
              <span>{MODE_LABELS[result.mode] ?? result.mode}</span>
            </div>
          </Card>

          {result.totals.length > 0 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {result.totals.map((delta) => (
                <Card key={delta.key} className="p-4">
                  <p className="text-xs text-muted-foreground">
                    {metricLabel(delta.key)}
                  </p>
                  <p className="mt-1 text-xl font-bold">
                    {formatMetric(delta.key, delta.current)}
                  </p>
                  <div className="mt-2 flex items-center justify-between">
                    <DeltaChip delta={delta} />
                    <span className="text-[11px] text-muted-foreground">
                      قبل: {formatMetric(delta.key, delta.previous)}
                    </span>
                  </div>
                  {delta.pct_capped && (
                    <p className="mt-1 flex items-center gap-1 text-[10px] text-amber-600">
                      <AlertTriangle className="h-3 w-3" />
                      تغییر بیش از حد بزرگ برای نمایش درصد
                    </p>
                  )}
                </Card>
              ))}
            </div>
          )}

          {result.rows && result.rows.length > 0 && result.row_key && (
            <Card className="p-1">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40 text-xs">
                      <th className="p-2 text-right font-medium">
                        {metricLabel(result.row_key)}
                      </th>
                      {(result.metrics ?? []).map((metric) => (
                        <th key={metric} className="p-2 text-right font-medium">
                          {metricLabel(metric)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, idx) => (
                      <tr key={idx} className="border-b last:border-0">
                        <td className="p-2 font-medium">
                          {String(row[result.row_key as string] ?? "—")}
                        </td>
                        {(result.metrics ?? []).map((metric) => {
                          const cell = row[metric] as MetricDelta | undefined;
                          if (!cell) {
                            return (
                              <td key={metric} className="p-2 text-muted-foreground">
                                —
                              </td>
                            );
                          }
                          return (
                            <td key={metric} className="p-2">
                              <div className="flex flex-col gap-0.5">
                                <span>{formatMetric(metric, cell.current)}</span>
                                <DeltaChip delta={cell} />
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      {!loading && !result && (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          برای مشاهده مقایسه، «اجرای مقایسه» را بزنید.
        </Card>
      )}
    </div>
  );
}
