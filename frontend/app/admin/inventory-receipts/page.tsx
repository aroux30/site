"use client";

import { useState } from "react";
import { Boxes, CheckCircle2, Plus, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toPersianDigits } from "@/lib/utils";
import { inventoryOperationsApi, type Receipt } from "@/lib/api/inventory-operations";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const RECEIPTS_QUERY_KEY = "admin-inventory-receipts" as const;

const STATUS: Record<Receipt["status"], { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  received: { label: "ثبت‌شده", variant: "default" },
  cancelled: { label: "لغوشده", variant: "destructive" },
};

export default function InventoryReceiptsPage() {
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [warehouseId, setWarehouseId] = useState("");
  const [variantId, setVariantId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [RECEIPTS_QUERY_KEY],
    queryFn: () => inventoryOperationsApi.listReceipts(),
    fallbackError: "دریافت رسیدها ناموفق بود",
  });
  const items: Receipt[] = data?.items ?? [];
  const runMutation = useAdminMutation();

  const create = async () => {
    const parsedQuantity = Number(quantity);
    if (!variantId.trim() || !Number.isInteger(parsedQuantity) || parsedQuantity <= 0) {
      setFormError("شناسه واریانت و تعداد صحیحِ مثبت را وارد کنید"); return;
    }
    setSaving(true);
    setFormError(null);
    const result = await runMutation(
      () =>
        inventoryOperationsApi.createReceipt({
          warehouse_id: warehouseId.trim() || undefined,
          lines: [{ product_variant_id: variantId.trim(), quantity: parsedQuantity }],
          notes: notes.trim() || undefined,
        }),
      {
        fallbackError: "ایجاد رسید ناموفق بود",
        invalidateKeys: [[RECEIPTS_QUERY_KEY]],
      },
    );
    if (result.ok) {
      setVariantId(""); setQuantity(""); setNotes("");
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const receive = async (receipt: Receipt) => {
    if (!window.confirm("رسید را ثبت می‌کنید؟ موجودی فقط از طریق تراکنش دریافت در دفتر موجودی افزایش می‌یابد.")) return;
    setSaving(true);
    const result = await runMutation(
      () => inventoryOperationsApi.receiveReceipt(receipt.id),
      {
        fallbackError: "ثبت رسید ناموفق بود",
        invalidateKeys: [[RECEIPTS_QUERY_KEY]],
      },
    );
    if (!result.ok) setFormError(result.error);
    setSaving(false);
  };

  const columns: DataTableColumn<Receipt>[] = [
    { key: "id", header: "شماره رسید", render: (item) => <span className="font-mono text-xs">{item.id.slice(0, 8)}</span> },
    { key: "warehouse", header: "انبار", render: (item) => <span className="font-mono text-xs" dir="ltr">{item.warehouse_id.slice(0, 12)}</span> },
    { key: "lines", header: "اقلام", render: (item) => toPersianDigits(`${item.lines.length} ردیف / ${item.lines.reduce((sum, line) => sum + line.quantity, 0)} واحد`) },
    { key: "status", header: "وضعیت", render: (item) => <Badge variant={STATUS[item.status].variant}>{STATUS[item.status].label}</Badge> },
    { key: "date", header: "زمان ثبت", hideOnMobile: true, render: (item) => item.received_at ? new Date(item.received_at).toLocaleString("fa-IR") : "—" },
    { key: "action", header: "عملیات", render: (item) => item.status === "draft" ? <Button size="sm" disabled={saving} onClick={() => void receive(item)}><CheckCircle2 className="ms-1 h-4 w-4" /> ثبت دریافت</Button> : "—" },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl"><h2 className="flex items-center gap-2 text-xl font-bold"><Boxes className="h-5 w-5 text-primary" /> دریافت کالا</h2><p className="mt-1 text-sm leading-6 text-muted-foreground">رسید مستقل از سفارش خرید برای دریافت اولیه کالا. دریافت اقلام سفارش خرید از صفحه سفارش‌های خرید، رسید مرتبط را به‌صورت خودکار می‌سازد.</p></div>
        <Button variant="outline" onClick={() => void load()}><RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی</Button>
      </section>

      <Card className="border-s-4 border-s-primary p-5">
        <h3 className="mb-4 text-sm font-semibold">ایجاد رسید دریافت</h3>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="space-y-1.5"><Label htmlFor="receiptWarehouse">شناسه انبار</Label><Input id="receiptWarehouse" dir="ltr" value={warehouseId} onChange={(event) => setWarehouseId(event.target.value)} placeholder="خالی = انبار مرکزی" /></div>
          <div className="space-y-1.5"><Label htmlFor="receiptVariant">شناسه واریانت</Label><Input id="receiptVariant" dir="ltr" value={variantId} onChange={(event) => setVariantId(event.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="receiptQuantity">تعداد</Label><Input id="receiptQuantity" dir="ltr" type="number" min="1" inputMode="numeric" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></div>
        </div>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row"><Input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="یادداشت اختیاری، مانند شماره بارنامه" /><Button disabled={saving} onClick={() => void create()}><Plus className="ms-1 h-4 w-4" /> ایجاد پیش‌نویس رسید</Button></div>
        {formError && <div role="alert" className="mt-3 text-sm text-destructive">{formError}</div>}
      </Card>

      <DataTable columns={columns} rows={items} rowKey={(item) => item.id} loading={loading} error={error} emptyMessage="رسید دریافت ثبت نشده است" emptyDescription="برای افزایش کنترل‌شده موجودی، ابتدا یک رسید پیش‌نویس بسازید." />
    </div>
  );
}
