"use client";

import { useState } from "react";
import Link from "next/link";
import { ClipboardList, Plus, RefreshCw, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toPersianDigits } from "@/lib/utils";
import {
  procurementApi,
  type PurchaseOrder,
  type PurchaseOrderStatus,
  type Supplier,
  type SuggestedPOGroup,
} from "@/lib/api/procurement";
import { apiErrorMessage } from "@/lib/api/error-message";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const POS_QUERY_KEY = "admin-procurement-pos" as const;
const POS_SUPPLIERS_QUERY_KEY = "admin-procurement-pos-suppliers" as const;

const STATUS: Record<PurchaseOrderStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  sent: { label: "ارسال‌شده", variant: "secondary" },
  partially_received: { label: "دریافت جزئی", variant: "secondary" },
  received: { label: "دریافت کامل", variant: "default" },
  closed: { label: "بسته‌شده", variant: "default" },
  cancelled: { label: "لغوشده", variant: "destructive" },
};

function formatRial(value: number): string {
  return toPersianDigits(new Intl.NumberFormat("en-US").format(value));
}

export default function PurchaseOrdersPage() {
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Create form
  const [supplierId, setSupplierId] = useState("");
  const [variantId, setVariantId] = useState("");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [taxBps, setTaxBps] = useState("0");

  // Suggest dialog
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [groups, setGroups] = useState<SuggestedPOGroup[]>([]);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  // Two queries: POs (keyed on statusFilter) and active suppliers for the
  // form. Keeping suppliers separate means changing the status filter does
  // not re-query the supplier list.
  const {
    data: posData,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [POS_QUERY_KEY, statusFilter],
    queryFn: () =>
      procurementApi.listPOs({
        status: statusFilter === "all" ? undefined : (statusFilter as PurchaseOrderStatus),
      }),
    fallbackError: "دریافت سفارش‌های خرید ناموفق بود",
  });
  const items: PurchaseOrder[] = posData?.items ?? [];

  const { data: suppliersData } = useAdminQuery({
    queryKey: [POS_SUPPLIERS_QUERY_KEY],
    queryFn: () => procurementApi.listSuppliers({ is_active: true }),
    fallbackError: "دریافت فهرست تامین‌کنندگان ناموفق بود",
  });
  const suppliers: Supplier[] = suppliersData?.items ?? [];
  const runMutation = useAdminMutation();

  const create = async () => {
    const parsedQty = Number(qty);
    const parsedPrice = Number(price);
    const parsedTax = Number(taxBps);
    if (!supplierId || !variantId.trim() || !Number.isInteger(parsedQty) || parsedQty <= 0 || !Number.isInteger(parsedPrice) || parsedPrice < 0) {
      setFormError("تامین‌کننده، شناسه واریانت، تعداد صحیح مثبت و قیمت واحد معتبر الزامی است"); return;
    }
    setSaving(true);
    setFormError(null);
    const result = await runMutation(
      () =>
        procurementApi.createPO({
          supplier_id: supplierId,
          lines: [{
            product_variant_id: variantId.trim(),
            qty_ordered: parsedQty,
            unit_price_rial: parsedPrice,
            tax_basis_points: Number.isInteger(parsedTax) ? parsedTax : 0,
          }],
        }),
      {
        fallbackError: "ایجاد سفارش خرید ناموفق بود",
        invalidateKeys: [[POS_QUERY_KEY]],
      },
    );
    if (result.ok) {
      setVariantId(""); setQty(""); setPrice(""); setTaxBps("0");
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const openSuggest = async () => {
    setSuggestOpen(true); setSuggestLoading(true); setChecked({});
    try {
      const data = await procurementApi.suggestPOs();
      setGroups(data.groups);
      const initial: Record<string, boolean> = {};
      for (const group of data.groups) for (const line of group.lines) initial[line.variant_id] = true;
      setChecked(initial);
    } catch (reason) { setFormError(apiErrorMessage(reason, "دریافت پیشنهادها ناموفق بود")); setSuggestOpen(false); }
    finally { setSuggestLoading(false); }
  };

  const createFromSuggestion = async (group: SuggestedPOGroup) => {
    const supplierId = group.supplier_id;
    if (!supplierId) { setFormError("برای اقلام بدون تامین‌کننده ترجیحی ابتدا تامین‌کننده ترجیحی تعیین کنید"); return; }
    const selected = group.lines.filter((line) => checked[line.variant_id]).map((line) => line.variant_id);
    if (!selected.length) { setFormError("حداقل یک قلم را انتخاب کنید"); return; }
    setSaving(true);
    const result = await runMutation(
      () =>
        procurementApi.createPOFromSuggestions({
          supplier_id: supplierId,
          variant_ids: selected,
          notes: "ایجاد خودکار از پیشنهاد نقطه سفارش",
        }),
      {
        fallbackError: "ایجاد سفارش از پیشنهاد ناموفق بود",
        invalidateKeys: [[POS_QUERY_KEY]],
      },
    );
    if (result.ok) {
      setSuggestOpen(false);
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const columns: DataTableColumn<PurchaseOrder>[] = [
    { key: "number", header: "شماره", render: (item) => (
      <Link href={`/admin/procurement/pos/${item.id}`} className="font-mono text-xs text-primary hover:underline" dir="ltr">
        {item.number ?? item.id.slice(0, 8)}
      </Link>
    ) },
    { key: "supplier", header: "تامین‌کننده", render: (item) => item.supplier_name ?? "—" },
    { key: "lines", header: "اقلام", hideOnMobile: true, render: (item) => toPersianDigits(`${item.lines.length} ردیف`) },
    { key: "total", header: "مبلغ کل (ریال)", render: (item) => <span dir="ltr">{formatRial(item.total_rial)}</span> },
    { key: "status", header: "وضعیت", render: (item) => <Badge variant={STATUS[item.status].variant}>{STATUS[item.status].label}</Badge> },
    { key: "date", header: "ایجاد", hideOnMobile: true, render: (item) => new Date(item.created_at).toLocaleDateString("fa-IR") },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold"><ClipboardList className="h-5 w-5 text-primary" /> سفارش‌های خرید</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">چرخه خرید از تامین‌کننده: پیش‌نویس، ارسال، دریافت جزئی یا کامل و بستن. دریافت اقلام به‌صورت خودکار رسید انبار مرتبط می‌سازد.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void load()}><RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی</Button>
          <Button onClick={() => void openSuggest()}><Sparkles className="ms-1 h-4 w-4" /> پیشنهاد خرید</Button>
        </div>
      </section>

      <Card className="border-s-4 border-s-primary p-5">
        <h3 className="mb-4 text-sm font-semibold">ایجاد سفارش خرید</h3>
        <div className="grid gap-3 md:grid-cols-5">
          <div className="space-y-1.5">
            <Label>تامین‌کننده</Label>
            <Select value={supplierId} onValueChange={setSupplierId}>
              <SelectTrigger><SelectValue placeholder="انتخاب کنید" /></SelectTrigger>
              <SelectContent>
                {suppliers.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5"><Label htmlFor="poVariant">شناسه واریانت</Label><Input id="poVariant" dir="ltr" value={variantId} onChange={(e) => setVariantId(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="poQty">تعداد</Label><Input id="poQty" dir="ltr" type="number" min="1" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="poPrice">قیمت واحد (ریال)</Label><Input id="poPrice" dir="ltr" type="number" min="0" inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="poTax">مالیات (بیسیس‌پوینت)</Label><Input id="poTax" dir="ltr" type="number" min="0" max="10000" inputMode="numeric" value={taxBps} onChange={(e) => setTaxBps(e.target.value)} placeholder="900 = ۹٪" /></div>
        </div>
        <div className="mt-3"><Button disabled={saving} onClick={() => void create()}><Plus className="ms-1 h-4 w-4" /> ایجاد پیش‌نویس</Button></div>
      </Card>

      <div className="max-w-xs space-y-1.5">
        <Label>فیلتر وضعیت</Label>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">همه</SelectItem>
            {Object.entries(STATUS).map(([value, meta]) => (
              <SelectItem key={value} value={value}>{meta.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <DataTable columns={columns} rows={items} rowKey={(item) => item.id} loading={loading} error={error} emptyMessage="سفارش خریدی ثبت نشده است" emptyDescription="از دکمه پیشنهاد خرید برای تجمیع اقلام کم‌موجودی استفاده کنید." />

      <Dialog open={suggestOpen} onOpenChange={setSuggestOpen}>
        <DialogContent className="max-w-2xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>پیشنهاد سفارش خرید از نقطه سفارش</DialogTitle>
            <DialogDescription>اقلامی که موجودی آن‌ها به حداقل رسیده، گروه‌بندی‌شده بر اساس تامین‌کننده ترجیحی.</DialogDescription>
          </DialogHeader>
          {suggestLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">در حال محاسبه پیشنهادها…</p>
          ) : groups.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">قلم کم‌موجودی برای پیشنهاد یافت نشد.</p>
          ) : (
            <div className="max-h-96 space-y-4 overflow-y-auto">
              {groups.map((group) => (
                <Card key={group.supplier_id ?? "unassigned"} className="p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-sm font-semibold">
                      {group.supplier_name ?? "بدون تامین‌کننده ترجیحی"}
                    </h4>
                    {group.supplier_id && (
                      <Button size="sm" disabled={saving} onClick={() => void createFromSuggestion(group)}>
                        ایجاد پیش‌نویس PO
                      </Button>
                    )}
                  </div>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground">
                        <th className="py-1 text-start">انتخاب</th>
                        <th className="py-1 text-start">واریانت</th>
                        <th className="py-1 text-start">موجودی</th>
                        <th className="py-1 text-start">حداقل</th>
                        <th className="py-1 text-start">پیشنهاد</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.lines.map((line) => (
                        <tr key={line.variant_id} className="border-b border-border/50">
                          <td className="py-1">
                            <input
                              type="checkbox"
                              checked={checked[line.variant_id] ?? false}
                              onChange={(e) => setChecked((prev) => ({ ...prev, [line.variant_id]: e.target.checked }))}
                            />
                          </td>
                          <td className="py-1 font-mono" dir="ltr">{line.variant_id.slice(0, 8)}</td>
                          <td className="py-1">{toPersianDigits(String(line.available))}</td>
                          <td className="py-1">{toPersianDigits(String(line.min_quantity))}</td>
                          <td className="py-1 font-semibold">{toPersianDigits(String(line.suggested_qty))}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Card>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
