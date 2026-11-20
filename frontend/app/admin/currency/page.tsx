"use client";

/**
 * Admin — به‌روزرسانی خودکار قیمت دلاری (USD→Toman rate updater).
 *
 * Ported from the owner's WordPress plugin "Nobitex Price Updater Ultimate".
 * Two tabs:
 * - «تنظیمات» — one config object (SiteSetting `currency.usd_rate`): master
 *   switch, Nobitex API on/off, manual fallback rate (Toman), interval,
 *   rounding step (Toman), history-log switch. The status card shows the
 *   last successful rate, next scheduled run, managed-variant count, and the
 *   last error when a run failed. «به‌روزرسانی الآن» runs a sweep on demand.
 * - «تاریخچهٔ اجراها» — one row per sweep (the plugin's log viewer):
 *   rate used, source, how many prices changed, scheduled vs manual, and the
 *   per-variant before/after detail.
 *
 * Money: the wire carries integer Rial (ADR-012); the manual rate and the
 * rounding step are EDIT in Toman and displayed with Toman units — the same
 * convention as the referrals panel. `last_*` fields are server-owned.
 */

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Coins,
  FileDown,
  History,
  Loader2,
  Play,
  RefreshCw,
  Save,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { JalaliDatePicker } from "@/components/ui/jalali-datepicker";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { FilterSelect } from "@/components/admin/filter-select";
import { formatJalali, formatJalaliDateTime } from "@/lib/date";
import { toEnglishDigits, toPersianDigits } from "@/lib/utils";
import {
  exportRateHistory,
  fetchRateHistory,
  fetchUsdRateConfig,
  runUsdRateUpdateNow,
  updateUsdRateConfig,
  type RateHistoryFilters,
  type RateHistoryItem,
  type UsdRateConfigResponse,
} from "@/lib/api/currency-admin";
import { saveBlob } from "@/lib/api/data-exchange";

/** Rial → Toman display (store convention: 1 Toman = 10 Rial). */
function fmtToman(rial: number): string {
  return Math.trunc(rial / 10).toLocaleString("fa-IR");
}

/** Toman input text → Rial for the wire. */
function tomanToRial(toman: string): number {
  const n = Number(toEnglishDigits(toman).replace(/[^\d]/g, ""));
  return Number.isFinite(n) ? n * 10 : 0;
}

// ── Settings tab ──────────────────────────────────────────────────────────

function SettingsTab() {
  const { toast } = useToast();
  const [data, setData] = useState<UsdRateConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  // Text state for the two Toman inputs: a number input silently rewrites
  // while typing; text + commit-on-blur keeps the operator's digits intact.
  const [manualRateText, setManualRateText] = useState("");
  const [roundingText, setRoundingText] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchUsdRateConfig();
      setData(res);
      setManualRateText(String(Math.trunc(res.config.manual_rate_rial / 10)));
      setRoundingText(String(res.config.price_rounding_toman));
    } catch {
      setError("دریافت تنظیمات به‌روزرسانی قیمت ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const patch = (partial: Partial<UsdRateConfigResponse["config"]>) => {
    setData((prev) =>
      prev ? { ...prev, config: { ...prev.config, ...partial } } : prev,
    );
  };

  const onSave = async () => {
    if (!data) return;
    setSaving(true);
    try {
      const res = await updateUsdRateConfig({
        enabled: data.config.enabled,
        api_enabled: data.config.api_enabled,
        manual_rate_rial: tomanToRial(manualRateText),
        update_interval_minutes: data.config.update_interval_minutes,
        price_rounding_toman: Number(roundingText.replace(/[^\d]/g, "")) || 1,
        log_enabled: data.config.log_enabled,
      });
      setData(res);
      setManualRateText(String(Math.trunc(res.config.manual_rate_rial / 10)));
      setRoundingText(String(res.config.price_rounding_toman));
      toast({
        title: "تنظیمات ذخیره شد",
        description: "تنظیمات به‌روزرسانی قیمت دلاری به‌روزرسانی گردید.",
        variant: "success",
      });
    } catch {
      toast({
        title: "ذخیره ناموفق",
        description: "تنظیمات ذخیره نشد؛ دوباره تلاش کنید.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const onRunNow = async () => {
    setRunning(true);
    try {
      const res = await runUsdRateUpdateNow();
      if (res.status === "success") {
        toast({
          title: "به‌روزرسانی انجام شد",
          description: `${toPersianDigits(res.updated_count)} قیمت با نرخ ${fmtToman(res.rate_rial ?? 0)} تومان به‌روز شد.`,
          variant: "success",
        });
      } else {
        toast({
          title: "به‌روزرسانی ناموفق",
          description: res.error || "اجرای به‌روزرسانی با خطا مواجه شد.",
          variant: "destructive",
        });
      }
      await load();
    } catch {
      toast({
        title: "خطا",
        description: "درخواست اجرای به‌روزرسانی ناموفق بود.",
        variant: "destructive",
      });
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          {error || "داده‌ای یافت نشد."}
          <div className="mt-3">
            <Button variant="outline" size="sm" onClick={() => void load()}>
              <RefreshCw className="h-4 w-4" /> تلاش دوباره
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const cfg = data.config;

  return (
    <div className="space-y-4">
      {/* Status card — the plugin's "وضعیت فعلی" panel. */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Coins className="h-4 w-4" />
            وضعیت فعلی
          </CardTitle>
          <CardDescription>
            نرخ در گردش، زمان اجرای بعدی و تعداد کالاهای دلاری تحت مدیریت.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-xs text-muted-foreground">نرخ فعلی</p>
              <p className="mt-1 font-mono text-lg font-bold">
                {cfg.last_rate_rial > 0 ? (
                  <>
                    {fmtToman(cfg.last_rate_rial)}
                    <span className="text-xs font-normal text-muted-foreground"> تومان</span>
                  </>
                ) : (
                  <span className="text-sm font-normal text-muted-foreground">هنوز اجرا نشده</span>
                )}
              </p>
              {cfg.last_source ? (
                <Badge variant="secondary" className="mt-1 text-[10px]">
                  {cfg.last_source === "api" ? "از نوبیتکس" : "نرخ دستی"}
                </Badge>
              ) : null}
            </div>
            <div>
              <p className="text-xs text-muted-foreground">آخرین اجرا</p>
              <p className="mt-1 text-sm">
                {cfg.last_attempt_at ? formatJalaliDateTime(cfg.last_attempt_at) : "هرگز"}
              </p>
              {cfg.last_status === "failed" ? (
                <Badge variant="destructive" className="mt-1 text-[10px]">
                  ناموفق
                </Badge>
              ) : cfg.last_status === "success" ? (
                <Badge variant="success" className="mt-1 text-[10px]">
                  موفق
                </Badge>
              ) : null}
            </div>
            <div>
              <p className="text-xs text-muted-foreground">اجرای بعدی</p>
              <p className="mt-1 text-sm">
                {data.next_run_at ? (
                  cfg.enabled ? (
                    formatJalaliDateTime(data.next_run_at)
                  ) : (
                    "برنامه غیرفعال است"
                  )
                ) : (
                  "زمان‌بندی نشده"
                )}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">کالاهای دلاری</p>
              <p className="mt-1 font-mono text-lg font-bold">
                {toPersianDigits(data.managed_variants)}
                <span className="text-xs font-normal text-muted-foreground"> واریانت</span>
              </p>
            </div>
          </div>

          {cfg.last_status === "failed" && cfg.last_error ? (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{cfg.last_error}</span>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void onRunNow()} disabled={running} className="gap-2">
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              به‌روزرسانی قیمت‌ها الآن
            </Button>
            <Button variant="outline" onClick={() => void load()} disabled={loading} className="gap-2">
              <RefreshCw className="h-4 w-4" />
              تازه‌سازی
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            اجرای دستی مستقل از کلید فعال‌بودن و فاصلهٔ زمانی اجرا می‌شود و مثل اجراهای زمان‌بندی‌شده
            در تاریخچه ثبت می‌گردد.
          </p>
        </CardContent>
      </Card>

      {/* Settings form — the plugin's options page. */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">تنظیمات نرخ و اجرا</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium">فعال بودن کل به‌روزرسانی خودکار</p>
              <p className="text-xs text-muted-foreground">
                با خاموش‌شدن، اجرای زمان‌بندی‌شده متوقف می‌شود؛ دکمهٔ اجرای دستی کار می‌کند.
              </p>
            </div>
            <Switch
              checked={cfg.enabled}
              onCheckedChange={(v) => patch({ enabled: v })}
              aria-label="فعال/غیرفعال کردن به‌روزرسانی خودکار قیمت"
            />
          </div>

          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium">دریافت نرخ از API نوبیتکس</p>
              <p className="text-xs text-muted-foreground">
                در صورت قطع بودن یا ناموفق بودن API، نرخ دستی زیر استفاده می‌شود.
              </p>
            </div>
            <Switch
              checked={cfg.api_enabled}
              onCheckedChange={(v) => patch({ api_enabled: v })}
              aria-label="فعال/غیرفعال کردن دریافت نرخ از نوبیتکس"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5">
              <span className="text-sm font-medium">نرخ دستی (تومان)</span>
              <div className="flex items-center gap-2">
                <Input
                  dir="ltr"
                  className="font-mono"
                  value={manualRateText ? Number(manualRateText).toLocaleString("fa-IR") : ""}
                  onChange={(e) => setManualRateText(toEnglishDigits(e.target.value).replace(/\D/g, ""))}
                  placeholder="مثلاً: ۱۸۵٬۰۰۰"
                />
                <span className="text-xs whitespace-nowrap text-muted-foreground">تومان</span>
              </div>
              <span className="block text-xs text-muted-foreground">
                نرخ دلار به تومان برای وقتی که API در دسترس نیست. خالی/صفر یعنی «تعیین نشده» و
                اجرای بدون API ناموفق ثبت می‌شود.
              </span>
            </label>

            <label className="block space-y-1.5">
              <span className="text-sm font-medium">فاصلهٔ به‌روزرسانی (دقیقه)</span>
              <div className="flex items-center gap-2">
                <Input
                  dir="ltr"
                  type="number"
                  min={1}
                  max={1440}
                  className="font-mono"
                  value={cfg.update_interval_minutes}
                  onChange={(e) =>
                    patch({ update_interval_minutes: Number(e.target.value) || 1 })
                  }
                />
                <span className="text-xs whitespace-nowrap text-muted-foreground">دقیقه</span>
              </div>
              <span className="block text-xs text-muted-foreground">
                حداقل فاصله بین دو اجرای خودکار (۱ تا ۱۴۴۰ دقیقه).
              </span>
            </label>

            <label className="block space-y-1.5">
              <span className="text-sm font-medium">رند کردن قیمت (تومان)</span>
              <div className="flex items-center gap-2">
                <Input
                  dir="ltr"
                  className="font-mono"
                  value={roundingText ? Number(roundingText).toLocaleString("fa-IR") : ""}
                  onChange={(e) => setRoundingText(toEnglishDigits(e.target.value).replace(/\D/g, ""))}
                  placeholder="مثلاً: ۱۰۰"
                />
                <span className="text-xs whitespace-nowrap text-muted-foreground">تومان</span>
              </div>
              <span className="block text-xs text-muted-foreground">
                قیمت‌ها به نزدیک‌ترین مضرب این عدد رند می‌شوند. مثال: با ۲۰۰، قیمت ۱۱۱٬۶۱۲ به
                ۱۱۱٬۶۰۰ تبدیل می‌شود.
              </span>
            </label>

            <div className="flex items-start justify-between gap-4 sm:pt-6">
              <div>
                <p className="text-sm font-medium">ثبت تاریخچهٔ اجراها</p>
                <p className="text-xs text-muted-foreground">
                  خاموش‌کردن آن فقط ثبت تاریخچه را متوقف می‌کند؛ به‌روزرسانی قیمت‌ها ادامه دارد.
                </p>
              </div>
              <Switch
                checked={cfg.log_enabled}
                onCheckedChange={(v) => patch({ log_enabled: v })}
                aria-label="فعال/غیرفعال کردن ثبت تاریخچهٔ اجراها"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 border-t border-border pt-4">
            <Button onClick={() => void onSave()} disabled={saving} className="gap-2">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              ذخیرهٔ تنظیمات
            </Button>
            <span className="text-xs text-muted-foreground">
              نرخ دستی و مقدار رند در واحد تومان ذخیره و نمایش داده می‌شوند.
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ── History tab ───────────────────────────────────────────────────────────

const HISTORY_PAGE_SIZE = 25;

function RateHistoryTab() {
  const { toast } = useToast();
  const [status, setStatus] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<RateHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [detailItem, setDetailItem] = useState<RateHistoryItem | null>(null);

  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);

  const filters = useCallback(
    (): RateHistoryFilters => ({
      status: status === "all" ? null : (status as "success" | "failed"),
      q: debouncedSearch || null,
      dateFrom: dateFrom || null,
      dateTo: dateTo || null,
    }),
    [status, debouncedSearch, dateFrom, dateTo],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRateHistory({
        ...filters(),
        skip: (page - 1) * HISTORY_PAGE_SIZE,
        limit: HISTORY_PAGE_SIZE,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError("دریافت تاریخچهٔ اجراها ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetPage = () => setPage(1);

  const onExport = async () => {
    setExporting(true);
    try {
      const blob = await exportRateHistory(filters());
      saveBlob(blob, `usd-rate-history-${new Date().toISOString().slice(0, 10)}.csv`);
      toast({ title: "خروجی آماده شد", description: "فایل اکسل (CSV) دانلود شد." });
    } catch {
      toast({
        title: "خطا",
        description: "تهیهٔ خروجی ناموفق بود.",
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  const columns: DataTableColumn<RateHistoryItem>[] = [
    {
      key: "created_at",
      columnLabel: "تاریخ اجرا",
      header: "تاریخ اجرا",
      render: (r) => (
        <span className="text-xs text-muted-foreground">
          {r.created_at ? formatJalaliDateTime(r.created_at) : "—"}
        </span>
      ),
    },
    {
      key: "rate",
      columnLabel: "نرخ",
      header: "نرخ",
      render: (r) => (
        <div>
          <span className="font-mono font-medium">
            {r.rate_rial > 0 ? `${fmtToman(r.rate_rial)} تومان` : "—"}
          </span>
          <div className="text-xs text-muted-foreground">
            {r.rate_source === "api" ? "نوبیتکس" : r.rate_source === "manual" ? "دستی" : "—"}
          </div>
        </div>
      ),
    },
    {
      key: "updated_count",
      columnLabel: "تغییر قیمت",
      header: "تغییر قیمت",
      render: (r) =>
        r.status === "success" ? (
          <span className="font-mono">{toPersianDigits(r.updated_count)}</span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        ),
    },
    {
      key: "kind",
      columnLabel: "نوع",
      header: "نوع",
      hideOnMobile: true,
      render: (r) => (
        <Badge variant="secondary" className="text-[10px]">
          {r.scheduled ? "زمان‌بندی‌شده" : "دستی"}
        </Badge>
      ),
    },
    {
      key: "status",
      columnLabel: "وضعیت",
      header: "وضعیت",
      render: (r) =>
        r.status === "success" ? (
          <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
            <CheckCircle2 className="h-3.5 w-3.5" /> موفق
          </span>
        ) : (
          <span
            className="inline-flex items-center gap-1 text-xs text-destructive"
            title={r.error ?? undefined}
          >
            <AlertTriangle className="h-3.5 w-3.5" /> ناموفق
          </span>
        ),
    },
    {
      key: "details",
      columnLabel: "جزئیات",
      header: "جزئیات",
      hideOnMobile: true,
      render: (r) => {
        const changed = r.details?.changed ?? [];
        if (!changed.length) return <span className="text-xs text-muted-foreground">—</span>;
        return (
          <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => setDetailItem(r)}>
            {toPersianDigits(changed.length)} تغییر
          </Button>
        );
      },
    },
  ];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <History className="h-4 w-4" />
            تاریخچهٔ اجراهای به‌روزرسانی
          </CardTitle>
          <CardDescription>
            هر اجرا با نرخ استفاده‌شده، تعداد قیمت‌های تغییر‌یافته و جزئیات هر تغییر ثبت می‌شود —
            دقیقاً همان گزارش افزونهٔ وردپرس، این‌بار قابل جستجو و خروجی‌گیری.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <FilterSelect
              id="rate-status-filter"
              label="وضعیت اجرا"
              value={status}
              options={[
                { value: "all", label: "همه" },
                { value: "success", label: "موفق" },
                { value: "failed", label: "ناموفق" },
              ]}
              onChange={(v) => {
                setStatus(v);
                resetPage();
              }}
            />
            <label className="block space-y-1.5">
              <span className="block text-[11px] font-medium text-muted-foreground">
                جستجو (کد SKU، نام محصول)
              </span>
              <Input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  resetPage();
                }}
                placeholder="مثلاً SAM-A54-256 یا نام کالا"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="block text-[11px] font-medium text-muted-foreground">از تاریخ</span>
              <JalaliDatePicker
                value={dateFrom}
                onChange={(value) => {
                  setDateFrom(value);
                  resetPage();
                }}
                placeholder="انتخاب تاریخ"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="block text-[11px] font-medium text-muted-foreground">تا تاریخ</span>
              <JalaliDatePicker
                value={dateTo}
                onChange={(value) => {
                  setDateTo(value);
                  resetPage();
                }}
                placeholder="انتخاب تاریخ"
              />
            </label>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-muted-foreground">
              {toPersianDigits(total)} رکورد مطابق فیلترها
            </span>
            <Button
              variant="outline"
              onClick={() => void onExport()}
              disabled={exporting || total === 0}
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileDown className="h-4 w-4" />
              )}
              خروجی CSV
            </Button>
          </div>

          {error ? (
            <p className="py-6 text-center text-sm text-muted-foreground">{error}</p>
          ) : (
            <DataTable<RateHistoryItem>
              columns={columns}
              rows={items}
              rowKey={(r) => r.id}
              columnVisibilityKey="admin.currency.columns"
              loading={loading}
              emptyMessage="هیچ اجرایی با این فیلترها ثبت نشده است."
              serverTotal={total}
              onServerPageChange={(p) => setPage(p)}
            />
          )}
        </CardContent>
      </Card>

      {/* Per-change detail dialog — the plugin's detailed log lines. */}
      <Dialog open={detailItem !== null} onOpenChange={(open) => !open && setDetailItem(null)}>
        <DialogContent className="max-h-[80vh] max-w-3xl overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle>جزئیات تغییر قیمت‌ها</DialogTitle>
            <DialogDescription>
              {detailItem?.created_at ? formatJalaliDateTime(detailItem.created_at) : ""} — نرخ{" "}
              {detailItem ? fmtToman(detailItem.rate_rial) : ""} تومان
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            {(detailItem?.details?.changed ?? []).map((c) => (
              <div
                key={c.variant_id}
                className="rounded-lg border border-border p-3 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{c.product_name || c.sku}</span>
                  <span className="font-mono text-xs text-muted-foreground" dir="ltr">
                    {c.sku}
                  </span>
                </div>
                <div className="mt-1 grid grid-cols-1 gap-1 text-xs text-muted-foreground sm:grid-cols-3">
                  <span dir="ltr" className="font-mono">
                    ${c.usd_price}
                    {c.usd_sale_price ? ` / $${c.usd_sale_price}` : ""}
                  </span>
                  <span>
                    قیمت قبلی: <span className="font-mono">{fmtToman(c.old_price)}</span> تومان
                  </span>
                  <span>
                    قیمت جدید:{" "}
                    <span className="font-mono text-foreground">{fmtToman(c.new_price)}</span> تومان
                  </span>
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function CurrencyAdminPage() {
  return (
    <div className="space-y-6" dir="rtl">
      <div>
        <h1 className="text-2xl font-bold text-foreground">به‌روزرسانی خودکار قیمت دلاری</h1>
        <p className="text-sm text-muted-foreground">
          قیمت کالاهای دلاری بر اساس نرخ لحظه‌ای تتر نوبیتکس (یا نرخ دستی) به‌صورت خودکار به تومان
          تبدیل و در کاتالوگ اعمال می‌شود.
        </p>
      </div>

      {/* Radix Tabs renders its root with dir="ltr" when the prop is absent,
          which flips every descendant back to LTR — the switches landed on
          the left and the status columns read right-to-left. The referrals
          page carries the same explicit dir for the same reason. */}
      <Tabs defaultValue="settings" dir="rtl">
        <TabsList>
          <TabsTrigger value="settings">تنظیمات</TabsTrigger>
          <TabsTrigger value="history">تاریخچهٔ اجراها</TabsTrigger>
        </TabsList>
        <TabsContent value="settings" className="mt-4">
          <SettingsTab />
        </TabsContent>
        <TabsContent value="history" className="mt-4">
          <RateHistoryTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
