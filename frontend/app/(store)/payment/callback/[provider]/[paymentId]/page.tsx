"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/lib/api/client";

type VerifyState = "verifying" | "success" | "failed";

/**
 * Server-authoritative payment return page.
 *
 * Gateway query parameters (authority / status) are hints only — payment
 * truth comes exclusively from the backend verify endpoint, which validates
 * the payment with the gateway and confirms the order.
 */
function PaymentCallbackContent() {
  const routeParams = useParams<{ provider: string; paymentId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [state, setState] = useState<VerifyState>("verifying");
  const [message, setMessage] = useState<string>("");
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;

    const verify = async () => {
      const paymentId = routeParams?.paymentId;
      if (!paymentId) {
        setState("failed");
        setMessage("شناسه پرداخت یافت نشد. لطفاً از بخش سفارش‌ها وضعیت پرداخت را بررسی کنید.");
        return;
      }

      const authority =
        searchParams.get("authority") ??
        searchParams.get("Authority") ??
        searchParams.get("id") ??
        "";
      const status =
        searchParams.get("status") ??
        searchParams.get("Status") ??
        "OK";

      try {
        await apiClient.post(`/payments/${paymentId}/verify`, {
          authority,
          status,
        });
        setState("success");
        setTimeout(() => router.replace("/account/orders"), 2500);
      } catch (err) {
        setState("failed");
        setMessage(
          (err as { message?: string })?.message ||
            "تأیید پرداخت با خطا مواجه شد. در صورت کسر مبلغ، وجه حداکثر تا ۷۲ ساعت آینده به‌صورت خودکار بازگردانده می‌شود."
        );
      }
    };

    verify();
  }, [routeParams, searchParams, router]);

  if (state === "verifying") {
    return (
      <div className="container-page flex min-h-[60vh] items-center justify-center py-16">
        <Card className="w-full max-w-md border-border shadow-sm">
          <CardHeader className="text-center">
            <CardTitle className="text-lg font-bold">در حال بررسی پرداخت</CardTitle>
            <CardDescription>لطفاً چند لحظه صبر کنید و صفحه را نبندید…</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (state === "success") {
    return (
      <div className="container-page flex min-h-[60vh] items-center justify-center py-16">
        <Card className="w-full max-w-md border-emerald-200 bg-emerald-50/50 text-center shadow-sm dark:border-emerald-900 dark:bg-emerald-950/30">
          <CardHeader>
            <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-4xl dark:bg-emerald-900/60">
              ✅
            </div>
            <CardTitle className="text-lg font-bold text-emerald-700 dark:text-emerald-300">
              پرداخت شما با موفقیت انجام شد
            </CardTitle>
            <CardDescription>
              سفارش شما تأیید شد و در حال پردازش است. در حال انتقال به صفحه سفارش‌ها…
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <Button asChild>
              <Link href="/account/orders">مشاهده سفارش‌ها</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/products">ادامه خرید</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container-page flex min-h-[60vh] items-center justify-center py-16">
      <Card className="w-full max-w-md border-destructive/30 bg-red-50/50 text-center shadow-sm dark:bg-red-950/20">
        <CardHeader>
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-4xl dark:bg-red-900/60">
            ⚠️
          </div>
          <CardTitle className="text-lg font-bold text-red-700 dark:text-red-300">
            پرداخت ناموفق بود
          </CardTitle>
          <CardDescription>{message}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <Button asChild>
            <Link href="/account/orders">مشاهده سفارش‌ها</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/contact">تماس با پشتیبانی</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default function PaymentCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="container-page flex min-h-[60vh] items-center justify-center py-16">
          <Card className="w-full max-w-md border-border shadow-sm">
            <CardHeader className="text-center">
              <CardTitle className="text-lg font-bold">در حال بررسی پرداخت</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </CardContent>
          </Card>
        </div>
      }
    >
      <PaymentCallbackContent />
    </Suspense>
  );
}
