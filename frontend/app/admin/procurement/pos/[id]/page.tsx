"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, CheckCircle2, ClipboardList, PackageCheck, RefreshCw, Send, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toPersianDigits } from "@/lib/utils";
import { useAdminQuery } from "@/lib/api/admin-query";
import {
  procurementApi,
  type PurchaseOrder,
  type PurchaseOrderStatus,
} from "@/lib/api/procurement";

const STATUS: Record<PurchaseOrderStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  sent: { label: "ارسال‌شده", variant: "secondary" },
  partially_received: { label: "دریافت جزئی", variant: "secondary" },
  received: { label: "دریافت کامل", variant: "default" },
  closed: { label: "بسته‌شده", variant: "default" },
  cancelled: { label: "لغوشده", variant: "destructive" },
};

function errorText(error: unknown, fallback: string): string {
  return (error as { response?: { data?: { error?: { message?: string }; detail?: string } } })?.response?.data?.error?.message
    ?? (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ?? fallback;
}

function formatRial(value: number): string {
  return toPersianDigits(new Intl.NumberFormat("en-US").format(value));
}

export default function PurchaseOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const poId = params.id;
  const [saving, setSaving] = useState(false);
  const [receiveQty, setReceiveQty] = useState<Record<string, string>>({});

  const {
    data: po = null,
    loading,
    error,
    reload: load,
  } = useAdminQuery<PurchaseOrder | null>({
    queryKey: ["admin", "procurement", "pos", poId],
    enabled: Boolean(poId),
    queryFn: async () => {
      return await procurementApi.getPO(poId);
    },
    fallbackError: "دریافت سفارش خرید ناموفق بود",
  });

  const act = async (fn: () => Promise<PurchaseOrder>, confirmText?: string) => {
    if (confirmText && !window.confirm(confirmText)) return;
    setSaving(true);
    try {
      await fn();
      await load();
    } catch (reason) {
      alert(errorText(reason, "عملیات ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };

  const receive = async () => {
    if (!po) return;
    const lines = po.lines
      .map((line) => ({ line_id: line.id, quantity: Number(receiveQty[line.id] ?? "0") }))
      .filter((entry) => Number.isInteger(entry.quantity) && entry.quantity > 0);
    if (!lines.length) { alert("برای حداقل یک ردیف، تعداد دریافت مثبت وارد کنید"); return; }
    await act(
      () => procurementApi.receivePO(po.id, lines),
      "دریافت اقلام ثبت شود؟ رسید انبار مرتبط به‌صورت خودکار ساخته و موجودی افزایش می‌یابد.",
    );
    setReceiveQty({});
  };

  if (loading) return <div className="py-16 text-center text-sm text-muted-foreground" dir="rtl">در حال بارگذاری…</div>;
  if (!po) return <div className="py-16 text-center text-sm text-destructive" dir="rtl">{error ?? "سفارش خرید یافت نشد"}</div>;

  const receivable = po.status === "sent" || po.status === "partially_received";

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <Link href="/admin/procurement/pos" className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <ArrowRight className="h-3 w-3" /> بازگشت به فهرست
          </Link>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <ClipboardList className="h-5 w-5 text-primary" />
            سفارش خرید <span className="font-mono" dir="ltr">{po.number}</span>
            <Badge variant={STATUS[po.status].variant}>{STATUS[po.status].label}</Badge>
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            تامین‌کننده: {po.supplier_name ?? "—"}
            {po.expected_at && <> · تحویل مورد انتظار: {new Date(po.expected_at).toLocaleDateString("fa-IR")}</>}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void load()}><RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی</Button>
          {po.status === "draft" && (
            <Button disabled={saving} onClick={() => void act(() => procurementApi.sendPO(po.id), "سفارش به تامین‌کننده ارسال (علامت‌گذاری) شود؟")}>
              <Send className="ms-1 h-4 w-4" /> ارسال به تامین‌کننده
            </Button>
          )}
          {(po.status === "received" || po.status === "partially_received" || po.status === "sent") && (
            <Button variant="outline" disabled={saving} onClick={() => void act(() => procurementApi.closePO(po.id), "سفارش بسته شود؟ این عمل نهایی است.")}>
              <CheckCircle2 className="ms-1 h-4 w-4" /> بستن سفارش
            </Button>
          )}
          {(po.status === "draft" || po.status === "sent") && (
            <Button variant="destructive" disabled={saving} onClick={() => void act(() => procurementApi.cancelPO(po.id), "سفارش لغو شود؟")}>
              <XCircle className="ms-1 h-4 w-4" /> لغو
            </Button>
          )}
        </div>
      </section>

      {error && <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div>}

      <Card className="p-5">
        <h3 className="mb-4 text-sm font-semibold">اقلام سفارش</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground">
                <th className="py-2 text-start">واریانت</th>
                <th className="py-2 text-start">سفارش‌داده</th>
                <th className="py-2 text-start">دریافت‌شده</th>
                <th className="py-2 text-start">باقیمانده</th>
                <th className="py-2 text-start">قیمت واحد (ریال)</th>
                <th className="py-2 text-start">مالیات (bp)</th>
                <th className="py-2 text-start">مبلغ ردیف (ریال)</th>
                {receivable && <th className="py-2 text-start">دریافت جدید</th>}
              </tr>
            </thead>
            <tbody>
              {po.lines.map((line) => (
                <tr key={line.id} className="border-b border-border/50">
                  <td className="py-2 font-mono text-xs" dir="ltr">{line.product_variant_id.slice(0, 8)}</td>
                  <td className="py-2">{toPersianDigits(String(line.qty_ordered))}</td>
                  <td className="py-2">{toPersianDigits(String(line.qty_received))}</td>
                  <td className="py-2">{toPersianDigits(String(line.qty_outstanding))}</td>
                  <td className="py-2" dir="ltr">{formatRial(line.unit_price_rial)}</td>
                  <td className="py-2">{toPersianDigits(String(line.tax_basis_points))}</td>
                  <td className="py-2" dir="ltr">{formatRial(line.line_total_rial)}</td>
                  {receivable && (
                    <td className="py-2">
                      {line.qty_outstanding > 0 ? (
                        <Input
                          dir="ltr"
                          type="number"
                          min="0"
                          max={line.qty_outstanding}
                          inputMode="numeric"
                          className="h-8 w-24"
                          placeholder={`حداکثر ${toPersianDigits(String(line.qty_outstanding))}`}
                          value={receiveQty[line.id] ?? ""}
                          onChange={(e) => setReceiveQty((prev) => ({ ...prev, [line.id]: e.target.value }))}
                        />
                      ) : "—"}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {receivable && (
          <div className="mt-4">
            <Button disabled={saving} onClick={() => void receive()}>
              <PackageCheck className="ms-1 h-4 w-4" /> ثبت دریافت اقلام
            </Button>
          </div>
        )}
        <div className="mt-6 grid max-w-md gap-1 text-sm">
          <div className="flex justify-between"><span className="text-muted-foreground">جمع اقلام</span><span dir="ltr">{formatRial(po.subtotal_rial)}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">مالیات</span><span dir="ltr">{formatRial(po.tax_rial)}</span></div>
          <div className="flex justify-between font-bold"><span>مبلغ کل (ریال)</span><span dir="ltr">{formatRial(po.total_rial)}</span></div>
        </div>
      </Card>

      {po.receipt_ids.length > 0 && (
        <Card className="p-5">
          <h3 className="mb-2 text-sm font-semibold">رسیدهای انبار مرتبط</h3>
          <ul className="space-y-1 text-xs text-muted-foreground">
            {po.receipt_ids.map((id) => (
              <li key={id} className="font-mono" dir="ltr">{id}</li>
            ))}
          </ul>
        </Card>
      )}

      {po.notes && (
        <Card className="p-5">
          <h3 className="mb-2 text-sm font-semibold">یادداشت</h3>
          <p className="text-sm text-muted-foreground">{po.notes}</p>
        </Card>
      )}
    </div>
  );
}
