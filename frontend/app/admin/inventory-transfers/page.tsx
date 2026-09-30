"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeftRight, PackageCheck, Plus, RefreshCw, Truck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toPersianDigits } from "@/lib/utils";
import { inventoryOperationsApi, type WarehouseTransfer } from "@/lib/api/inventory-operations";
import { warehousesApi, type Warehouse } from "@/lib/api/warehouses";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const TRANSFERS_QUERY_KEY = "admin-inventory-transfers" as const;

const STATUS: Record<WarehouseTransfer["status"], { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  shipped: { label: "در مسیر", variant: "secondary" },
  received: { label: "تحویل‌شده", variant: "default" },
  cancelled: { label: "لغوشده", variant: "destructive" },
};

/** Warehouse picker options: active warehouses, labelled with their code. */
function warehouseLabel(warehouse: Warehouse): string {
  return `${warehouse.name} (${warehouse.code})`;
}

export default function InventoryTransfersPage() {
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [fromWarehouse, setFromWarehouse] = useState("");
  const [toWarehouse, setToWarehouse] = useState("");
  const [variantId, setVariantId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");

  // Transfers and the warehouse picker load together: the picker only offers
  // warehouses that exist, so a separate fetch could let an operator pick one
  // that the transfer list does not know about.
  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [TRANSFERS_QUERY_KEY],
    queryFn: async () => {
      const [transfers, catalogue] = await Promise.all([
        inventoryOperationsApi.listTransfers(),
        // Only active warehouses can take part in a transfer.
        warehousesApi.list({ is_active: true }),
      ]);
      return { items: transfers.items, warehouses: catalogue.items };
    },
    fallbackError: "دریافت انتقال‌ها ناموفق بود",
  });
  const items: WarehouseTransfer[] = data?.items ?? [];
  const warehouses: Warehouse[] = data?.warehouses ?? [];
  const runMutation = useAdminMutation();

  const create = async () => {
    const parsedQuantity = Number(quantity);
    if (!fromWarehouse.trim() || !toWarehouse.trim() || !variantId.trim() || !Number.isInteger(parsedQuantity) || parsedQuantity <= 0) {
      setFormError("شناسه دو انبار، شناسه واریانت و تعداد صحیحِ مثبت را وارد کنید");
      return;
    }
    setSaving(true);
    setFormError(null);
    const result = await runMutation(
      () =>
        inventoryOperationsApi.createTransfer({
          from_warehouse_id: fromWarehouse.trim(),
          to_warehouse_id: toWarehouse.trim(),
          lines: [{ product_variant_id: variantId.trim(), quantity: parsedQuantity }],
          notes: notes.trim() || undefined,
        }),
      {
        fallbackError: "ایجاد انتقال ناموفق بود",
        invalidateKeys: [[TRANSFERS_QUERY_KEY]],
      },
    );
    if (result.ok) {
      setVariantId(""); setQuantity(""); setNotes("");
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const transition = async (transfer: WarehouseTransfer, action: "ship" | "receive") => {
    const label = action === "ship" ? "ارسال از انبار مبدا" : "تحویل در انبار مقصد";
    if (!window.confirm(`تایید ${label}؟ تغییر موجودی از طریق دفتر تراکنش ثبت می‌شود.`)) return;
    setSaving(true);
    const result = await runMutation(
      () => action === "ship"
        ? inventoryOperationsApi.shipTransfer(transfer.id)
        : inventoryOperationsApi.receiveTransfer(transfer.id),
      {
        fallbackError: `${label} ناموفق بود`,
        invalidateKeys: [[TRANSFERS_QUERY_KEY]],
      },
    );
    if (!result.ok) setFormError(result.error);
    setSaving(false);
  };

  const columns: DataTableColumn<WarehouseTransfer>[] = [
    { key: "id", header: "شماره انتقال", render: (item) => <span className="font-mono text-xs">{item.id.slice(0, 8)}</span> },
    { key: "route", header: "مسیر", render: (item) => <span className="font-mono text-xs" dir="ltr">{item.from_warehouse_id.slice(0, 8)} → {item.to_warehouse_id.slice(0, 8)}</span> },
    { key: "lines", header: "اقلام", render: (item) => toPersianDigits(`${item.lines.length} ردیف / ${item.lines.reduce((sum, line) => sum + line.quantity, 0)} واحد`) },
    { key: "status", header: "وضعیت", render: (item) => <Badge variant={STATUS[item.status].variant}>{STATUS[item.status].label}</Badge> },
    {
      key: "action",
      header: "عملیات",
      render: (item) => item.status === "draft" ? (
        <Button size="sm" disabled={saving} onClick={() => void transition(item, "ship")}><Truck className="ms-1 h-4 w-4" /> ارسال</Button>
      ) : item.status === "shipped" ? (
        <Button size="sm" disabled={saving} onClick={() => void transition(item, "receive")}><PackageCheck className="ms-1 h-4 w-4" /> تحویل</Button>
      ) : "—",
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl"><h2 className="flex items-center gap-2 text-xl font-bold"><ArrowLeftRight className="h-5 w-5 text-primary" /> انتقال بین انبارها</h2><p className="mt-1 text-sm leading-6 text-muted-foreground">ارسال و تحویل دو مرحله‌ای: موجودی در ارسال از مبدا خارج و فقط با تحویل، به مقصد افزوده می‌شود.</p></div>
        <Button variant="outline" onClick={() => void load()}><RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی</Button>
      </section>

      <Card className="border-s-4 border-s-primary p-5">
        <h3 className="mb-4 text-sm font-semibold">ایجاد انتقال جدید</h3>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="space-y-1.5">
            <Label htmlFor="fromWarehouse">انبار مبدا</Label>
            <select
              id="fromWarehouse"
              value={fromWarehouse}
              onChange={(event) => setFromWarehouse(event.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">— انتخاب انبار —</option>
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouseLabel(warehouse)}
                </option>
              ))}
            </select>
            <Input
              dir="ltr"
              value={fromWarehouse}
              onChange={(event) => setFromWarehouse(event.target.value)}
              placeholder="یا شناسه انبار را وارد کنید"
              className="font-mono text-xs"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="toWarehouse">انبار مقصد</Label>
            <select
              id="toWarehouse"
              value={toWarehouse}
              onChange={(event) => setToWarehouse(event.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">— انتخاب انبار —</option>
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouseLabel(warehouse)}
                </option>
              ))}
            </select>
            <Input
              dir="ltr"
              value={toWarehouse}
              onChange={(event) => setToWarehouse(event.target.value)}
              placeholder="یا شناسه انبار را وارد کنید"
              className="font-mono text-xs"
            />
          </div>
          <div className="space-y-1.5"><Label htmlFor="transferVariant">شناسه واریانت</Label><Input id="transferVariant" dir="ltr" value={variantId} onChange={(event) => setVariantId(event.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="transferQty">تعداد</Label><Input id="transferQty" dir="ltr" inputMode="numeric" type="number" min="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></div>
        </div>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row"><Input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="یادداشت اختیاری" /><Button disabled={saving} onClick={() => void create()}><Plus className="ms-1 h-4 w-4" /> ایجاد پیش‌نویس انتقال</Button></div>
      </Card>

      {formError && <div role="alert" className="text-sm text-destructive">{formError}</div>}
      <DataTable columns={columns} rows={items} rowKey={(item) => item.id} loading={loading} error={error} emptyMessage="انتقالی ثبت نشده است" emptyDescription="برای جابه‌جایی کنترل‌شده میان انبارها، یک پیش‌نویس انتقال بسازید." />
    </div>
  );
}
