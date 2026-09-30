"use client";

import { useState } from "react";
import { Coins, Plus, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { FilterSelect } from "@/components/admin/filter-select";
import {
  MissingDataNotice,
  PartialDataNotice,
  UnavailableValue,
} from "@/components/admin/async-state";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { formatJalali } from "@/lib/date";
import { formatRial, toPersianDigits } from "@/lib/utils";
import {
  CASHBACK_RULE_TYPES,
  CASHBACK_RULE_TYPE_LABELS,
  cashbackRuleTypeLabel,
  createCashbackRule,
  deactivateCashbackRule,
  fetchCashbackRules,
  updateCashbackRule,
  type CashbackRule,
} from "@/lib/api/cashback";

const CASHBACK_RULES_QUERY_KEY = "admin-cashback-rules" as const;

const EMPTY_FORM = {
  name: "",
  type: "category",
  scopeId: "",
  /** Percent, 0 < p <= 100 — NOT basis points. Converted at submit. */
  percentage: "",
  maxAmount: "",
  isActive: true,
  startsAt: "",
  endsAt: "",
};

function todayInput(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Cashback rules (admin).
 *
 * The percentage is the field most easily got wrong on this contract. Writes
 * take `percentage` as a PERCENT; the response returns the stored integer
 * `percentage_bp` (1% = 100 bp). This page always shows and collects percent,
 * reading the backend's own `percentage` field when it is present and deriving
 * from basis points only when it is not — so a displayed rate can never
 * disagree with the stored value.
 *
 * "Deactivate" is a soft-delete: the rule row is kept and only `is_active`
 * flips. The button is labelled accordingly — calling it "delete" would tell
 * an operator the rule is gone when it is still on file.
 *
 * `max_amount` is integer rials.
 */
export default function AdminCashbackPage() {
  const [isActiveFilter, setIsActiveFilter] = useState("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<CashbackRule | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState<CashbackRule | null>(null);

  const runMutation = useAdminMutation();

  const { data, loading, error, reload } = useAdminQuery({
    queryKey: [CASHBACK_RULES_QUERY_KEY, isActiveFilter],
    queryFn: () =>
      fetchCashbackRules({
        limit: 100,
        isActive:
          isActiveFilter === "all" ? undefined : isActiveFilter === "active",
      }),
    fallbackError: "دریافت قواعد کش‌بک ناموفق بود",
  });
  const rules: CashbackRule[] = data?.items ?? [];
  const missingCount = data?.missingCount ?? null;
  const invalidCount = data?.invalidCount ?? 0;

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM, startsAt: todayInput() });
    setFormError(null);
    setDialogOpen(true);
  };

  const openEdit = (rule: CashbackRule) => {
    setEditing(rule);
    setForm({
      name: rule.name,
      type: rule.type,
      scopeId: rule.scopeId ?? "",
      percentage: rule.percentage === null ? "" : String(rule.percentage),
      maxAmount: rule.maxAmount === null ? "" : String(rule.maxAmount),
      isActive: rule.isActive,
      startsAt: rule.startsAt ? rule.startsAt.slice(0, 10) : "",
      endsAt: rule.endsAt ? rule.endsAt.slice(0, 10) : "",
    });
    setFormError(null);
    setDialogOpen(true);
  };

  const submit = async () => {
    setFormError(null);

    const percentage = Number(form.percentage);
    if (!Number.isFinite(percentage) || percentage <= 0 || percentage > 100) {
      setFormError("درصد کش‌بک باید عددی بزرگ‌تر از صفر و حداکثر ۱۰۰ باشد.");
      return;
    }
    if (!form.name.trim()) {
      setFormError("نام قاعده الزامی است.");
      return;
    }
    if (!form.startsAt || !form.endsAt) {
      setFormError("بازه اعتبار (از تاریخ و تا تاریخ) الزامی است.");
      return;
    }

    const maxAmount = form.maxAmount.trim()
      ? Math.trunc(Number(form.maxAmount))
      : null;

    setSaving(true);
    const result = await runMutation(
      () => {
        const payload = {
          name: form.name.trim(),
          type: form.type,
          scopeId: form.scopeId.trim() || null,
          percentage,
          maxAmount,
          isActive: form.isActive,
          startsAt: new Date(form.startsAt).toISOString(),
          endsAt: new Date(`${form.endsAt}T23:59:59`).toISOString(),
        };
        return editing
          ? updateCashbackRule(editing.id, payload)
          : createCashbackRule(payload);
      },
      { fallbackError: editing ? "ویرایش قاعده ناموفق بود" : "ایجاد قاعده ناموفق بود" },
    );
    if (result.ok) {
      setDialogOpen(false);
      await reload();
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const toggleActive = async (rule: CashbackRule) => {
    setActionError(null);
    const result = rule.isActive
      ? await runMutation(() => deactivateCashbackRule(rule.id), {
          fallbackError: "غیرفعال‌سازی قاعده ناموفق بود",
        })
      : await runMutation(() => updateCashbackRule(rule.id, { isActive: true }), {
          fallbackError: "فعال‌سازی قاعده ناموفق بود",
        });
    if (result.ok) await reload();
    else setActionError(result.error);
    setConfirmDeactivate(null);
  };

  const columns: DataTableColumn<CashbackRule>[] = [
    {
      key: "name",
      header: "نام",
      render: (r) => <span className="font-medium text-foreground">{r.name}</span>,
    },
    {
      key: "type",
      header: "نوع",
      render: (r) => (
        <Badge variant="secondary">{cashbackRuleTypeLabel(r.type)}</Badge>
      ),
    },
    {
      key: "percentage",
      header: "درصد",
      render: (r) =>
        r.percentage === null ? (
          <UnavailableValue reason="گزارش نشد." />
        ) : (
          <span className="font-mono">{toPersianDigits(String(r.percentage))}٪</span>
        ),
    },
    {
      key: "max",
      header: "سقف مبلغ",
      hideOnMobile: true,
      render: (r) =>
        r.maxAmount === null ? (
          <span className="text-xs text-muted-foreground">بدون سقف</span>
        ) : (
          <span className="font-mono">{formatRial(r.maxAmount)}</span>
        ),
    },
    {
      key: "scope",
      header: "دامنه",
      hideOnMobile: true,
      render: (r) =>
        r.scopeId ? (
          <span className="font-mono text-xs" dir="ltr">
            {r.scopeId}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">سراسری</span>
        ),
    },
    {
      key: "period",
      header: "بازه اعتبار",
      hideOnMobile: true,
      render: (r) => (
        <span className="text-xs text-muted-foreground">
          {formatJalali(r.startsAt)} ← {formatJalali(r.endsAt)}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (r) =>
        r.isActive ? (
          <Badge variant="success">فعال</Badge>
        ) : (
          <Badge variant="outline">غیرفعال</Badge>
        ),
    },
    {
      key: "actions",
      header: "",
      render: (r) => (
        <div className="flex gap-1">
          <Button variant="outline" size="sm" onClick={() => openEdit(r)}>
            ویرایش
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              r.isActive ? setConfirmDeactivate(r) : void toggleActive(r)
            }
          >
            {r.isActive ? "غیرفعال" : "فعال"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Coins className="h-5 w-5 text-primary" />
            کش‌بک و بازگشت وجه
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            قواعد کش‌بک بر پایه درصد از مبلغ خرید، با سقف اختیاری به ریال. غیرفعال
            کردن قاعده آن را حذف نمی‌کند و سابقه تراکنش‌های پیشین دست‌نخورده
            می‌ماند.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void reload()}>
            <RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی
          </Button>
          <Button onClick={openCreate}>
            <Plus className="ms-1 h-4 w-4" /> قاعده جدید
          </Button>
        </div>
      </section>

      <Card className="p-4">
        <div className="max-w-xs">
          <FilterSelect
            id="cashback-status-filter"
            label="وضعیت"
            value={isActiveFilter}
            options={[
              { value: "all", label: "همه وضعیت‌ها" },
              { value: "active", label: "فعال" },
              { value: "inactive", label: "غیرفعال" },
            ]}
            onChange={setIsActiveFilter}
          />
        </div>
      </Card>

      {actionError && (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
        >
          {actionError}
        </div>
      )}

      <PartialDataNotice count={invalidCount} label="قواعد بازگشتی" />
      <MissingDataNotice count={missingCount ?? 0} label="قواعد کش‌بک" />

      <DataTable
        columns={columns}
        rows={rules}
        rowKey={(r) => r.id}
        loading={loading}
        error={error}
        emptyMessage="قاعده کش‌بکی ثبت نشده است"
        emptyDescription="برای بازگرداندن بخشی از مبلغ خرید به کیف پول مشتری، نخستین قاعده را ایجاد کنید."
      />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editing ? "ویرایش قاعده کش‌بک" : "قاعده کش‌بک جدید"}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3 py-2">
            <div className="col-span-2 space-y-1.5">
              <label
                htmlFor="cashback-name"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                نام
              </label>
              <Input
                id="cashback-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>

            <FilterSelect
              id="cashback-type"
              label="نوع"
              value={form.type}
              options={CASHBACK_RULE_TYPES.map((t) => ({
                value: t,
                label: CASHBACK_RULE_TYPE_LABELS[t] ?? t,
              }))}
              onChange={(v) => setForm({ ...form, type: v })}
            />

            <div className="space-y-1.5">
              <label
                htmlFor="cashback-percentage"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                درصد کش‌بک
              </label>
              <Input
                id="cashback-percentage"
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={form.percentage}
                onChange={(e) => setForm({ ...form, percentage: e.target.value })}
                dir="ltr"
                className="font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="cashback-max"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                سقف مبلغ (ریال)
              </label>
              <Input
                id="cashback-max"
                type="number"
                value={form.maxAmount}
                onChange={(e) => setForm({ ...form, maxAmount: e.target.value })}
                dir="ltr"
                className="font-mono"
                placeholder="بدون سقف"
              />
              {form.maxAmount.trim() && Number(form.maxAmount) > 0 && (
                <p className="text-[11px] text-muted-foreground">
                  {formatRial(Math.trunc(Number(form.maxAmount)))}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="cashback-scope"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                شناسه دامنه (اختیاری)
              </label>
              <Input
                id="cashback-scope"
                value={form.scopeId}
                onChange={(e) => setForm({ ...form, scopeId: e.target.value })}
                dir="ltr"
                className="font-mono"
                placeholder="خالی = سراسری"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="cashback-from"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                از تاریخ
              </label>
              <Input
                id="cashback-from"
                type="date"
                value={form.startsAt}
                onChange={(e) => setForm({ ...form, startsAt: e.target.value })}
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="cashback-to"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                تا تاریخ
              </label>
              <Input
                id="cashback-to"
                type="date"
                value={form.endsAt}
                onChange={(e) => setForm({ ...form, endsAt: e.target.value })}
              />
            </div>

            <div className="col-span-2 pt-1">
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={form.isActive}
                  onChange={(e) => setForm({ ...form, isActive: e.target.checked })}
                />
                فعال
              </label>
            </div>
          </div>

          {formError && (
            <p role="alert" className="text-sm text-destructive">
              {formError}
            </p>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              انصراف
            </Button>
            <Button disabled={saving} onClick={() => void submit()}>
              {saving ? "در حال ذخیره..." : "ذخیره"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Deactivation is soft — say so before it happens. */}
      <Dialog
        open={confirmDeactivate !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmDeactivate(null);
        }}
      >
        <DialogContent dir="rtl">
          <DialogHeader>
            <DialogTitle>غیرفعال‌سازی قاعده کش‌بک</DialogTitle>
          </DialogHeader>
          <p className="py-2 text-sm leading-6 text-muted-foreground">
            قاعده «{confirmDeactivate?.name}» غیرفعال می‌شود و از این پس روی
            خریدهای جدید اعمال نخواهد شد. این قاعده حذف نمی‌شود و سابقه
            تراکنش‌های کش‌بک پیشین دست‌نخورده باقی می‌ماند.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDeactivate(null)}>
              انصراف
            </Button>
            <Button
              variant="destructive"
              onClick={() => confirmDeactivate && void toggleActive(confirmDeactivate)}
            >
              غیرفعال کن
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
