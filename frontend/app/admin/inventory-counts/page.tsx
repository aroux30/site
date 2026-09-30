"use client";

import { useState } from "react";
import Link from "next/link";
import { ClipboardCheck, Plus, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { toPersianDigits } from "@/lib/utils";
import {
  inventoryOperationsApi,
  type StockCount,
  type StockCountScope,
  type StockCountStatus,
} from "@/lib/api/inventory-operations";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const COUNTS_QUERY_KEY = "admin-inventory-counts" as const;

const STATUS: Record<StockCountStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  counting: { label: "در حال شمارش", variant: "secondary" },
  review: { label: "آماده بررسی", variant: "default" },
  posted: { label: "ثبت‌شده", variant: "default" },
  cancelled: { label: "لغوشده", variant: "destructive" },
};

function dateText(value: string | null): string {
  return value ? new Date(value).toLocaleString("fa-IR") : "—";
}

export default function InventoryCountsPage() {
  const [formError, setFormError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [warehouseId, setWarehouseId] = useState("");
  const [scope, setScope] = useState<StockCountScope>("full");
  const [scopeValue, setScopeValue] = useState("");

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [COUNTS_QUERY_KEY],
    queryFn: () => inventoryOperationsApi.listCounts(),
    fallbackError: "دریافت فهرست شمارش‌ها ناموفق بود",
  });
  const items: StockCount[] = data?.items ?? [];
  const runMutation = useAdminMutation();

  const create = async () => {
    const scopeFilter = scope === "category"
      ? { category_id: scopeValue.trim() }
      : scope === "product-list"
        ? { product_variant_ids: scopeValue.split(/[\s,]+/).filter(Boolean) }
        : undefined;
    setCreating(true);
    setFormError(null);
    // No cache invalidation: a successful create navigates away to the new
    // session, and the old code never refetched this list either.
    const result = await runMutation(
      () =>
        inventoryOperationsApi.createCount({
          warehouse_id: warehouseId.trim() || undefined,
          scope,
          scope_filter: scopeFilter,
        }),
      { fallbackError: "ایجاد شمارش موجودی ناموفق بود" },
    );
    if (result.ok) {
      window.location.assign(`/admin/inventory-counts/${result.data.id}`);
    } else {
      setFormError(result.error);
      setCreating(false);
    }
  };

  const columns: DataTableColumn<StockCount>[] = [
    {
      key: "id",
      header: "شناسه جلسه",
      render: (count) => <span className="font-mono text-xs">{count.id.slice(0, 8)}</span>,
    },
    {
      key: "status",
      header: "وضعیت",
      render: (count) => <Badge variant={STATUS[count.status].variant}>{STATUS[count.status].label}</Badge>,
    },
    {
      key: "progress",
      header: "پیشرفت شمارش",
      render: (count) => (
        <span>{toPersianDigits(`${count.counted_line_count} از ${count.line_count}`)}</span>
      ),
    },
    {
      key: "variance",
      header: "اختلاف",
      hideOnMobile: true,
      render: (count) => (
        <span className={count.variance_line_count ? "font-medium text-amber-700 dark:text-amber-400" : ""}>
          {toPersianDigits(`${count.variance_line_count} ردیف / ${count.variance_quantity} واحد`)}
        </span>
      ),
    },
    {
      key: "created",
      header: "تاریخ ایجاد",
      hideOnMobile: true,
      render: (count) => <span className="text-xs text-muted-foreground">{dateText(count.created_at)}</span>,
    },
    {
      key: "action",
      header: "",
      render: (count) => (
        <Button asChild variant="outline" size="sm">
          <Link href={`/admin/inventory-counts/${count.id}`}>باز کردن</Link>
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <ClipboardCheck className="h-5 w-5 text-primary" />
            شمارش فیزیکی موجودی
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            موجودی قابل‌فروش هر انبار را در یک نقطه زمانی ثبت، بررسی و از طریق دفتر تراکنش اصلاح کنید.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void load()}>
            <RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی
          </Button>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="ms-1 h-4 w-4" /> شروع شمارش
          </Button>
        </div>
      </section>

{formError && <div role="alert" className="text-sm text-destructive">{formError}</div>}
            <DataTable
        columns={columns}
        rows={items}
        rowKey={(count) => count.id}
        loading={loading}
        error={error}
        emptyMessage="جلسه شمارش فعالی وجود ندارد"
        emptyDescription="برای ثبت وضعیت واقعی انبار، یک جلسه شمارش جدید ایجاد کنید."
      />

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent dir="rtl">
          <DialogHeader><DialogTitle>شروع جلسه شمارش موجودی</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="countWarehouse">شناسه انبار</Label>
              <Input id="countWarehouse" value={warehouseId} onChange={(event) => setWarehouseId(event.target.value)} placeholder="خالی = انبار مرکزی" dir="ltr" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="countScope">دامنه شمارش</Label>
              <select
                id="countScope"
                value={scope}
                onChange={(event) => { setScope(event.target.value as StockCountScope); setScopeValue(""); }}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="full">کل موجودی انبار</option>
                <option value="category">یک دسته‌بندی</option>
                <option value="product-list">فهرست واریانت‌ها</option>
              </select>
            </div>
            {scope !== "full" && (
              <div className="space-y-1.5">
                <Label htmlFor="scopeValue">
                  {scope === "category" ? "شناسه دسته‌بندی" : "شناسه واریانت‌ها (با کاما جدا کنید)"}
                </Label>
                <Input id="scopeValue" value={scopeValue} onChange={(event) => setScopeValue(event.target.value)} dir="ltr" />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>انصراف</Button>
            <Button disabled={creating || (scope !== "full" && !scopeValue.trim())} onClick={() => void create()}>
              {creating ? "در حال ایجاد..." : "ایجاد جلسه"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
