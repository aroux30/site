"use client";

import React, { useCallback, useMemo, useState } from "react";
import {
  BarChart3,
  CalendarClock,
  Download,
  FileText,
  Package,
  Play,
  Plus,
  RefreshCw,
  Scale,
  TrendingUp,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { SystemHealthSection } from "@/components/admin/system-health-section";
import {
  daysAgoApiDate,
  formatJalali,
  formatJalaliDateTime,
  todayApiDate,
} from "@/lib/date";
import {
  reportingApi,
  type ReportPayload,
  type ReportQuery,
  type ReportRun,
  type ReportRunStatusValue,
  type ReportTypeValue,
  type SavedReport,
} from "@/lib/api/reporting";
import { saveBlob } from "@/lib/api/data-exchange";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import { apiErrorMessage } from "@/lib/api/error-message";
import { useAdminQuery } from "@/lib/api/admin-query";

const REPORTS_LIVE_QUERY_KEY = "admin-reports-live" as const;
const REPORTS_SAVED_QUERY_KEY = "admin-reports-saved" as const;

// ── Report catalogue ──────────────────────────────────────────────────────

interface ReportDef {
  value: ReportTypeValue;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  groupBys: { value: string; label: string }[];
  defaultGroupBy: string;
  supportsLowStockOnly?: boolean;
}

const REPORT_DEFS: ReportDef[] = [
  {
    value: "sales",
    label: "گزارش فروش",
    description: "تعداد سفارش، فروش ناخالص، تخفیف، استرداد، مالیات و درآمد خالص",
    icon: TrendingUp,
    groupBys: [
      { value: "day", label: "روزانه" },
      { value: "week", label: "هفتگی" },
      { value: "month", label: "ماهانه" },
      { value: "category", label: "دسته‌بندی" },
      { value: "vendor", label: "فروشنده" },
      { value: "channel", label: "کانال فروش" },
    ],
    defaultGroupBy: "day",
  },
  {
    value: "stock",
    label: "گزارش موجودی انبار",
    description: "موجودی فیزیکی، رزرو فعال و قابل فروش به‌همراه اقلام کم‌موجودی",
    icon: Package,
    groupBys: [
      { value: "variant", label: "تک‌تک اقلام" },
      { value: "warehouse", label: "انبار" },
      { value: "category", label: "دسته‌بندی" },
    ],
    defaultGroupBy: "variant",
    supportsLowStockOnly: true,
  },
  {
    value: "vendor_settlement",
    label: "گزارش تسویه فروشندگان",
    description: "کمیسیون پلتفرم و مبالغ در انتظار، قابل پرداخت و پرداخت‌شده",
    icon: Scale,
    groupBys: [
      { value: "vendor", label: "فروشنده" },
      { value: "status", label: "وضعیت سند تسویه" },
    ],
    defaultGroupBy: "vendor",
  },
  {
    value: "tax_vat",
    label: "گزارش مالیات بر ارزش افزوده",
    description: "تجمیع مشاهدات مالیاتی ثبت‌شده سفارش‌ها (موتور مالیاتی checkout)",
    icon: FileText,
    groupBys: [
      { value: "period", label: "دوره ماهانه" },
      { value: "rule", label: "قاعده مالیاتی" },
      { value: "category", label: "دسته‌بندی" },
    ],
    defaultGroupBy: "period",
  },
];

const REPORT_TYPE_LABELS: Record<ReportTypeValue, string> = {
  sales: "فروش",
  stock: "موجودی",
  vendor_settlement: "تسویه فروشندگان",
  tax_vat: "مالیات ارزش افزوده",
};

const RUN_STATUS_LABELS: Record<ReportRunStatusValue, string> = {
  pending: "در صف",
  running: "در حال اجرا",
  succeeded: "موفق",
  failed: "ناموفق",
  completed_no_delivery: "اجرا شد (بدون ارسال ایمیل)",
};

const RUN_STATUS_VARIANTS: Record<
  ReportRunStatusValue,
  "default" | "secondary" | "destructive" | "outline"
> = {
  pending: "outline",
  running: "secondary",
  succeeded: "default",
  failed: "destructive",
  completed_no_delivery: "secondary",
};

// Backend money columns are integer Rials → display in Toman.
function formatCell(value: string | number | null | undefined, kind: string): string {
  if (value === null || value === undefined || value === "") return "—";
  if (kind === "money" && typeof value === "number") {
    return formatPrice(Math.trunc(value / 10));
  }
  if (kind === "int" && typeof value === "number") {
    return toPersianDigits(value.toLocaleString("en-US"));
  }
  return toPersianDigits(String(value));
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function AdminReportsPage() {
  const { toast } = useToast();

  // ── Report query state ────────────────────────────────────────────
  const [reportType, setReportType] = useState<ReportTypeValue>("sales");
  const [dateFrom, setDateFrom] = useState(() => daysAgoApiDate(30));
  const [dateTo, setDateTo] = useState(() => todayApiDate());
  const [groupBy, setGroupBy] = useState("day");
  const [lowStockOnly, setLowStockOnly] = useState(false);

  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveCron, setSaveCron] = useState("");
  const [saveRecipients, setSaveRecipients] = useState("");
  const [saving, setSaving] = useState(false);
  const [runsFor, setRunsFor] = useState<SavedReport | null>(null);
  const [runs, setRuns] = useState<ReportRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);

  const currentDef = useMemo(
    () => REPORT_DEFS.find((d) => d.value === reportType)!,
    [reportType],
  );

  const currentFilters = useCallback((): Record<string, unknown> => {
    const filters: Record<string, unknown> = {
      date_from: dateFrom,
      date_to: dateTo,
      group_by: groupBy,
    };
    if (currentDef.supportsLowStockOnly && lowStockOnly) {
      filters.low_stock_only = true;
    }
    return filters;
  }, [dateFrom, dateTo, groupBy, currentDef, lowStockOnly]);

  // Two queries. Report generation and saved reports fail independently: a
  // broken saved-report cron parser must not blank the live charts.
  const dateOrderValid = dateFrom <= dateTo;
  const reportQuery = useAdminQuery({
    queryKey: [REPORTS_LIVE_QUERY_KEY, reportType, dateFrom, dateTo, groupBy, lowStockOnly],
    enabled: dateOrderValid,
    queryFn: () => {
      const query: ReportQuery = {
        from: dateFrom,
        to: dateTo,
        group_by: groupBy,
        ...(currentDef.supportsLowStockOnly && lowStockOnly ? { low_stock_only: true } : {}),
      };
      return reportingApi.getReport(reportType, query);
    },
    fallbackError: "خطا در دریافت گزارش",
  });
  const report: ReportPayload | null = dateOrderValid ? (reportQuery.data ?? null) : null;
  const reportLoading = dateOrderValid ? reportQuery.loading : false;
  const reportError = !dateOrderValid
    ? "«از تاریخ» نمی‌تواند بعد از «تا تاریخ» باشد"
    : reportQuery.error;
  const fetchReport = reportQuery.reload;

  const savedQuery = useAdminQuery({
    queryKey: [REPORTS_SAVED_QUERY_KEY],
    queryFn: () => reportingApi.listSavedReports({ page_size: 100 }),
    fallbackError: "خطا در دریافت گزارش‌های ذخیره‌شده",
  });
  const savedReports: SavedReport[] = savedQuery.data?.items ?? [];
  const savedLoading = savedQuery.loading;
  const savedError = savedQuery.error;
  const fetchSavedReports = savedQuery.reload;

  // When the report type changes, snap group_by to that report's default.
  const handleReportTypeChange = (value: string) => {
    const next = REPORT_DEFS.find((d) => d.value === value)!;
    setReportType(next.value);
    setGroupBy(next.defaultGroupBy);
    setLowStockOnly(false);
  };

  const handleExportCsv = async () => {
    try {
      const blob = await reportingApi.exportCsv(reportType, {
        from: dateFrom,
        to: dateTo,
        group_by: groupBy,
        ...(currentDef.supportsLowStockOnly && lowStockOnly
          ? { low_stock_only: true }
          : {}),
      });
      saveBlob(blob, `${reportType}-report-${dateFrom}-${dateTo}.csv`);
      toast({ title: "خروجی CSV آماده شد" });
    } catch (err) {
      toast({
        title: "خطا",
        description: apiErrorMessage(err, "دریافت خروجی CSV ناموفق بود"),
        variant: "destructive",
      });
    }
  };

  const handleSaveCurrent = async () => {
    if (!saveName.trim()) {
      toast({
        title: "نام گزارش الزامی است",
        description: "برای ذخیره گزارش یک نام وارد کنید",
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    try {
      const cron = saveCron.trim();
      const recipients = saveRecipients
        .split(/[,;\n]/)
        .map((r) => r.trim())
        .filter(Boolean);
      await reportingApi.createSavedReport({
        name: saveName.trim(),
        report_type: reportType,
        filters: currentFilters(),
        schedule_cron: cron || null,
        delivery_channels: recipients.length > 0 ? ["email"] : [],
        recipients,
      });
      toast({ title: "گزارش ذخیره شد" });
      setSaveDialogOpen(false);
      setSaveName("");
      setSaveCron("");
      setSaveRecipients("");
      void fetchSavedReports();
    } catch (err) {
      toast({
        title: "خطا در ذخیره گزارش",
        description: apiErrorMessage(err, "ذخیره گزارش ناموفق بود"),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleRunNow = async (saved: SavedReport) => {
    setRunningId(saved.id);
    try {
      const run = await reportingApi.runNow(saved.id);
      toast({
        title: "گزارش اجرا شد",
        description: `وضعیت: ${RUN_STATUS_LABELS[run.status]} — ${toPersianDigits(run.row_count)} ردیف`,
        variant: run.status === "failed" ? "destructive" : "default",
      });
      void fetchSavedReports();
      if (runsFor?.id === saved.id) void openRuns(saved);
    } catch (err) {
      toast({
        title: "خطا",
        description: apiErrorMessage(err, "اجرای گزارش ناموفق بود"),
        variant: "destructive",
      });
    } finally {
      setRunningId(null);
    }
  };

  const handleDeleteSaved = async (saved: SavedReport) => {
    if (!window.confirm(`گزارش «${saved.name}» برای همیشه حذف شود؟`)) return;
    try {
      await reportingApi.deleteSavedReport(saved.id);
      toast({ title: "گزارش حذف شد" });
      void fetchSavedReports();
    } catch (err) {
      toast({
        title: "خطا",
        description: apiErrorMessage(err, "حذف گزارش ناموفق بود"),
        variant: "destructive",
      });
    }
  };

  const handleToggleActive = async (saved: SavedReport) => {
    try {
      await reportingApi.updateSavedReport(saved.id, { is_active: !saved.is_active });
      void fetchSavedReports();
    } catch (err) {
      toast({
        title: "خطا",
        description: apiErrorMessage(err, "تغییر وضعیت گزارش ناموفق بود"),
        variant: "destructive",
      });
    }
  };

  const openRuns = async (saved: SavedReport) => {
    setRunsFor(saved);
    setRunsLoading(true);
    try {
      const data = await reportingApi.listRuns(saved.id, { page_size: 20 });
      setRuns(data.items);
    } catch (err) {
      toast({
        title: "خطا",
        description: apiErrorMessage(err, "دریافت سوابق اجرا ناموفق بود"),
        variant: "destructive",
      });
      setRuns([]);
    } finally {
      setRunsLoading(false);
    }
  };

  const handleDownloadRun = async (run: ReportRun, kind: "csv" | "html") => {
    if (!runsFor) return;
    try {
      const blob =
        kind === "csv"
          ? await reportingApi.downloadRun(runsFor.id, run.id)
          : await reportingApi.downloadRunHtml(runsFor.id, run.id);
      saveBlob(blob, `report-run-${run.id.slice(0, 12)}.${kind}`);
    } catch (err) {
      toast({
        title: "خطا",
        description: apiErrorMessage(err, "دریافت خروجی اجرا ناموفق بود"),
        variant: "destructive",
      });
    }
  };

  // ── Dynamic table columns from the report payload ────────────────
  const reportColumns: DataTableColumn<Record<string, string | number | null>>[] =
    useMemo(
      () =>
        (report?.columns ?? []).map((col) => ({
          key: col.key,
          header: col.label,
          className:
            col.kind === "money" || col.kind === "int"
              ? "font-mono text-left"
              : undefined,
          render: (row) => formatCell(row[col.key], col.kind),
        })),
      [report],
    );

  const savedColumns: DataTableColumn<SavedReport>[] = [
    {
      key: "name",
      header: "نام گزارش",
      render: (r) => (
        <div>
          <div className="font-medium text-foreground">{r.name}</div>
          <div className="text-xs text-muted-foreground">
            {REPORT_TYPE_LABELS[r.report_type]}
          </div>
        </div>
      ),
    },
    {
      key: "schedule",
      header: "زمان‌بندی",
      render: (r) =>
        r.schedule_cron ? (
          <code className="font-mono text-xs" dir="ltr">
            {r.schedule_cron}
          </code>
        ) : (
          <span className="text-xs text-muted-foreground">دستی</span>
        ),
    },
    {
      key: "next_run",
      header: "اجرای بعدی",
      hideOnMobile: true,
      render: (r) => (
        <span className="text-xs text-muted-foreground">
          {formatJalaliDateTime(r.next_run_at)}
        </span>
      ),
    },
    {
      key: "last_run",
      header: "آخرین اجرا",
      hideOnMobile: true,
      render: (r) => (
        <span className="text-xs text-muted-foreground">
          {formatJalaliDateTime(r.last_run_at)}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (r) => (
        <Badge variant={r.is_active ? "default" : "secondary"} className="text-[10px]">
          {r.is_active ? "فعال" : "غیرفعال"}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      render: (r) => (
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 px-2 text-xs"
            disabled={runningId === r.id}
            onClick={() => void handleRunNow(r)}
          >
            <Play className="h-3.5 w-3.5" />
            اجرا
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => void openRuns(r)}
          >
            سوابق
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => void handleToggleActive(r)}
          >
            {r.is_active ? "غیرفعال" : "فعال"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-destructive"
            onClick={() => void handleDeleteSaved(r)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  const runColumns: DataTableColumn<ReportRun>[] = [
    {
      key: "started",
      header: "شروع",
      render: (r) => (
        <span className="text-xs">{formatJalaliDateTime(r.started_at)}</span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (r) => (
        <Badge variant={RUN_STATUS_VARIANTS[r.status]} className="text-[10px]">
          {RUN_STATUS_LABELS[r.status]}
        </Badge>
      ),
    },
    {
      key: "rows",
      header: "ردیف‌ها",
      render: (r) => toPersianDigits(r.row_count),
    },
    {
      key: "error",
      header: "پیام",
      hideOnMobile: true,
      render: (r) => (
        <span className="text-xs text-muted-foreground">
          {r.error_message ?? "—"}
        </span>
      ),
    },
    {
      key: "download",
      header: "خروجی",
      render: (r) => (
        <div className="flex items-center gap-1">
          {r.has_csv && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => void handleDownloadRun(r, "csv")}
            >
              CSV
            </Button>
          )}
          {r.has_html && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => void handleDownloadRun(r, "html")}
            >
              HTML
            </Button>
          )}
        </div>
      ),
    },
  ];

  const CurrentIcon = currentDef.icon;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <BarChart3 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">مرکز گزارش‌ها</h1>
            <p className="text-sm text-muted-foreground">
              گزارش‌های پارامتردار فروش، انبار، تسویه و مالیات با خروجی CSV و
              زمان‌بندی ارسال
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => void fetchReport()}
          >
            <RefreshCw className="h-4 w-4" /> به‌روزرسانی
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => setSaveDialogOpen(true)}
          >
            <Plus className="h-4 w-4" /> ذخیره این گزارش
          </Button>
          <Button size="sm" className="gap-2" onClick={() => void handleExportCsv()}>
            <Download className="h-4 w-4" /> خروجی CSV
          </Button>
        </div>
      </div>

      {/* Query builder */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-1.5">
            <Label>نوع گزارش</Label>
            <Select value={reportType} onValueChange={handleReportTypeChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {REPORT_DEFS.map((d) => (
                  <SelectItem key={d.value} value={d.value}>
                    {d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>از تاریخ</Label>
            <Input
              type="date"
              dir="ltr"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
            <span className="block text-[10px] text-muted-foreground">
              معادل شمسی: {formatJalali(dateFrom)}
            </span>
          </div>
          <div className="space-y-1.5">
            <Label>تا تاریخ</Label>
            <Input
              type="date"
              dir="ltr"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
            <span className="block text-[10px] text-muted-foreground">
              معادل شمسی: {formatJalali(dateTo)}
            </span>
          </div>
          <div className="space-y-1.5">
            <Label>گروه‌بندی</Label>
            <Select value={groupBy} onValueChange={setGroupBy}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {currentDef.groupBys.map((g) => (
                  <SelectItem key={g.value} value={g.value}>
                    {g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {currentDef.supportsLowStockOnly ? (
            <div className="flex items-end pb-1">
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={lowStockOnly}
                  onChange={(e) => setLowStockOnly(e.target.checked)}
                  className="h-4 w-4 rounded border-input"
                />
                فقط اقلام کم‌موجودی
              </label>
            </div>
          ) : (
            <div />
          )}
        </div>
        <p className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
          <CurrentIcon className="h-3.5 w-3.5" />
          {currentDef.description}
        </p>
      </div>

      {/* Report table */}
      <DataTable
        columns={reportColumns}
        rows={report?.rows ?? []}
        rowKey={(row) => `${row.bucket}-${row.sku ?? ""}-${row.order_count ?? ""}`}
        loading={reportLoading}
        loadingMessage="در حال تولید گزارش..."
        error={reportError}
        emptyMessage="داده‌ای در این بازه یافت نشد."
        emptyDescription="بازه تاریخ یا گروه‌بندی را تغییر دهید."
      />

      {/* Totals */}
      {report && Object.keys(report.totals).length > 0 && (
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {report.columns
            .filter((c) => report.totals[c.key] !== undefined && c.kind !== "text")
            .map((c) => (
              <div
                key={c.key}
                className="rounded-xl border border-border bg-muted/30 p-3"
              >
                <div className="text-[10px] text-muted-foreground">{c.label}</div>
                <div className="mt-1 font-mono text-sm font-bold" dir="auto">
                  {formatCell(report.totals[c.key], c.kind)}
                </div>
              </div>
            ))}
        </div>
      )}
      {report?.notes.map((note, i) => (
        <p key={i} className="text-xs text-muted-foreground">
          * {note}
        </p>
      ))}

      {/* Saved reports */}
      <div className="space-y-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <CalendarClock className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-foreground">
              گزارش‌های ذخیره‌شده و زمان‌بندی ارسال
            </h3>
            <p className="text-xs text-muted-foreground">
              گزارش‌های زمان‌بندی‌شده با کرون ۵ فیلدی (به وقت تهران) اجرا و در
              صورت پیکربندی SMTP ایمیل می‌شوند
            </p>
          </div>
        </div>
        <DataTable
          columns={savedColumns}
          rows={savedReports}
          rowKey={(r) => r.id}
          loading={savedLoading}
          error={savedError}
          emptyMessage="هنوز گزارشی ذخیره نشده است."
          emptyDescription="با دکمه «ذخیره این گزارش» تعریف فعلی را با زمان‌بندی اختیاری ذخیره کنید."
        />
      </div>

      {/* System health & SLO monitoring (preserved from the previous page) */}
      <SystemHealthSection />

      {/* Save dialog */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>ذخیره گزارش فعلی</DialogTitle>
            <DialogDescription>
              {currentDef.label} — از {formatJalali(dateFrom)} تا{" "}
              {formatJalali(dateTo)} — گروه‌بندی:{" "}
              {currentDef.groupBys.find((g) => g.value === groupBy)?.label}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>نام گزارش</Label>
              <Input
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="مثلاً: گزارش فروش هفتگی"
              />
            </div>
            <div className="space-y-1.5">
              <Label>زمان‌بندی (کرون ۵ فیلدی، اختیاری)</Label>
              <Input
                dir="ltr"
                value={saveCron}
                onChange={(e) => setSaveCron(e.target.value)}
                placeholder="0 8 * * *"
                className="font-mono"
              />
              <span className="block text-[10px] text-muted-foreground">
                مثال: «۰ ۸ * * *» یعنی هر روز ساعت ۸ صبح به وقت تهران
              </span>
            </div>
            <div className="space-y-1.5">
              <Label>گیرندگان ایمیل (اختیاری، با ویرگول جدا کنید)</Label>
              <Input
                dir="ltr"
                value={saveRecipients}
                onChange={(e) => setSaveRecipients(e.target.value)}
                placeholder="ops@example.com, finance@example.com"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSaveDialogOpen(false)}
              disabled={saving}
            >
              انصراف
            </Button>
            <Button onClick={() => void handleSaveCurrent()} disabled={saving}>
              {saving ? "در حال ذخیره..." : "ذخیره گزارش"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Runs dialog */}
      <Dialog open={runsFor !== null} onOpenChange={(open) => !open && setRunsFor(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>سوابق اجرای «{runsFor?.name}»</DialogTitle>
            <DialogDescription>
              خروجی CSV و HTML هر اجرا بایگانی می‌شود (PDF هنوز در دسترس نیست؛
              از نمای HTML برای چاپ استفاده کنید)
            </DialogDescription>
          </DialogHeader>
          <DataTable
            columns={runColumns}
            rows={runs}
            rowKey={(r) => r.id}
            loading={runsLoading}
            emptyMessage="هنوز اجرایی ثبت نشده است."
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
