"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CreditCard,
  History,
  Loader2,
  MapPin,
  Package,
  Phone,
  RefreshCw,
  User,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/components/ui/use-toast";
import { cn, formatPrice, toPersianDigits } from "@/lib/utils";
import {
  ORDER_STATUS_TRANSITIONS,
  STATUS_VISUALS,
  derivePaymentStatus,
  isOrderStale,
  rialsToToman,
  type OrderStatus,
} from "@/lib/admin/order-domain";
import { PAYMENT_VISUALS } from "@/lib/admin/order-domain";
import { adminOrdersApi, type AdminOrderDetail } from "@/lib/api/admin-orders";
import { apiErrorMessage } from "@/lib/api/error-message";

/**
 * The order detail drawer (side sheet, RTL from the left edge).
 *
 * Loads the admin detail endpoint — the ONLY source of the unmasked address,
 * payment rows and timeline. The drawer shows the full address (this route is
 * orders:read-gated and the customer mask does not apply), every payment with
 * its real status (the list rows carry none; the old board fabricated "paid"),
 * and the transition buttons for exactly the transitions the state machine
 * allows — the same table the board's drag enforces.
 */

export interface OrderDetailSheetProps {
  orderId: string | null;
  onClose: () => void;
  /** Fired after a successful status change so the caller can resync. */
  onStatusChanged: () => void;
}

const PAYMENT_PROVIDER_LABELS: Record<string, string> = {
  zarinpal: "زرین‌پال",
  nextpay: "نکست‌پی",
  wallet: "کیف پول",
  card_transfer: "کارت به کارت",
};

export function OrderDetailSheet({ orderId, onClose, onStatusChanged }: OrderDetailSheetProps) {
  const { toast } = useToast();
  const [detail, setDetail] = useState<AdminOrderDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [changingTo, setChangingTo] = useState<OrderStatus | null>(null);

  useEffect(() => {
    if (!orderId) {
      setDetail(null);
      setLoadError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    adminOrdersApi
      .detail(orderId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (!cancelled) {
          setLoadError(apiErrorMessage(err, "جزئیات سفارش دریافت نشد."));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [orderId]);

  /**
   * Transitions offered as buttons in the drawer.
   *
   * `refunded` is a LEGAL state-machine move, but the PATCH route only flips
   * the status — the money moves through `POST /payments/{id}/refund`
   * (permission `payments:refund`). Offering it as a plain button here would
   * be an operational lie: the status would read "بازگشت وجه" while no refund
   * was ever issued. It is filtered out and explained instead; the real refund
   * path lives in the payments admin surface.
   */
  const allowedNext = useMemo(() => {
    if (!detail) return [] as OrderStatus[];
    return (ORDER_STATUS_TRANSITIONS[detail.status] ?? []).filter(
      (s) => s !== "refunded",
    );
  }, [detail]);

  const refundOnlyTransitions = useMemo(() => {
    if (!detail) return [] as OrderStatus[];
    return (ORDER_STATUS_TRANSITIONS[detail.status] ?? []).filter(
      (s) => s === "refunded",
    );
  }, [detail]);

  const handleTransition = async (target: OrderStatus) => {
    if (!detail) return;
    setChangingTo(target);
    try {
      await adminOrdersApi.updateStatus(detail.id, target);
      toast({
        title: "وضعیت تغییر کرد",
        description: `سفارش ${detail.orderNumber} به «${STATUS_VISUALS[target].label}» منتقل شد.`,
        variant: "success",
      });
      // Refetch the drawer (timeline grows) and tell the page to resync.
      const fresh = await adminOrdersApi.detail(detail.id);
      setDetail(fresh);
      onStatusChanged();
    } catch (err) {
      toast({
        title: "تغییر وضعیت ناموفق بود",
        description: apiErrorMessage(err, "سرور این تغییر را نپذیرفت."),
        variant: "destructive",
      });
    } finally {
      setChangingTo(null);
    }
  };

  const paymentStatus = detail ? derivePaymentStatus(detail.payments) : "unpaid";
  const visual = detail ? STATUS_VISUALS[detail.status] : null;
  const stale = detail ? isOrderStale(detail.status, detail.createdAt) : false;

  return (
    <Sheet open={Boolean(orderId)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="left"
        className="w-full overflow-y-auto sm:max-w-2xl"
        dir="rtl"
        aria-describedby={undefined}
      >
        <SheetHeader className="text-right">
          <SheetTitle className="flex items-center gap-2">
            {detail ? (
              <>
                <span className="font-mono">{detail.orderNumber}</span>
                {visual && (
                  <Badge variant="outline" className={cn("text-xs", visual.chip)}>
                    {visual.label}
                  </Badge>
                )}
              </>
            ) : (
              "جزئیات سفارش"
            )}
          </SheetTitle>
          <SheetDescription>اطلاعات کامل سفارش، مشتری، پرداخت و تاریخچهٔ وضعیت</SheetDescription>
        </SheetHeader>

        {loading && (
          <div className="flex min-h-48 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {loadError && !loading && (
          <div
            role="alert"
            className="mt-4 flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {loadError}
          </div>
        )}

        {detail && !loading && (
          <div className="mt-4 space-y-5 pb-8">
            {stale && (
              <div className="flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-xs font-medium text-amber-700 dark:text-amber-300">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                این سفارش بیش از ۲۴ ساعت در وضعیت فعلی مانده است — نیازمند پیگیری.
              </div>
            )}

            {/* Status transitions — exactly the allowed moves */}
            {(allowedNext.length > 0 || refundOnlyTransitions.length > 0) && (
              <section className="rounded-2xl border border-border p-4">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-foreground">
                  <ArrowLeft className="h-4 w-4 text-primary" />
                  تغییر وضعیت
                </h3>
                {allowedNext.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {allowedNext.map((target) => (
                      <Button
                        key={target}
                        size="sm"
                        variant={target === "canceled" ? "destructive" : "outline"}
                        disabled={changingTo !== null}
                        onClick={() => void handleTransition(target)}
                        className={cn(
                          "gap-1.5 text-xs",
                          target !== "canceled" && STATUS_VISUALS[target].chip,
                        )}
                      >
                        {changingTo === target ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        )}
                        {STATUS_VISUALS[target].label}
                      </Button>
                    ))}
                  </div>
                )}
                {allowedNext.includes("canceled") && (
                  <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                    لغو سفارش موجودی انبار را برمی‌گرداند و وجه پرداخت‌شده را به کیف پول مشتری
                    برمی‌گرداند.
                  </p>
                )}
                {refundOnlyTransitions.length > 0 && (
                  <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] leading-relaxed text-amber-700 dark:text-amber-300">
                    بازگشت وجه ({refundOnlyTransitions
                      .map((s) => STATUS_VISUALS[s].label)
                      .join("، ")}) از این مسیر انجام نمی‌شود؛ چون وضعیت را تغییر می‌دهد ولی
                    مبلغی جابه‌جا نمی‌کند. برای بازگشت واقعی وجه، از بخش «پرداخت و
                    کارت‌به‌کارت» روی تراکنش موردنظر اقدام کنید.
                  </p>
                )}
              </section>
            )}

            {/* Customer + address */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <section className="space-y-2 rounded-2xl border border-border p-4">
                <h3 className="flex items-center gap-2 border-b border-border/60 pb-2 text-sm font-bold text-foreground">
                  <User className="h-4 w-4 text-primary" />
                  مشتری
                </h3>
                <p className="text-sm font-medium text-foreground">
                  {detail.customerName ?? "بدون نام پروفایل"}
                </p>
                {detail.customerPhone && (
                  <p className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground" dir="ltr">
                    <Phone className="h-3 w-3" />
                    {toPersianDigits(detail.customerPhone)}
                  </p>
                )}
              </section>

              <section className="space-y-2 rounded-2xl border border-border p-4">
                <h3 className="flex items-center gap-2 border-b border-border/60 pb-2 text-sm font-bold text-foreground">
                  <MapPin className="h-4 w-4 text-primary" />
                  نشانی تحویل (کامل)
                </h3>
                {detail.shippingAddress ? (
                  <div className="space-y-1 text-xs leading-relaxed text-foreground">
                    {detail.shippingAddress.title && (
                      <p className="font-medium">{detail.shippingAddress.title}</p>
                    )}
                    <p>
                      {[detail.shippingAddress.province, detail.shippingAddress.city, detail.shippingAddress.district]
                        .filter(Boolean)
                        .join("، ")}
                    </p>
                    {detail.shippingAddress.fullAddress && (
                      <p>{detail.shippingAddress.fullAddress}</p>
                    )}
                    {detail.shippingAddress.postalCode && (
                      <p className="font-mono text-muted-foreground" dir="ltr">
                        کد پستی: {toPersianDigits(detail.shippingAddress.postalCode)}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">نشانی ثبت نشده است.</p>
                )}
              </section>
            </div>

            {/* Items */}
            <section className="space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
                <Package className="h-4 w-4 text-primary" />
                اقلام سفارش
              </h3>
              <div className="overflow-hidden rounded-xl border border-border">
                <table className="w-full text-right text-xs">
                  <thead className="border-b border-border bg-muted/50 text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2.5">کالا</th>
                      <th className="px-3 py-2.5">SKU</th>
                      <th className="px-3 py-2.5 text-center">تعداد</th>
                      <th className="px-3 py-2.5">قیمت واحد</th>
                      <th className="px-3 py-2.5">جمع</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {detail.items.map((item) => (
                      <tr key={item.id} className="hover:bg-muted/20">
                        <td className="px-3 py-2.5">
                          <p className="font-medium text-foreground">{item.productName}</p>
                          {item.variantInfo && (
                            <p className="text-[11px] text-muted-foreground">{item.variantInfo}</p>
                          )}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-muted-foreground" dir="ltr">
                          {item.sku}
                        </td>
                        <td className="px-3 py-2.5 text-center font-mono font-bold">
                          {toPersianDigits(item.quantity)}
                        </td>
                        <td className="px-3 py-2.5 font-mono">
                          {formatPrice(rialsToToman(item.unitPriceRial))}
                        </td>
                        <td className="px-3 py-2.5 font-mono font-bold">
                          {formatPrice(rialsToToman(item.totalPriceRial))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Totals */}
              <div className="flex justify-end">
                <div className="w-full space-y-2 rounded-xl border border-border/80 bg-muted/20 p-3.5 text-xs sm:w-72">
                  <div className="flex justify-between text-muted-foreground">
                    <span>جمع اقلام:</span>
                    <span className="font-mono">{formatPrice(rialsToToman(detail.subtotalRial))}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>هزینه ارسال:</span>
                    <span className="font-mono">
                      {detail.shippingCostRial === 0
                        ? "رایگان"
                        : formatPrice(rialsToToman(detail.shippingCostRial))}
                    </span>
                  </div>
                  {detail.discountRial > 0 && (
                    <div className="flex justify-between text-emerald-600">
                      <span>تخفیف:</span>
                      <span className="font-mono">- {formatPrice(rialsToToman(detail.discountRial))}</span>
                    </div>
                  )}
                  {detail.taxRial > 0 && (
                    <div className="flex justify-between text-muted-foreground">
                      <span>مالیات:</span>
                      <span className="font-mono">{formatPrice(rialsToToman(detail.taxRial))}</span>
                    </div>
                  )}
                  <Separator />
                  <div className="flex justify-between text-sm font-bold text-foreground">
                    <span>مبلغ کل:</span>
                    <span className="font-mono text-primary">
                      {formatPrice(rialsToToman(detail.totalRial))}
                    </span>
                  </div>
                </div>
              </div>
            </section>

            {/* Payments — the real rows, never an invented "paid" */}
            <section className="space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
                <CreditCard className="h-4 w-4 text-primary" />
                پرداخت‌ها
                <Badge variant="outline" className={cn("text-[10px]", PAYMENT_VISUALS[paymentStatus].chip)}>
                  {PAYMENT_VISUALS[paymentStatus].label}
                </Badge>
              </h3>
              {detail.payments.length === 0 ? (
                <p className="rounded-xl border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                  تراکنشی برای این سفارش ثبت نشده است.
                </p>
              ) : (
                <div className="overflow-hidden rounded-xl border border-border">
                  <table className="w-full text-right text-xs">
                    <thead className="border-b border-border bg-muted/50 text-muted-foreground">
                      <tr>
                        <th className="px-3 py-2.5">مبلغ</th>
                        <th className="px-3 py-2.5">درگاه</th>
                        <th className="px-3 py-2.5">وضعیت</th>
                        <th className="px-3 py-2.5">تاریخ</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {detail.payments.map((p) => (
                        <tr key={p.id}>
                          <td className="px-3 py-2.5 font-mono font-bold">
                            {formatPrice(rialsToToman(p.amountRial))}
                          </td>
                          <td className="px-3 py-2.5">
                            {PAYMENT_PROVIDER_LABELS[p.provider] ?? p.provider}
                          </td>
                          <td className="px-3 py-2.5">
                            <Badge variant="outline" className="text-[10px]">
                              {p.status}
                            </Badge>
                          </td>
                          <td className="px-3 py-2.5 text-muted-foreground">
                            {new Date(p.createdAt).toLocaleString("fa-IR")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Timeline */}
            <section className="space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
                <History className="h-4 w-4 text-primary" />
                تاریخچهٔ وضعیت
              </h3>
              {detail.timeline.length === 0 ? (
                <p className="rounded-xl border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                  رویدادی ثبت نشده است.
                </p>
              ) : (
                <ol className="space-y-2">
                  {[...detail.timeline].reverse().map((event) => {
                    const toVisual = STATUS_VISUALS[event.toStatus as OrderStatus];
                    return (
                      <li
                        key={event.id}
                        className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-card px-3.5 py-2.5 text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <span className={cn("h-2 w-2 rounded-full", toVisual?.dot ?? "bg-muted-foreground")} />
                          <span className="font-medium text-foreground">
                            {toVisual?.label ?? event.toStatus}
                          </span>
                          {event.reason && (
                            <span className="text-muted-foreground">— {event.reason}</span>
                          )}
                        </div>
                        <span className="shrink-0 text-muted-foreground">
                          {new Date(event.createdAt).toLocaleString("fa-IR")}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              )}
            </section>

            {detail.notes && (
              <section className="rounded-2xl border border-border p-4">
                <h3 className="mb-2 text-sm font-bold text-foreground">یادداشت سفارش</h3>
                <p className="whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
                  {detail.notes}
                </p>
              </section>
            )}

            <div className="flex justify-end">
              <Button variant="outline" size="sm" onClick={onClose} className="gap-1.5 text-xs">
                <RefreshCw className="hidden h-3.5 w-3.5" />
                بستن
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
