"use client";

import { useState } from "react";
import { Percent, Plus, RefreshCw } from "lucide-react";
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
  DISCOUNT_SCOPES,
  DISCOUNT_SCOPE_LABELS,
  DISCOUNT_TYPES,
  DISCOUNT_TYPE_LABELS,
  basisPointsToPercent,
  createDiscount,
  discountScopeLabel,
  discountTypeLabel,
  fetchDiscounts,
  percentToBasisPoints,
  updateDiscount,
  type Discount,
} from "@/lib/api/discounts";

const DISCOUNTS_QUERY_KEY = "admin-discounts" as const;

const TYPE_BADGE_VARIANTS: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  fixed: "default",
  percentage: "secondary",
  first_order: "outline",
};

const EMPTY_FORM = {
  name: "",
  type: "percentage",
  // For `percentage` this is a percent; for `fixed` it is rials.
  value: "",
  minCartAmount: "",
  maxDiscount: "",
  scope: "global",
  startsAt: "",
  endsAt: "",
  isActive: true,
  isStackable: false,
  usageLimit: "",
  priority: "0",
};

function todayInput(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Discount rules and coupons (admin).
 *
 * One unit rule drives this whole page: for a `percentage` discount the stored
 * `value` is BASIS POINTS (1000 = 10%), while for `fixed` it is integer rials.
 * The form always collects a human value — percent for percentage, rials for
 * fixed — and converts once at the call site. Showing the raw stored number
 * would display "1000" for a 10% discount.
 *
 * `min_cart_amount` and `max_discount` are integer rials and are never summed,
 * averaged, or floated on the client.
 */
export default function AdminDiscountsPage() {
  const [includeInactive, setIncludeInactive] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Discount | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const runMutation = useAdminMutation();

  const { data, loading, error, reload } = useAdminQuery({
    queryKey: [DISCOUNTS_QUERY_KEY, includeInactive],
    queryFn: () => fetchDiscounts({ includeInactive, pageSize: 100 }),
    fallbackError: "دریافت فهرست تخفیف‌ها ناموفق بود",
  });
  const discounts: Discount[] = data?.items ?? [];
  const missingCount = data?.missingCount ?? null;
  const invalidCount = data?.invalidCount ?? 0;

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM, startsAt: todayInput() });
    setFormError(null);
    setDialogOpen(true);
  };

  const openEdit = (discount: Discount) => {
    setEditing(discount);
    setForm({
      name: discount.name,
      type: discount.type,
      // Convert the stored basis points back to the percent the operator typed.
      value:
        discount.type === "percentage"
          ? String(basisPointsToPercent(discount.value) ?? "")
          : String(discount.value ?? ""),
      minCartAmount: discount.minCartAmount === null ? "" : String(discount.minCartAmount),
      maxDiscount: discount.maxDiscount === null ? "" : String(discount.maxDiscount),
      scope: discount.scope,
      startsAt: discount.startsAt ? discount.startsAt.slice(0, 10) : "",
      endsAt: discount.endsAt ? discount.endsAt.slice(0, 10) : "",
      isActive: discount.isActive,
      isStackable: discount.isStackable,
      usageLimit: discount.usageLimit === null ? "" : String(discount.usageLimit),
      priority: String(discount.priority ?? 0),
    });
    setFormError(null);
    setDialogOpen(true);
  };

  const submit = async () => {
    setFormError(null);

    const rawValue = Number(form.value);
    if (!Number.isFinite(rawValue) || rawValue <= 0) {
      setFormError("مقدار تخفیف باید عددی بزرگ‌تر از صفر باشد.");
      return;
    }
    if (!form.name.trim()) {
      setFormError("نام تخفیف الزامی است.");
      return;
    }
    if (!form.startsAt || !form.endsAt) {
      setFormError("بازه اعتبار (از تاریخ و تا تاریخ) الزامی است.");
      return;
    }
    // Basis points only for a percentage rule; rials otherwise. Truncated, not
    // rounded: both units are integers and rounding a money value is banned.
    const storedValue =
      form.type === "percentage" ? percentToBasisPoints(rawValue) : Math.trunc(rawValue);

    const minCartAmount = form.minCartAmount.trim()
      ? Math.trunc(Number(form.minCartAmount))
      : null;
    const maxDiscount = form.maxDiscount.trim()
      ? Math.trunc(Number(form.maxDiscount))
      : null;
    const usageLimit = form.usageLimit.trim()
      ? Math.trunc(Number(form.usageLimit))
      : null;
    const priority = Number.parseInt(form.priority || "0", 10) || 0;

    setSaving(true);
    const result = await runMutation(
      () => {
        const payload = {
          name: form.name.trim(),
          type: form.type,
          value: storedValue,
          minCartAmount,
          maxDiscount,
          scope: form.scope,
          startsAt: new Date(form.startsAt).toISOString(),
          endsAt: new Date(`${form.endsAt}T23:59:59`).toISOString(),
          isActive: form.isActive,
          isStackable: form.isStackable,
          usageLimit,
          priority,
        };
        return editing
          ? updateDiscount(editing.id, payload)
          : createDiscount(payload);
      },
      { fallbackError: editing ? "ویرایش تخفیف ناموفق بود" : "ایجاد تخفیف ناموفق بود" },
    );
    if (result.ok) {
      setDialogOpen(false);
      await reload();
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const setActive = async (discount: Discount, isActive: boolean) => {
    setActionError(null);
    const result = await runMutation(
      () => updateDiscount(discount.id, { isActive }),
      { fallbackError: "تغییر وضعیت تخفیف ناموفق بود" },
    );
    if (result.ok) await reload();
    else setActionError(result.error);
  };

  const columns: DataTableColumn<Discount>[] = [
    {
      key: "name",
      header: "نام",
      render: (d) => <span className="font-medium text-foreground">{d.name}</span>,
    },
    {
      key: "type",
      header: "نوع",
      render: (d) => (
        <Badge variant={TYPE_BADGE_VARIANTS[d.type] ?? "outline"}>
          {discountTypeLabel(d.type)}
        </Badge>
      ),
    },
    {
      key: "value",
      header: "مقدار",
      render: (d) => {
        if (d.value === null) return <UnavailableValue reason="گزارش نشد." />;
        if (d.type === "percentage") {
          const percent = basisPointsToPercent(d.value);
          return (
            <span className="font-mono">
              {toPersianDigits(String(percent ?? ""))}٪
            </span>
          );
        }
        return <span className="font-mono">{formatRial(d.value)}</span>;
      },
    },
    {
      key: "scope",
      header: "دامنه",
      hideOnMobile: true,
      render: (d) => discountScopeLabel(d.scope),
    },
    {
      key: "period",
      header: "بازه اعتبار",
      hideOnMobile: true,
      render: (d) => (
        <span className="text-xs text-muted-foreground">
          {formatJalali(d.startsAt)} ← {formatJalali(d.endsAt)}
        </span>
      ),
    },
    {
      key: "usage",
      header: "مصرف",
      hideOnMobile: true,
      render: (d) => (
        <span className="font-mono text-xs">
          {d.usageCount === null ? "—" : toPersianDigits(String(d.usageCount))}
          {d.usageLimit === null ? "" : ` / ${toPersianDigits(String(d.usageLimit))}`}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (d) =>
        d.isActive ? (
          <Badge variant="success">فعال</Badge>
        ) : (
          <Badge variant="outline">غیرفعال</Badge>
        ),
    },
    {
      key: "actions",
      header: "",
      render: (d) => (
        <div className="flex gap-1">
          <Button variant="outline" size="sm" onClick={() => openEdit(d)}>
            ویرایش
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void setActive(d, !d.isActive)}
          >
            {d.isActive ? "غیرفعال" : "فعال"}
          </Button>
        </div>
      ),
    },
  ];

  const isPercentage = form.type === "percentage";

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Percent className="h-5 w-5 text-primary" />
            تخفیف‌ها و کدهای تخفیف
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            قواعد تخفیف تاریخ‌دار با دامنه سراسری یا محدود به کالا، دسته‌بندی،
            برند یا کاربر. مبلغ ثابت به ریال و تخفیف درصدی بر پایه واحد پایه ذخیره
            می‌شود.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void reload()}>
            <RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی
          </Button>
          <Button onClick={openCreate}>
            <Plus className="ms-1 h-4 w-4" /> تخفیف جدید
          </Button>
        </div>
      </section>

      <Card className="p-4">
        <div className="max-w-xs">
          <FilterSelect
            id="discount-status-filter"
            label="نمایش"
            value={includeInactive ? "all" : "active"}
            options={[
              { value: "active", label: "فقط فعال‌ها" },
              { value: "all", label: "همه (شامل غیرفعال)" },
            ]}
            onChange={(v) => setIncludeInactive(v === "all")}
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

      <PartialDataNotice count={invalidCount} label="تخفیف‌های بازگشتی" />
      <MissingDataNotice count={missingCount ?? 0} label="تخفیف‌ها" />

      <DataTable
        columns={columns}
        rows={discounts}
        rowKey={(d) => d.id}
        loading={loading}
        error={error}
        emptyMessage="تخفیفی ثبت نشده است"
        emptyDescription="برای اعمال تخفیف روی سبد خرید، نخستین قاعده تخفیف را ایجاد کنید."
      />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editing ? "ویرایش تخفیف" : "تخفیف جدید"}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3 py-2">
            <div className="col-span-2 space-y-1.5">
              <label
                htmlFor="discount-name"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                نام
              </label>
              <Input
                id="discount-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>

            <FilterSelect
              id="discount-type"
              label="نوع"
              value={form.type}
              disabled={!!editing}
              options={DISCOUNT_TYPES.map((t) => ({
                value: t,
                label: DISCOUNT_TYPE_LABELS[t] ?? t,
              }))}
              onChange={(v) =>
                setForm({ ...form, type: v, value: "" })
              }
            />

            <div className="space-y-1.5">
              <label
                htmlFor="discount-value"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                {isPercentage ? "مقدار (درصد)" : "مقدار (ریال)"}
              </label>
              <Input
                id="discount-value"
                type="number"
                step={isPercentage ? "0.01" : "1"}
                value={form.value}
                onChange={(e) => setForm({ ...form, value: e.target.value })}
                dir="ltr"
                className="font-mono"
              />
              {!isPercentage && form.value.trim() && Number(form.value) > 0 && (
                <p className="text-[11px] text-muted-foreground">
                  {formatRial(Math.trunc(Number(form.value)))}
                </p>
              )}
            </div>

            <FilterSelect
              id="discount-scope"
              label="دامنه"
              value={form.scope}
              options={DISCOUNT_SCOPES.map((s) => ({
                value: s,
                label: DISCOUNT_SCOPE_LABELS[s] ?? s,
              }))}
              onChange={(v) => setForm({ ...form, scope: v })}
            />

            <div className="space-y-1.5">
              <label
                htmlFor="discount-priority"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                اولویت
              </label>
              <Input
                id="discount-priority"
                type="number"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}
                dir="ltr"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="discount-min"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                حداقل مبلغ سبد (ریال)
              </label>
              <Input
                id="discount-min"
                type="number"
                value={form.minCartAmount}
                onChange={(e) => setForm({ ...form, minCartAmount: e.target.value })}
                dir="ltr"
                className="font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="discount-max"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                سقف تخفیف (ریال)
              </label>
              <Input
                id="discount-max"
                type="number"
                value={form.maxDiscount}
                onChange={(e) => setForm({ ...form, maxDiscount: e.target.value })}
                dir="ltr"
                className="font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="discount-from"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                از تاریخ
              </label>
              <Input
                id="discount-from"
                type="date"
                value={form.startsAt}
                onChange={(e) => setForm({ ...form, startsAt: e.target.value })}
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="discount-to"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                تا تاریخ
              </label>
              <Input
                id="discount-to"
                type="date"
                value={form.endsAt}
                onChange={(e) => setForm({ ...form, endsAt: e.target.value })}
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="discount-usage-limit"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                سقف تعداد استفاده
              </label>
              <Input
                id="discount-usage-limit"
                type="number"
                value={form.usageLimit}
                onChange={(e) => setForm({ ...form, usageLimit: e.target.value })}
                dir="ltr"
                placeholder="بدون محدودیت"
              />
            </div>

            <div className="col-span-2 flex flex-wrap gap-5 pt-1">
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={form.isActive}
                  onChange={(e) => setForm({ ...form, isActive: e.target.checked })}
                />
                فعال
              </label>
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={form.isStackable}
                  onChange={(e) => setForm({ ...form, isStackable: e.target.checked })}
                />
                قابل ترکیب با سایر تخفیف‌ها
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
    </div>
  );
}
