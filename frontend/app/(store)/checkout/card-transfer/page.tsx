"use client";

import React, { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, ArrowRight, Clock, Copy, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { formatCardNumber } from "@/lib/iranian-commerce";
import { formatPrice } from "@/lib/utils";
import apiClient from "@/lib/api/client";

/**
 * Card-to-card receipt submission screen.
 *
 * This is the URL the card_transfer provider advertises as its `gateway_url`
 * (`/checkout/card-transfer?authority=…&order_id=…`). It is reached both when
 * a customer completes checkout with card-to-card and when they come back
 * later via the payment link, because abandoning the transfer leaves the
 * order unpaid.
 *
 * The payment is looked up server-side (the payment id and the merchant card
 * details cannot be reconstructed client-side) and stays PENDING until an
 * admin reviews the submitted slip.
 */

interface PendingPayment {
  id: string;
  status: string;
  amount: number;
  authority?: string | null;
  extra_data?: Record<string, unknown> | null;
}

function CardTransferForm() {
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const orderId = searchParams.get("order_id");

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [payment, setPayment] = useState<PendingPayment | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [trackingCode, setTrackingCode] = useState("");
  const [cardPan, setCardPan] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");

  const load = useCallback(async () => {
    if (!orderId) {
      setLoadError("شناسه سفارش در آدرس یافت نشد.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const { data } = await apiClient.get<PendingPayment | null>(
        `/payments/by-order/${orderId}`
      );
      if (!data) {
        // No pending card-to-card payment: either it was already reviewed or
        // the order was never a card-to-card order.
        setNotFound(true);
      } else {
        setPayment(data);
      }
    } catch (err: unknown) {
      setLoadError(
        (err as { message?: string })?.message ||
          "دریافت اطلاعات پرداخت با خطا مواجه شد."
      );
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting || !payment) return;

    const tracking = trackingCode.trim();
    if (!tracking) {
      setSubmitError("شماره پیگیری / شماره ارجاع واریز الزامی است.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      await apiClient.post(`/payments/${payment.id}/card-receipt`, {
        tracking_code: tracking,
        card_pan: cardPan.trim() || null,
      });
      setSubmitted(true);
      toast({
        title: "فیش واریز ثبت شد",
        description: "پس از بررسی و تأیید مدیریت، سفارش شما تکمیل می‌شود.",
        variant: "success",
      });
    } catch (err: unknown) {
      setSubmitError(
        (err as { message?: string })?.message ||
          "ثبت فیش واریز با خطا مواجه شد. لطفاً دوباره تلاش کنید."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const extra = payment?.extra_data ?? {};
  const cardNumber = extra.card_number ? String(extra.card_number) : "";
  const formattedCardNumber = formatCardNumber(cardNumber);
  const cardHolder = extra.card_holder ? String(extra.card_holder) : "";
  const bankName = extra.bank_name ? String(extra.bank_name) : "";
  const instructions = extra.instructions ? String(extra.instructions) : "";

  const copyCardNumber = async () => {
    if (!cardNumber || !navigator.clipboard?.writeText) {
      const message = "امکان کپی شماره کارت وجود ندارد. لطفاً آن را دستی وارد کنید.";
      setCopyStatus(message);
      toast({ title: "کپی شماره کارت ناموفق بود", description: message, variant: "destructive" });
      return;
    }

    try {
      await navigator.clipboard.writeText(cardNumber);
      const message = "شماره کارت مقصد کپی شد.";
      setCopyStatus(message);
      toast({ title: "شماره کارت کپی شد", description: message, variant: "success" });
    } catch {
      const message = "امکان کپی شماره کارت وجود ندارد. لطفاً آن را دستی وارد کنید.";
      setCopyStatus(message);
      toast({ title: "کپی شماره کارت ناموفق بود", description: message, variant: "destructive" });
    }
  };

  if (loading) {
    return (
      <div className="container-page flex min-h-[50vh] items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        در حال دریافت اطلاعات پرداخت...
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="container-page py-12">
        <Card className="mx-auto max-w-2xl space-y-4 p-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <AlertCircle className="h-7 w-7" />
          </div>
          <p className="text-sm text-muted-foreground">{loadError}</p>
          <div className="flex justify-center gap-3">
            <Button onClick={() => void load()} variant="outline">
              تلاش دوباره
            </Button>
            <Link href="/account/orders">
              <Button variant="ghost">مشاهده سفارش‌ها</Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="container-page py-12">
        <Card className="mx-auto max-w-2xl overflow-hidden border-emerald-500/30 p-8 text-center shadow-lg">
          <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <Clock className="h-10 w-10" />
          </div>
          <h1 className="mb-2 text-2xl font-extrabold text-foreground">فیش واریز ثبت شد</h1>
          <p className="mb-6 text-sm text-muted-foreground">
            اطلاعات واریز شما دریافت شد و پس از بررسی و تأیید مدیریت، سفارش تکمیل و برای شما
            ارسال خواهد شد.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Link href="/account/orders">
              <Button size="lg">پیگیری سفارش‌ها</Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  if (notFound || !payment) {
    return (
      <div className="container-page py-12">
        <Card className="mx-auto max-w-2xl space-y-4 p-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400">
            <AlertCircle className="h-7 w-7" />
          </div>
          <h1 className="text-lg font-extrabold text-foreground">
            پرداخت کارت به کارتی در انتظار نیست
          </h1>
          <p className="text-sm text-muted-foreground">
            این سفارش در حال حاضر پرداخت کارت به کارت معلقی ندارد؛ ممکن است فیش قبلاً ثبت و
            بررسی شده باشد.
          </p>
          <Link href="/account/orders">
            <Button>مشاهده سفارش‌ها</Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="container-page py-12">
      <Card className="mx-auto max-w-2xl overflow-hidden border-amber-500/30 p-8 shadow-lg">
        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400">
          <Clock className="h-10 w-10" />
        </div>

        <h1 className="mb-2 text-center text-2xl font-extrabold text-foreground">
          پرداخت کارت به کارت
        </h1>
        <p className="mb-6 text-center text-sm text-muted-foreground">
          سفارش شما در انتظار واریز است. مبلغ را به کارت زیر واریز کرده و سپس شماره پیگیری را
          ثبت کنید.
        </p>

        <div className="mb-6 space-y-3 rounded-xl border border-border bg-muted/30 p-5">
          <div className="flex items-center justify-between border-b border-border/60 pb-3">
            <span className="text-sm text-muted-foreground">مبلغ قابل واریز:</span>
            <span className="font-bold text-foreground">
              {formatPrice(Math.round(payment.amount / 10))}
            </span>
          </div>

          {cardNumber ? (
            <>
              <div className="flex items-center justify-between gap-3 border-b border-border/60 pb-3">
                <span className="text-sm text-muted-foreground">شماره کارت:</span>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-base font-bold text-foreground" dir="ltr">
                    {formattedCardNumber}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="shrink-0"
                    onClick={() => void copyCardNumber()}
                    aria-label="کپی شماره کارت مقصد"
                  >
                    <Copy className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </div>
              </div>
              <p className="sr-only" role="status" aria-live="polite">
                {copyStatus}
              </p>
              <div className="flex items-center justify-between border-b border-border/60 pb-3">
                <span className="text-sm text-muted-foreground">به نام:</span>
                <span className="font-medium text-foreground">{cardHolder}</span>
              </div>
              {bankName && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">بانک:</span>
                  <span className="font-medium text-foreground">{bankName}</span>
                </div>
              )}
            </>
          ) : (
            <p className="text-xs text-muted-foreground">
              اطلاعات کارت مقصد در دسترس نیست. لطفاً برای دریافت شماره کارت با پشتیبانی تماس
              بگیرید.
            </p>
          )}

          {payment.authority && (
            <div className="flex items-center justify-between border-t border-border/60 pt-3">
              <span className="text-sm text-muted-foreground">شماره پیگیری پرداخت:</span>
              <span className="font-mono text-xs font-bold text-muted-foreground" dir="ltr">
                {payment.authority}
              </span>
            </div>
          )}
        </div>

        {instructions && (
          <p className="mb-6 rounded-xl border border-amber-500/25 bg-amber-500/5 p-4 text-xs leading-relaxed text-muted-foreground">
            {instructions}
          </p>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="ct-tracking">شماره پیگیری / شماره ارجاع واریز</Label>
            <Input
              id="ct-tracking"
              value={trackingCode}
              onChange={(e) => setTrackingCode(e.target.value)}
              placeholder="مثال: ۱۲۳۴۵۶۷۸۹"
              dir="ltr"
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ct-pan">۴ رقم آخر کارت واریز کننده (اختیاری)</Label>
            <Input
              id="ct-pan"
              value={cardPan}
              onChange={(e) => setCardPan(e.target.value)}
              placeholder="۱۲۳۴"
              dir="ltr"
              maxLength={4}
            />
          </div>

          {submitError && (
            <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="flex flex-col gap-3 sm:flex-row">
            <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="ms-2 h-4 w-4 animate-spin" />
                  در حال ثبت فیش...
                </>
              ) : (
                "ثبت فیش واریز"
              )}
            </Button>
            <Link href="/account/orders">
              <Button type="button" variant="outline" size="lg" className="w-full sm:w-auto">
                پرداخت را بعداً تکمیل می‌کنم
                <ArrowRight className="ms-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </form>

        <p className="mt-6 text-center text-[11px] text-muted-foreground">
          مبلغ به تومان نمایش داده شده است؛ واریز بر اساس مبلغ ریالی انجام می‌شود.
        </p>
      </Card>
    </div>
  );
}

export default function CardTransferPage() {
  return (
    <Suspense
      fallback={
        <div className="container-page flex min-h-[50vh] items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <CardTransferForm />
    </Suspense>
  );
}
