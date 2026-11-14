"use client";

/**
 * Admin — برنامه دعوت دوستان (referral & bonus program).
 *
 * Two tabs:
 * - «تنظیمات» — one config object (SiteSetting `referrals.config`). Money is
 *   integer Rial on the wire, displayed in Toman; percents accept up to two
 *   decimals. The «شروع برنامه» stamp is read-only: the backend refreshes it
 *   on every activation (off → on), so the off period is never paid.
 * - «تاریخچهٔ پاداش‌ها» — the audit view: every reward the program has paid
 *   (from the wallet ledger), filterable by kind, showing who received it,
 *   for whom / which order / which top-up, and when.
 *
 * Rewards are paid eagerly at the event; there is no manual sweep button —
 * the periodic background task only retries failures.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { FileDown, Gift, History, Loader2, RefreshCw, Save, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { JalaliDatePicker } from "@/components/ui/jalali-datepicker";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { FilterSelect } from "@/components/admin/filter-select";
import { formatJalali, formatJalaliDateTime } from "@/lib/date";
import { toPersianDigits } from "@/lib/utils";
import {
  exportRewardHistory,
  fetchReferralConfig,
  fetchRewardHistory,
  updateReferralConfig,
  REWARD_KIND_LABELS,
  type ReferralProgramConfig,
  type RewardHistoryFilters,
  type RewardHistoryItem,
  type RewardKind,
} from "@/lib/api/referrals-admin";
import { saveBlob } from "@/lib/api/data-exchange";

/** Rial → Toman display (store convention: 1 Toman = 10 Rial). */
function fmtToman(rial: number): string {
  return Math.trunc(rial / 10).toLocaleString("fa-IR");
}

/** Toman input → Rial for the wire. */
function tomanToRial(toman: string): number {
  const n = Number(toman.replace(/[^\d]/g, ""));
  return Number.isFinite(n) ? n * 10 : 0;
}

interface AmountFieldProps {
  label: string;
  hint?: string;
  rial: number;
  onChange: (rial: number) => void;
  disabled?: boolean;
}

function AmountField({ label, hint, rial, onChange, disabled }: AmountFieldProps) {
  const [text, setText] = useState(String(Math.trunc(rial / 10)));
  useEffect(() => setText(String(Math.trunc(rial / 10))), [rial]);
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      <div className="flex items-center gap-2">
        <Input
          dir="ltr"
          className="font-mono"
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => onChange(tomanToRial(text))}
        />
        <span className="text-muted-foreground text-xs whitespace-nowrap">تومان</span>
      </div>
      {hint ? <span className="text-muted-foreground block text-xs">{hint}</span> : null}
    </label>
  );
}

interface PercentFieldProps {
  label: string;
  hint?: string;
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}

/** A percent text is acceptable while typing: at most two decimal digits. */
const PERCENT_INPUT_RE = /^\d{0,3}(\.\d{0,2})?$/;

function PercentField({ label, hint, value, onChange, disabled }: PercentFieldProps) {
  // Text state (not number): a number input silently accepts a third
  // decimal digit and rounds on read. Keeping the raw text lets us refuse
  // the third digit at the keystroke instead of rewriting the operator's
  // value after the fact.
  const [text, setText] = useState(formatPercentText(value));
  const focusedRef = useRef(false);
  useEffect(() => {
    // Adopt server value only while the field is not being edited.
    if (!focusedRef.current) setText(formatPercentText(value));
  }, [value]);

  const commit = (raw: string) => {
    if (raw === "" || raw === ".") {
      onChange(0);
      return;
    }
    const n = Number(raw);
    if (!Number.isFinite(n)) {
      onChange(0);
      return;
    }
    onChange(Math.max(0, Math.min(100, Math.round(n * 100) / 100)));
  };

  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      <div className="flex items-center gap-2">
        <Input
          dir="ltr"
          className="font-mono"
          type="text"
          inputMode="decimal"
          value={text}
          disabled={disabled}
          onFocus={() => {
            focusedRef.current = true;
          }}
          onBlur={() => {
            focusedRef.current = false;
            commit(text);
            setText(formatPercentText(Math.max(0, Math.min(100, Math.round(Number(text || 0) * 100) / 100))));
          }}
          onChange={(e) => {
            const raw = e.target.value.trim();
            // Refuse a third decimal digit (and any non-numeric text) by
            // leaving the field unchanged — the keystroke never lands.
            if (!PERCENT_INPUT_RE.test(raw)) return;
            setText(raw);
            commit(raw);
          }}
        />
        <span className="text-muted-foreground text-xs whitespace-nowrap">درصد</span>
      </div>
      {hint ? <span className="text-muted-foreground block text-xs">{hint}</span> : null}
    </label>
  );
}

/** Display helper: 1.25 → "1.25", 2 → "2", 0.5 → "0.5". */
function formatPercentText(value: number): string {
  if (!Number.isFinite(value)) return "0";
  return String(Math.round(value * 100) / 100);
}

// ── History tab ───────────────────────────────────────────────────────────

const HISTORY_PAGE_SIZE = 50;

function RewardHistoryTab() {
  const { toast } = useToast();
  const [kind, setKind] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<RewardHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  // Debounce the free-text search so a page is not refetched per keystroke.
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);

  const filters = useCallback(
    (): RewardHistoryFilters => ({
      kind: kind === "all" ? null : (kind as RewardKind),
      q: debouncedSearch || null,
      dateFrom: dateFrom || null,
      dateTo: dateTo || null,
    }),
    [kind, debouncedSearch, dateFrom, dateTo],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRewardHistory({
        ...filters(),
        skip: (page - 1) * HISTORY_PAGE_SIZE,
        limit: HISTORY_PAGE_SIZE,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError("دریافت تاریخچهٔ پاداش‌ها ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    void load();
  }, [load]);

  // A new filter means a new result set — page 5 of the old one is meaningless.
  const resetPage = () => setPage(1);

  const onExport = async () => {
    setExporting(true);
    try {
      const blob = await exportRewardHistory(filters());
      saveBlob(blob, `referral-rewards-${new Date().toISOString().slice(0, 10)}.csv`);
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

  const columns: DataTableColumn<RewardHistoryItem>[] = [
    {
      key: "kind",
      columnLabel: "نوع پاداش",
      header: "نوع پاداش",
      render: (r) => <Badge variant="secondary">{REWARD_KIND_LABELS[r.kind]}</Badge>,
    },
    {
      key: "earner",
      columnLabel: "گیرنده",
      header: "گیرنده",
      render: (r) => (
        <div>
          <div className="font-medium text-foreground">{r.earner_name}</div>
          {r.earner_phone ? (
            <div className="text-xs text-muted-foreground" dir="ltr">
              {toPersianDigits(r.earner_phone)}
            </div>
          ) : null}
        </div>
      ),
    },
    {
      key: "level",
      columnLabel: "لایه",
      header: "لایه",
      hideOnMobile: true,
      render: (r) =>
        r.kind === "recharge_bonus" ? (
          <span className="text-xs text-muted-foreground">—</span>
        ) : (
          <span className="text-xs">لایهٔ {toPersianDigits(r.level ?? 1)}</span>
        ),
    },
    {
      key: "reason",
      columnLabel: "بابت",
      header: "بابت",
      render: (r) => {
        if (r.kind === "signup_gift") {
          return (
            <span className="text-xs">
              {r.invited_user_name
                ? `عضویت «${r.invited_user_name}» با لینک دعوت`
                : "عضویت با لینک دعوت"}
            </span>
          );
        }
        if (r.kind === "commission") {
          return (
            <span className="text-xs">
              سفارش{" "}
              <span className="font-mono" dir="ltr">
                {r.order_number ?? "—"}
              </span>
              {r.payment_amount != null ? (
                <span className="text-muted-foreground">
                  {" "}
                  (مبلغ سفارش: {fmtToman(r.payment_amount)} تومان)
                </span>
              ) : null}
            </span>
          );
        }
        return (
          <span className="text-xs">
            شارژ کیف پول
            {r.payment_amount != null ? (
              <span className="text-muted-foreground"> (مبلغ شارژ: {fmtToman(r.payment_amount)} تومان)</span>
            ) : null}
          </span>
        );
      },
    },
    {
      key: "amount",
      columnLabel: "مبلغ",
      header: "مبلغ",
      // Toman on this page: the settings inputs above are in Toman, so the
      // history must use the same unit or the operator reads two units in
      // one screen (the money-unit trap).
      render: (r) => (
        <span className="font-mono font-medium">{fmtToman(r.amount)} تومان</span>
      ),
    },
    {
      key: "created_at",
      columnLabel: "تاریخ",
      header: "تاریخ",
      hideOnMobile: true,
      render: (r) => (
        <span className="text-xs text-muted-foreground">
          {r.created_at ? formatJalaliDateTime(r.created_at) : "—"}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <History className="h-4 w-4" />
            تاریخچهٔ پاداش‌ها
          </CardTitle>
          <CardDescription>
            هر پاداشی که برنامه پرداخت کرده است — چه چیزی، برای کی، بابت چه و چه زمانی.
            پرداخت‌ها در لحظهٔ رویداد انجام می‌شوند (ثبت‌نام، تکمیل سفارش، شارژ کیف پول).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <FilterSelect
              id="reward-kind-filter"
              label="نوع پاداش"
              value={kind}
              options={[
                { value: "all", label: "همه" },
                { value: "signup_gift", label: REWARD_KIND_LABELS.signup_gift },
                { value: "commission", label: REWARD_KIND_LABELS.commission },
                { value: "recharge_bonus", label: REWARD_KIND_LABELS.recharge_bonus },
              ]}
              onChange={(v) => {
                setKind(v);
                resetPage();
              }}
            />
            <label className="block space-y-1.5">
              <span className="text-muted-foreground block text-[11px] font-medium">
                جستجو (نام، شماره، شمارهٔ سفارش)
              </span>
              <Input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  resetPage();
                }}
                placeholder="مثلاً ۰۹۱۲… یا نام کاربر یا TEST-…"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-muted-foreground block text-[11px] font-medium">از تاریخ</span>
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
              <span className="text-muted-foreground block text-[11px] font-medium">تا تاریخ</span>
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
            <span className="text-muted-foreground text-xs">
              {toPersianDigits(total)} رکورد مطابق فیلترها
            </span>
            <Button variant="outline" onClick={() => void onExport()} disabled={exporting || total === 0}>
              {exporting ? (
                <Loader2 className="me-2 h-4 w-4 animate-spin" />
              ) : (
                <FileDown className="me-2 h-4 w-4" />
              )}
              خروجی اکسل (CSV)
            </Button>
          </div>
        </CardContent>
      </Card>

      <DataTable
        columns={columns}
        rows={items}
        rowKey={(r) => r.id}
        loading={loading}
        error={error}
        emptyMessage="هنوز پاداشی پرداخت نشده است."
        emptyDescription="با فعال‌کردن برنامه و ثبت رویدادها (ثبت‌نام با لینک دعوت، خرید، شارژ)، اینجا پر می‌شود."
        pageSize={HISTORY_PAGE_SIZE}
        serverTotal={total}
        onServerPageChange={(p) => setPage(p)}
        columnVisibilityKey="referrals-history-columns"
      />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function AdminReferralsPage() {
  const { toast } = useToast();
  const [config, setConfig] = useState<ReferralProgramConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setConfig(await fetchReferralConfig());
    } catch (err) {
      setError("بارگذاری تنظیمات برنامه دعوت ناموفق بود.");
      void err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const set = <K extends keyof ReferralProgramConfig>(key: K, value: ReferralProgramConfig[K]) => {
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const onSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const saved = await updateReferralConfig(config);
      setConfig(saved);
      toast({ title: "ذخیره شد", description: "تنظیمات برنامه دعوت ذخیره شد." });
    } catch {
      toast({
        title: "خطا",
        description: "ذخیره تنظیمات ناموفق بود.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24" dir="rtl">
        <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className="space-y-4 py-12 text-center" dir="rtl">
        <p className="text-destructive text-sm">{error ?? "خطای نامشخص"}</p>
        <Button variant="outline" onClick={() => void load()}>
          <RefreshCw className="me-2 h-4 w-4" />
          تلاش دوباره
        </Button>
      </div>
    );
  }

  const payoutsConfigured =
    (config.gift_enabled && (config.signup_gift_l1 > 0 || config.signup_gift_l2 > 0)) ||
    (config.commission_enabled &&
      (config.commission_percent_l1 > 0 || config.commission_percent_l2 > 0)) ||
    (config.recharge_bonus_enabled && config.recharge_bonus_percent > 0);

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <Users className="h-5 w-5" />
            برنامه دعوت دوستان
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            هدیه ثبت‌نام و پورسانت خرید برای معرف‌ها (دو لایه) + بونوس شارژ کیف پول
          </p>
        </div>
      </div>

      <Tabs defaultValue="settings" dir="rtl">
        <TabsList>
          <TabsTrigger value="settings">تنظیمات</TabsTrigger>
          <TabsTrigger value="history">تاریخچهٔ پاداش‌ها</TabsTrigger>
        </TabsList>

        <TabsContent value="settings" className="space-y-6">
          <div className="flex justify-end">
            <Button onClick={() => void onSave()} disabled={saving}>
              {saving ? <Loader2 className="me-2 h-4 w-4 animate-spin" /> : <Save className="me-2 h-4 w-4" />}
              ذخیره
            </Button>
          </div>

          {/* Program status */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">وضعیت برنامه</CardTitle>
              <CardDescription>
                این سوئیچ اصلی، کل برنامه را یکجا خاموش/روشن می‌کند. برای خاموش‌کردن
                فقط یک بخش (مثلاً هدیهٔ ثبت‌نام) از سوئیچ همان کارت پایین‌تر استفاده کنید.
                با هر بار فعال‌کردن برنامه، «شروع برنامه» به‌روز می‌شود و فقط
                دعوت‌ها/سفارش‌های بعد از آن مشمول پاداش می‌شوند — پس دورهٔ خاموشی هنگام
                روشن‌شدن دوباره پرداخت نمی‌شود.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">فعال بودن کل برنامه</span>
                <Switch
                  checked={config.enabled}
                  onCheckedChange={(v) => set("enabled", v)}
                />
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">شروع برنامه:</span>
                {config.program_started_at ? (
                  <Badge variant="secondary">{formatJalali(config.program_started_at)}</Badge>
                ) : (
                  <Badge variant="outline">هنوز شروع نشده (مبالغ صفر است)</Badge>
                )}
              </div>
              {!payoutsConfigured && (
                <p className="text-muted-foreground text-xs">
                  برای فعال‌کردن پرداخت، حداقل یکی از مبالغ/درصدهای زیر را غیرصفر کنید.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Signup gifts */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Gift className="h-4 w-4" />
                  هدیهٔ ثبت‌نام (پاداش دعوت)
                </CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-xs">
                    {config.gift_enabled ? "فعال" : "غیرفعال"}
                  </span>
                  <Switch
                    checked={config.gift_enabled}
                    onCheckedChange={(v) => set("gift_enabled", v)}
                    aria-label="فعال/غیرفعال کردن ماژول هدیهٔ ثبت‌نام"
                  />
                </div>
              </div>
              <CardDescription>
                وقتی کاربری با لینک دعوت عضو می‌شود، این مبلغ بلافاصله به کیف پول معرف واریز می‌شود.
                با خاموش‌کردن این سوئیچ، فقط همین ماژول متوقف می‌شود (پورسانت و بونوس شارژ
                دست‌نخورده می‌مانند).
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <AmountField
                label="هدیه لایه اول (معرف مستقیم)"
                rial={config.signup_gift_l1}
                onChange={(v) => set("signup_gift_l1", v)}
              />
              <AmountField
                label="هدیه لایه دوم (معرفِ معرف)"
                rial={config.signup_gift_l2}
                onChange={(v) => set("signup_gift_l2", v)}
              />
            </CardContent>
          </Card>

          {/* Commission */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">پورسانت خرید (درصدی)</CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-xs">
                    {config.commission_enabled ? "فعال" : "غیرفعال"}
                  </span>
                  <Switch
                    checked={config.commission_enabled}
                    onCheckedChange={(v) => set("commission_enabled", v)}
                    aria-label="فعال/غیرفعال کردن ماژول پورسانت خرید"
                  />
                </div>
              </div>
              <CardDescription>
                در ازای هر سفارش تکمیل‌شدهٔ کاربر دعوت‌شده، درصدی از مبلغ سفارش بلافاصله به
                کیف پول معرف واریز می‌شود. با خاموش‌کردن این سوئیچ، پورسانت‌های معلق
                «در انتظار» می‌مانند و با روشن‌کردن دوباره پرداخت می‌شوند.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <PercentField
                label="درصد پورسانت لایه اول"
                value={config.commission_percent_l1}
                onChange={(v) => set("commission_percent_l1", v)}
              />
              <PercentField
                label="درصد پورسانت لایه دوم"
                value={config.commission_percent_l2}
                onChange={(v) => set("commission_percent_l2", v)}
              />
              <AmountField
                label="سقف هر پورسانت"
                hint="۰ = بدون سقف"
                rial={config.commission_max_per_event}
                onChange={(v) => set("commission_max_per_event", v)}
              />
              <AmountField
                label="حداقل مبلغ سفارش"
                hint="سفارش‌های کمتر از این مبلغ پورسانت نمی‌گیرند (۰ = همه)"
                rial={config.min_order_total}
                onChange={(v) => set("min_order_total", v)}
              />
            </CardContent>
          </Card>

          {/* Recharge bonus */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">بونوس شارژ کیف پول</CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-xs">
                    {config.recharge_bonus_enabled ? "فعال" : "غیرفعال"}
                  </span>
                  <Switch
                    checked={config.recharge_bonus_enabled}
                    onCheckedChange={(v) => set("recharge_bonus_enabled", v)}
                    aria-label="فعال/غیرفعال کردن ماژول بونوس شارژ"
                  />
                </div>
              </div>
              <CardDescription>
                در ازای هر شارژ کیف پول، درصدی بلافاصله به‌عنوان بونوس به موجودی اضافه می‌شود.
                با خاموش‌کردن این سوئیچ، فقط بونوس شارژ متوقف می‌شود.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <PercentField
                label="درصد بونوس شارژ"
                hint="۰ = خاموش"
                value={config.recharge_bonus_percent}
                onChange={(v) => set("recharge_bonus_percent", v)}
              />
            </CardContent>
          </Card>

          {/* Notifications */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">اعلان‌ها</CardTitle>
              <CardDescription>پیام درون‌برنامه‌ای برای دریافت‌کنندهٔ پاداش.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm">اعلان هدیهٔ ثبت‌نام</span>
                <Switch checked={config.notify_on_gift} onCheckedChange={(v) => set("notify_on_gift", v)} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">اعلان پورسانت خرید</span>
                <Switch
                  checked={config.notify_on_commission}
                  onCheckedChange={(v) => set("notify_on_commission", v)}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">اعلان بونوس شارژ</span>
                <Switch
                  checked={config.notify_on_recharge_bonus}
                  onCheckedChange={(v) => set("notify_on_recharge_bonus", v)}
                />
              </div>
              <label className="block space-y-1">
                <span className="text-sm font-medium">متن اعلان هدیه</span>
                <Input
                  value={config.gift_notif_text}
                  onChange={(e) => set("gift_notif_text", e.target.value)}
                />
                <span className="text-muted-foreground block text-xs">{"{amount}"} = مبلغ به تومان</span>
              </label>
              <label className="block space-y-1">
                <span className="text-sm font-medium">متن اعلان پورسانت</span>
                <Input
                  value={config.commission_notif_text}
                  onChange={(e) => set("commission_notif_text", e.target.value)}
                />
              </label>
              <label className="block space-y-1">
                <span className="text-sm font-medium">متن اعلان بونوس شارژ</span>
                <Input
                  value={config.recharge_bonus_notif_text}
                  onChange={(e) => set("recharge_bonus_notif_text", e.target.value)}
                />
              </label>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <RewardHistoryTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
