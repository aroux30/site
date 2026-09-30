"use client";

/**
 * Mock payment gateway (development only).
 *
 * The backend MockProvider builds a gateway URL pointing here with
 * `authority`, `callback` and `amount` (Rials). The page mimics a real
 * gateway: it shows the amount and redirects back to the provider callback
 * with `status=OK` (pay) or `status=NOK` (cancel). The callback page then
 * asks the backend to verify — the server, never this page, owns payment
 * truth (QA B24: this route used to 404, breaking the whole pay flow).
 */

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ShieldCheck, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatPrice, toPersianDigits } from "@/lib/utils";

function MockGatewayContent() {
  const searchParams = useSearchParams();
  const [submitting, setSubmitting] = useState<"OK" | "NOK" | null>(null);

  const authority = searchParams.get("authority") ?? "";
  const callback = searchParams.get("callback") ?? "";
  const amountRials = Number(searchParams.get("amount") ?? "0");
  const amountToman = Math.round(amountRials / 10);

  const redirectTo = (status: "OK" | "NOK") => {
    if (!callback) return;
    const sep = callback.includes("?") ? "&" : "?";
    window.location.href = `${callback}${sep}authority=${encodeURIComponent(authority)}&status=${status}`;
  };

  const pay = (status: "OK" | "NOK") => {
    setSubmitting(status);
    // Small delay so the user sees the pressed state, like a real gateway.
    setTimeout(() => redirectTo(status), 600);
  };

  const merchant = useMemo(() => "فروشگاه آنلاین ایرانین", []);

  if (!authority || !callback || !amountRials) {
    return (
      <div className="container-page flex min-h-[60vh] items-center justify-center py-12">
        <Card className="max-w-md p-8 text-center">
          <h1 className="mb-3 text-lg font-bold text-foreground">درگاه آزمایشی در دسترس نیست</h1>
          <p className="text-sm text-muted-foreground">
            پارامترهای تراکنش (authority / callback / amount) کامل نیستند. از صفحه پرداخت سفارش دوباره تلاش کنید.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="container-page flex min-h-[70vh] items-center justify-center py-10" dir="rtl">
      <Card className="w-full max-w-lg overflow-hidden shadow-xl">
        {/* Gateway header */}
        <div className="flex items-center justify-between border-b border-border bg-muted/60 px-6 py-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-emerald-600" />
            <span className="text-sm font-bold text-foreground">درگاه پرداخت آزمایشی (Mock)</span>
          </div>
          <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-[10px] font-bold text-amber-600">
            محیط تست — پول واقعی جابه‌جا نمی‌شود
          </span>
        </div>

        <div className="space-y-4 p-6">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">پذیرنده:</span>
            <span className="font-bold text-foreground">{merchant}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">شماره پیگیری تراکنش:</span>
            <span className="font-mono text-xs text-foreground" dir="ltr">
              {toPersianDigits(authority.slice(0, 21))}
            </span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-primary/5 px-4 py-3">
            <span className="text-sm text-muted-foreground">مبلغ قابل پرداخت:</span>
            <span className="text-lg font-black text-primary">{formatPrice(amountToman)}</span>
          </div>

          <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-2 text-[11px] text-muted-foreground">
            <Lock className="h-3.5 w-3.5" />
            این درگاه فقط برای توسعه است؛ پس از انتخاب، به صفحه تأیید پرداخت فروشگاه برمی‌گردید.
          </div>

          <div className="grid grid-cols-1 gap-3 pt-2 sm:grid-cols-2">
            <Button
              onClick={() => pay("OK")}
              disabled={submitting !== null}
              className="h-12 bg-emerald-600 font-bold text-white hover:bg-emerald-700"
            >
              {submitting === "OK" ? "در حال انتقال…" : "پرداخت موفق (تست)"}
            </Button>
            <Button
              onClick={() => pay("NOK")}
              disabled={submitting !== null}
              variant="outline"
              className="h-12 font-bold"
            >
              {submitting === "NOK" ? "در حال انتقال…" : "انصراف / پرداخت ناموفق"}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default function MockGatewayPage() {
  return (
    <Suspense
      fallback={
        <div className="container-page flex min-h-[60vh] items-center justify-center py-12">
          <p className="text-sm text-muted-foreground">در حال بارگذاری درگاه…</p>
        </div>
      }
    >
      <MockGatewayContent />
    </Suspense>
  );
}
