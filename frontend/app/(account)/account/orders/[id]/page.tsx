"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Package,
  RefreshCw,
  ShieldCheck,
  ShieldX,
  XCircle,
} from "lucide-react";
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
import { apiErrorMessage } from "@/lib/api/error-message";
import { formatJalaliDateTime } from "@/lib/date";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import {
  cancelOrder,
  fetchOrderDetail,
  fetchOrderReturns,
  fetchPriceSnapshot,
  isCancellable,
  orderStatusLabel,
  type OrderDetail,
  type OrderRma,
  type PriceSnapshot,
} from "@/lib/api/order-detail";

/**
 * One order, as its owner sees it.
 *
 * Three reads feed this page and they fail independently, so each keeps its own
 * error: a snapshot outage must not blank the item list, and vice versa. The
 * order itself is the one hard dependency — if it fails there is nothing to
 * show, so that error replaces the page.
 *
 * The price snapshot reports `hash_valid`, computed server-side against the
 * stored SHA-256. A `false` value is a tamper signal about the customer's own
 * pricing and is surfaced loudly, never hidden. `null` means "not reported",
 * which is a different fact from "reported and failed".
 *
 * The shipping address arrives already masked by the backend. This page does
 * not attempt to unmask it.
 */
export default function AccountOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const orderId = params?.id ?? "";

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [snapshot, setSnapshot] = useState<PriceSnapshot | null>(null);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);

  const [rmas, setRmas] = useState<OrderRma[]>([]);
  const [rmaError, setRmaError] = useState<string | null>(null);

  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!orderId) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await fetchOrderDetail(orderId);
      setOrder(detail);
      if (!detail) {
        setError("سفارش یافت نشد یا به آن دسترسی ندارید.");
      }
    } catch (err) {
      setError(
        apiErrorMessage(err, "دریافت اطلاعات سفارش ناموفق بود. لطفاً دوباره تلاش کنید."),
      );
      setOrder(null);
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  // Independent reads: run alongside the order and record their own failures.
  useEffect(() => {
    if (!orderId) return;
    let alive = true;

    (async () => {
      try {
        const snap = await fetchPriceSnapshot(orderId);
        if (alive) setSnapshot(snap);
      } catch (err) {
        if (alive) {
          setSnapshotError(apiErrorMessage(err, "دریافت ریز قیمت سفارش ناموفق بود."));
        }
      }
    })();

    (async () => {
      try {
        const res = await fetchOrderReturns(orderId);
        if (alive) setRmas(res.items);
      } catch (err) {
        if (alive) {
          setRmaError(apiErrorMessage(err, "دریافت اطلاعات مرجوعی سفارش ناموفق بود."));
        }
      }
    })();

    return () => {
      alive = false;
    };
  }, [orderId]);

  const submitCancellation = async () => {
    setCancelError(null);
    // The backend requires at least 3 characters; state the rule here rather
    // than let a 422 explain it.
    if (cancelReason.trim().length < 3) {
      setCancelError("دلیل لغو باید حداقل ۳ کاراکتر باشد.");
      return;
    }
    setCancelling(true);
    try {
      await cancelOrder(orderId, cancelReason);
      setCancelOpen(false);
      setCancelReason("");
      await load();
    } catch (err) {
      setCancelError(apiErrorMessage(err, "لغو سفارش ناموفق بود."));
    } finally {
      setCancelling(false);
    }
  };

  const timeline = useMemo(() => order?.timeline ?? [], [order]);

  if (loading) {
    return (
      <div className="flex min-h-[300px] items-center justify-center" dir="rtl">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="space-y-4" dir="rtl">
        <Card
          role="alert"
          className="flex flex-col items-center justify-center gap-3 p-12 text-center"
        >
          <XCircle className="h-12 w-12 text-destructive/60" aria-hidden="true" />
          <p className="font-semibold text-foreground">نمایش سفارش ناموفق بود</p>
          <p className="max-w-md text-sm text-muted-foreground">
            {error ?? "سفارش یافت نشد یا به آن دسترسی ندارید."}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void load()}>
              تلاش مجدد
            </Button>
            <Button asChild variant="ghost">
              <Link href="/account/orders">بازگشت به فهرست سفارش‌ها</Link>
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm">
            <Link href="/account/orders">
              <ArrowRight className="ms-1 h-4 w-4" />
              سفارش‌ها
            </Link>
          </Button>
          <div>
            <h1 className="font-mono text-lg font-bold text-foreground" dir="ltr">
              {order.orderNumber || order.id.slice(0, 8)}
            </h1>
            <p className="text-xs text-muted-foreground">
              ثبت‌شده در {formatJalaliDateTime(order.createdAt)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{orderStatusLabel(order.status)}</Badge>
          {isCancellable(order.status) && (
            <Button
              variant="outline"
              size="sm"
              className="text-destructive"
              onClick={() => setCancelOpen(true)}
            >
              لغو سفارش
            </Button>
          )}
        </div>
      </div>

      {/* ── Pricing ── */}
      <Card className="space-y-3 p-4">
        <h2 className="text-sm font-bold text-foreground">مبالغ</h2>
        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
          <Line label="جمع کالاها" value={order.subtotal} />
          <Line label="هزینه ارسال" value={order.shippingCost} />
          <Line label="مالیات" value={order.tax} />
          <Line label="تخفیف" value={order.discountAmount} />
          <div className="col-span-2 sm:col-span-1">
            <dt className="text-[11px] text-muted-foreground">مبلغ نهایی پرداختی</dt>
            <dd className="mt-0.5 font-mono text-base font-bold text-foreground">
              {order.total === null ? "—" : formatPrice(Math.trunc(order.total / 10))}
            </dd>
          </div>
        </dl>
      </Card>

      {/* ── Items ── */}
      <Card className="overflow-hidden p-0">
        <h2 className="border-b border-border px-4 py-3 text-sm font-bold text-foreground">
          اقلام سفارش
        </h2>
        {order.items.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">
            این سفارش قلمی ندارد.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3">کالا</th>
                  <th scope="col" className="px-4 py-3">تعداد</th>
                  <th scope="col" className="px-4 py-3">قیمت واحد</th>
                  <th scope="col" className="px-4 py-3">جمع</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {order.items.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-foreground">
                        {item.productName || "—"}
                      </div>
                      {item.variantInfo && (
                        <div className="text-[11px] text-muted-foreground">
                          {item.variantInfo}
                        </div>
                      )}
                      <div className="font-mono text-[10px] text-muted-foreground" dir="ltr">
                        {item.sku}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono">
                      {item.quantity === null ? "—" : toPersianDigits(String(item.quantity))}
                    </td>
                    <td className="px-4 py-3 font-mono">
                      {item.unitPrice === null
                        ? "—"
                        : formatPrice(Math.trunc(item.unitPrice / 10))}
                    </td>
                    <td className="px-4 py-3 font-mono">
                      {item.totalPrice === null
                        ? "—"
                        : formatPrice(Math.trunc(item.totalPrice / 10))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ── Timeline ── */}
      {timeline.length > 0 && (
        <Card className="space-y-3 p-4">
          <h2 className="text-sm font-bold text-foreground">گردش وضعیت</h2>
          <ol className="space-y-3">
            {timeline.map((event) => (
              <li key={event.id} className="flex gap-3">
                <CheckCircle2
                  className="mt-0.5 h-4 w-4 shrink-0 text-primary"
                  aria-hidden="true"
                />
                <div>
                  <div className="text-sm text-foreground">
                    {orderStatusLabel(event.toStatus)}
                    {event.fromStatus && (
                      <span className="text-[11px] text-muted-foreground">
                        {" "}
                        (از {orderStatusLabel(event.fromStatus)})
                      </span>
                    )}
                  </div>
                  {event.reason && (
                    <div className="text-[11px] text-muted-foreground">
                      {event.reason}
                    </div>
                  )}
                  <div className="text-[11px] text-muted-foreground">
                    {formatJalaliDateTime(event.createdAt)}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {/* ── Price snapshot + tamper check ── */}
      <Card className="space-y-3 p-4">
        <h2 className="flex items-center gap-2 text-sm font-bold text-foreground">
          <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
          ریز قیمت ثبت‌شده در زمان خرید
        </h2>
        {snapshotError ? (
          <p role="alert" className="text-sm text-destructive">
            {snapshotError} — این به‌معنای نبود ریز قیمت نیست؛ در این لحظه خوانده نشد.
          </p>
        ) : !snapshot ? (
          <p className="text-sm text-muted-foreground">ریز قیمتی برای این سفارش ثبت نشده است.</p>
        ) : (
          <>
            {snapshot.hashValid === false && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-[11px] leading-relaxed text-destructive"
              >
                <ShieldX className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>
                  <span className="font-bold">هشدار:</span> مهر تأیید ریز قیمت این
                  سفارش با محتوای آن مطابقت ندارد. این وضعیت به‌معنای تغییر
                  احتمالی در اطلاعات قیمت‌گذاری است؛ لطفاً با پشتیبانی تماس بگیرید.
                </span>
              </div>
            )}
            {snapshot.hashValid === true && (
              <p className="flex items-center gap-1.5 text-[11px] text-emerald-700 dark:text-emerald-400">
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                مهر تأیید ریز قیمت معتبر است.
              </p>
            )}
            {snapshot.hashValid === null && (
              <p className="text-[11px] text-muted-foreground">
                وضعیت مهر تأیید توسط سرور گزارش نشد.
              </p>
            )}

            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Line label="جمع اقلام" value={snapshot.subtotalRial} />
              <Line label="تخفیف" value={snapshot.totalDiscountRial} />
              <Line label="مالیات" value={snapshot.totalTaxRial} />
              <Line label="ارسال" value={snapshot.shippingRial} />
            </dl>

            {snapshot.lines.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs">
                  <thead className="border-b border-border text-muted-foreground">
                    <tr>
                      <th scope="col" className="px-3 py-2">کالا</th>
                      <th scope="col" className="px-3 py-2">تعداد</th>
                      <th scope="col" className="px-3 py-2">قیمت واحد</th>
                      <th scope="col" className="px-3 py-2">تخفیف</th>
                      <th scope="col" className="px-3 py-2">مالیات</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {snapshot.lines.map((line, idx) => (
                      <tr key={`${line.variantId}-${idx}`}>
                        <td className="px-3 py-2">{line.productName || "—"}</td>
                        <td className="px-3 py-2 font-mono">
                          {line.quantity === null ? "—" : toPersianDigits(String(line.quantity))}
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {line.unitPriceRial === null
                            ? "—"
                            : formatPrice(Math.trunc(line.unitPriceRial / 10))}
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {line.discountAmountRial === null
                            ? "—"
                            : formatPrice(Math.trunc(line.discountAmountRial / 10))}
                        </td>
                        <td className="px-3 py-2 font-mono">
                          {line.taxAmountRial === null
                            ? "—"
                            : formatPrice(Math.trunc(line.taxAmountRial / 10))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </Card>

      {/* ── Returns on this order (RMA) ── */}
      {(rmas.length > 0 || rmaError) && (
        <Card className="space-y-3 p-4">
          <h2 className="flex items-center gap-2 text-sm font-bold text-foreground">
            <RefreshCw className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            درخواست‌های مرجوعی این سفارش
          </h2>
          {rmaError ? (
            <p className="text-xs text-destructive">{rmaError}</p>
          ) : (
            <div className="space-y-2">
              {rmas.map((rma) => (
                <div
                  key={rma.id}
                  className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/20 p-3 text-xs"
                >
                  <div className="space-y-1">
                    <span className="font-mono font-bold text-foreground">
                      {rma.rmaNumber || rma.id}
                    </span>
                    {rma.createdAt && (
                      <span className="block text-[11px] text-muted-foreground">
                        ثبت‌شده در {formatJalaliDateTime(rma.createdAt)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {rma.refundAmount && rma.refundAmount > 0 ? (
                      <span className="font-mono text-xs text-foreground">
                        {formatPrice(Math.trunc(rma.refundAmount / 10))}
                      </span>
                    ) : null}
                    <Badge variant="secondary" className="text-[11px]">
                      {rma.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}


      {/* ── Masked shipping address ── */}
      {order.shippingAddressMasked && (
        <Card className="space-y-2 p-4">
          <h2 className="flex items-center gap-2 text-sm font-bold text-foreground">
            <AlertTriangle className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            نشانی ارسال (پوشانده‌شده)
          </h2>
          <pre
            className="max-h-48 overflow-auto rounded-md bg-muted/40 p-3 text-[11px] leading-5 text-muted-foreground"
            dir="ltr"
          >
            {JSON.stringify(order.shippingAddressMasked, null, 2)}
          </pre>
        </Card>
      )}

      {/* ── Cancel dialog ── */}
      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent dir="rtl">
          <DialogHeader>
            <DialogTitle>لغو سفارش</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm leading-6 text-muted-foreground">
              لغو سفارش قابل بازگشت نیست. در صورت پرداخت، مبلغ طبق رویه بازپرداخت
              به شما بازگردانده می‌شود.
            </p>
            <div className="space-y-1.5">
              <label
                htmlFor="cancel-reason"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                دلیل لغو (حداقل ۳ کاراکتر)
              </label>
              <Input
                id="cancel-reason"
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
              />
            </div>
          </div>
          {cancelError && (
            <p role="alert" className="text-sm text-destructive">
              {cancelError}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelOpen(false)}>
              انصراف
            </Button>
            <Button
              variant="destructive"
              disabled={cancelling}
              onClick={() => void submitCancellation()}
            >
              {cancelling ? "در حال لغو..." : "لغو سفارش"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** One money row. Renders an explicit marker when the server did not report it. */
function Line({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <dt className="text-[11px] text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-mono text-sm text-foreground">
        {value === null ? "—" : formatPrice(Math.trunc(value / 10))}
      </dd>
    </div>
  );
}
