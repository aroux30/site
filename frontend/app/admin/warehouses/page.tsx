"use client";

import { useMemo, useState } from "react";
import { Pencil, Plus, RefreshCw, Star, Warehouse as WarehouseIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toPersianDigits } from "@/lib/utils";
import {
  warehousesApi,
  type Warehouse,
  type WarehouseStockRow,
} from "@/lib/api/warehouses";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const WAREHOUSE_QUERY_KEY = "admin-warehouses" as const;

function quantity(row: WarehouseStockRow | undefined, key: keyof WarehouseStockRow["stock"]): string {
  return toPersianDigits(String(row?.stock[key] ?? 0));
}

export default function WarehousesPage() {
  // One server query behind the whole page: the warehouse list and the
  // stock-by-warehouse view always come from the same fetch, so they can
  // never disagree with each other the way two independent loads could.
  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [WAREHOUSE_QUERY_KEY],
    queryFn: async () => {
      const [warehouses, stock] = await Promise.all([
        warehousesApi.list(),
        warehousesApi.stockByWarehouse(),
      ]);
      return { items: warehouses.items, stockRows: stock.items };
    },
    fallbackError: "دریافت فهرست انبارها ناموفق بود",
  });
  const items: Warehouse[] = data?.items ?? [];
  const stockRows: WarehouseStockRow[] = data?.stockRows ?? [];

  // Dialog-local state. The page-level `error` is owned by the query now:
  // save failures use `formError` so they stay inside the dialog instead of
  // blanking the whole list behind it.
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Warehouse | null>(null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [address, setAddress] = useState("");
  const [isDefault, setIsDefault] = useState(false);

  const stockByWarehouse = useMemo(() => {
    const map = new Map<string, WarehouseStockRow>();
    for (const row of stockRows) map.set(row.warehouse_id, row);
    return map;
  }, [stockRows]);

  const openCreate = () => {
    setEditing(null);
    setName(""); setCode(""); setAddress(""); setIsDefault(false);
    setFormError(null);
    setDialogOpen(true);
  };

  const openEdit = (warehouse: Warehouse) => {
    setEditing(warehouse);
    setName(warehouse.name);
    setCode(warehouse.code);
    setAddress(warehouse.address ?? "");
    setIsDefault(warehouse.is_default);
    setFormError(null);
    setDialogOpen(true);
  };

  // Mutations invalidate the shared cache key; the query refetches and the
  // list updates without the page hand-crafting a `setItems` per save path.
  const runMutation = useAdminMutation();

  const save = async () => {
    if (!name.trim() || !code.trim()) {
      setFormError("نام و کد انبار الزامی است");
      return;
    }
    setSaving(true);
    setFormError(null);
    const payload = {
      name: name.trim(),
      code: code.trim(),
      address: address.trim() || null,
      is_default: isDefault,
    };
    const result = await runMutation(
      () => editing
        ? warehousesApi.update(editing.id, payload)
        : warehousesApi.create(payload),
      {
        fallbackError: "ذخیره انبار ناموفق بود",
        invalidateKeys: [[WAREHOUSE_QUERY_KEY]],
      },
    );
    if (result.ok) {
      setDialogOpen(false);
    } else {
      setFormError((result as { error: string }).error);
    }
    setSaving(false);
  };

  const setDefault = async (warehouse: Warehouse) => {
    if (warehouse.is_default) return;
    if (!window.confirm(`انبار «${warehouse.name}» پیش‌فرض شود؟ موجودی جابه‌جا نمی‌شود و فقط انبار پیش‌فرض سامانه تغییر می‌کند.`)) return;
    setSaving(true);
    const result = await runMutation(
      () => warehousesApi.update(warehouse.id, { is_default: true }),
      {
        fallbackError: "تعیین انبار پیش‌فرض ناموفق بود",
        // The previous default is demoted server-side: refresh rather than guess.
        invalidateKeys: [[WAREHOUSE_QUERY_KEY]],
      },
    );
    if (!result.ok) setFormError(result.error);
    setSaving(false);
  };

  const toggleActive = async (warehouse: Warehouse) => {
    const verb = warehouse.is_active ? "غیرفعال" : "فعال";
    if (!window.confirm(`تایید ${verb}سازی انبار «${warehouse.name}»؟`)) return;
    setSaving(true);
    const result = await runMutation(
      () => warehouse.is_active
        ? warehousesApi.deactivate(warehouse.id)
        : warehousesApi.reactivate(warehouse.id),
      {
        fallbackError: `${verb}سازی انبار ناموفق بود`,
        invalidateKeys: [[WAREHOUSE_QUERY_KEY]],
      },
    );
    if (!result.ok) setFormError(result.error);
    setSaving(false);
  };

  const columns: DataTableColumn<Warehouse>[] = [
    {
      key: "name",
      header: "نام انبار",
      render: (warehouse) => (
        <div className="flex items-center gap-2">
          <span className="font-medium">{warehouse.name}</span>
          {warehouse.is_default && (
            <Badge variant="default" className="gap-1">
              <Star className="h-3 w-3" /> پیش‌فرض
            </Badge>
          )}
        </div>
      ),
    },
    {
      key: "code",
      header: "کد",
      render: (warehouse) => <span className="font-mono text-xs" dir="ltr">{warehouse.code}</span>,
    },
    {
      key: "status",
      header: "وضعیت",
      render: (warehouse) => warehouse.is_active
        ? <Badge variant="secondary">فعال</Badge>
        : <Badge variant="outline">غیرفعال</Badge>,
    },
    {
      key: "available",
      header: "موجودی قابل فروش",
      hideOnMobile: true,
      render: (warehouse) => (
        <span className="font-medium">{quantity(stockByWarehouse.get(warehouse.id), "available")}</span>
      ),
    },
    {
      key: "on_hand",
      header: "موجودی فیزیکی",
      hideOnMobile: true,
      render: (warehouse) => quantity(stockByWarehouse.get(warehouse.id), "total_on_hand"),
    },
    {
      key: "variants",
      header: "تعداد کالا",
      hideOnMobile: true,
      render: (warehouse) => quantity(stockByWarehouse.get(warehouse.id), "variant_count"),
    },
    {
      key: "action",
      header: "عملیات",
      render: (warehouse) => (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={saving} onClick={() => openEdit(warehouse)}>
            <Pencil className="ms-1 h-3.5 w-3.5" /> ویرایش
          </Button>
          {!warehouse.is_default && (
            <Button size="sm" variant="ghost" disabled={saving || !warehouse.is_active} onClick={() => void setDefault(warehouse)}>
              پیش‌فرض کن
            </Button>
          )}
          <Button
            size="sm"
            variant={warehouse.is_active ? "destructive" : "secondary"}
            disabled={saving || warehouse.is_default}
            title={warehouse.is_default ? "انبار پیش‌فرض قابل غیرفعال‌سازی نیست" : undefined}
            onClick={() => void toggleActive(warehouse)}
          >
            {warehouse.is_active ? "غیرفعال" : "فعال"}
          </Button>
        </div>
      ),
    },
  ];

  const stockColumns: DataTableColumn<WarehouseStockRow>[] = [
    {
      key: "warehouse",
      header: "انبار",
      render: (row) => (
        <div className="flex items-center gap-2">
          <span className="font-medium">{row.name}</span>
          {row.is_default && <Badge>پیش‌فرض</Badge>}
          {!row.is_registered && <Badge variant="outline">ثبت‌نشده</Badge>}
        </div>
      ),
    },
    { key: "available", header: "قابل فروش", render: (row) => toPersianDigits(String(row.stock.available)) },
    { key: "reserved", header: "رزرو", hideOnMobile: true, render: (row) => toPersianDigits(String(row.stock.reserved)) },
    { key: "committed", header: "تعهدشده", hideOnMobile: true, render: (row) => toPersianDigits(String(row.stock.committed)) },
    { key: "damaged", header: "معیوب", hideOnMobile: true, render: (row) => toPersianDigits(String(row.stock.damaged)) },
    { key: "incoming", header: "در راه", hideOnMobile: true, render: (row) => toPersianDigits(String(row.stock.incoming)) },
    { key: "on_hand", header: "فیزیکی", render: (row) => toPersianDigits(String(row.stock.total_on_hand)) },
  ];

  const totalOnHand = stockRows.reduce((sum, row) => sum + row.stock.total_on_hand, 0);

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <WarehouseIcon className="h-5 w-5 text-primary" /> انبارها
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            مدیریت انبارهای فیزیکی. تغییر انبار پیش‌فرض هیچ موجودی را جابه‌جا نمی‌کند و انبار دارای موجودی یا سابقه عملیات غیرفعال نمی‌شود.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void load()}>
            <RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی
          </Button>
          <Button onClick={openCreate}>
            <Plus className="ms-1 h-4 w-4" /> انبار جدید
          </Button>
        </div>
      </section>

      <DataTable
        columns={columns}
        rows={items}
        rowKey={(warehouse) => warehouse.id}
        loading={loading}
        error={error}
        emptyMessage="انباری ثبت نشده است"
        emptyDescription="برای فعال‌سازی عملیات چند‌انباره، نخستین انبار را ایجاد کنید."
        emptyAction={<Button onClick={openCreate}><Plus className="ms-1 h-4 w-4" /> انبار جدید</Button>}
      />

      <section className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold">موجودی به تفکیک انبار</h3>
          <span className="text-xs text-muted-foreground">
            مجموع موجودی فیزیکی: {toPersianDigits(String(totalOnHand))} واحد
          </span>
        </div>
        <DataTable
          columns={stockColumns}
          rows={stockRows}
          rowKey={(row) => row.warehouse_id}
          loading={loading}
          error={error}
          emptyMessage="موجودی ثبت نشده است"
          emptyDescription="پس از ثبت رسید یا شمارش، موجودی هر انبار در این جدول نمایش داده می‌شود."
        />
      </section>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent dir="rtl">
          <DialogHeader>
            <DialogTitle>{editing ? "ویرایش انبار" : "ایجاد انبار"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="warehouseName">نام انبار</Label>
              <Input id="warehouseName" value={name} onChange={(event) => setName(event.target.value)} placeholder="انبار شمال" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="warehouseCode">کد یکتا</Label>
              <Input id="warehouseCode" dir="ltr" value={code} onChange={(event) => setCode(event.target.value)} placeholder="NORTH-1" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="warehouseAddress">نشانی</Label>
              <Input id="warehouseAddress" value={address} onChange={(event) => setAddress(event.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isDefault}
                onChange={(event) => setIsDefault(event.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              این انبار پیش‌فرض سامانه باشد (انبار پیش‌فرض فعلی به‌طور خودکار لغو می‌شود)
            </label>
            {formError && (
              <div role="alert" className="mt-1 text-sm text-destructive">
                {formError}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>انصراف</Button>
            <Button disabled={saving} onClick={() => void save()}>
              {saving ? "در حال ذخیره..." : editing ? "ذخیره تغییرات" : "ایجاد انبار"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
