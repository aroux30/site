"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BadgeCheck, RefreshCw, Store, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiErrorMessage } from "@/lib/api/error-message";
import { formatJalaliDateTime } from "@/lib/date";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import {
  commissionPercent,
  fetchMyEarnings,
  isNotASellerError,
  type SellerEarnings,
} from "@/lib/api/seller";

/**
 * Seller dashboard: what this account has earned by selling.
 *
 * `GET /vendors/me` answers **404 when the user has no vendor** — a normal
 * onboarding state, not a failure. This page distinguishes the two: a 404 shows
 * the sign-up invitation, while any other error shows the failure. Telling a
 * user "something went wrong" when the truth is "you never registered" sends
 * them hunting for a bug instead of using the form.
 *
 * All amounts are integer rials. `commission_rate` is basis points (1000 = 10%)
 * and is converted only for display.
 */
export default function AccountSellerPage() {
  const [earnings, setEarnings] = useState<SellerEarnings | null>(null);
  const [notASeller, setNotASeller] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotASeller(false);
    try {
      const result = await fetchMyEarnings();
      setEarnings(result);
      if (!result) setError("اطلاعات درآمد فروشندگی بازگردانده نشد.");
    } catch (err) {
      if (isNotASellerError(err)) {
        // The backend's "you have no vendor yet" — an invitation, not an error.
        setNotASeller(true);
        setEarnings(null);
      } else {
        setError(
          apiErrorMessage(err, "دریافت اطلاعات فروشندگی ناموفق بود. لطفاً دوباره تلاش کنید."),
        );
        setEarnings(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const commission = commissionPercent(earnings?.commissionRate ?? null);

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-foreground">
            <Store className="h-5 w-5 text-primary" />
            فروشندگی در بازارگاه
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            فروش کالا، مشاهده درآمد و کمیسیون پلتفرم.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`ms-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          تازه‌سازی
        </Button>
      </div>

      {loading ? (
        <Card className="p-12 text-center text-sm text-muted-foreground">
          در حال دریافت اطلاعات...
        </Card>
      ) : error ? (
        <Card
          role="alert"
          className="flex flex-col items-center justify-center gap-3 p-12 text-center"
        >
          <XMark />
          <p className="font-semibold text-foreground">دریافت اطلاعات ناموفق بود</p>
          <p className="max-w-md text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" onClick={() => void load()}>
            تلاش مجدد
          </Button>
          <p className="text-[11px] text-muted-foreground">
            این پیام به‌معنای نبود فروشگاه نیست؛ وضعیت در این لحظه خوانده نشد.
          </p>
        </Card>
      ) : notASeller ? (
        <Card className="flex flex-col items-center justify-center gap-3 p-12 text-center">
          <Store className="h-12 w-12 text-muted-foreground/40" aria-hidden="true" />
          <p className="font-semibold text-foreground">
            هنوز برای فروشندگی ثبت‌نام نکرده‌اید
          </p>
          <p className="max-w-md text-sm text-muted-foreground">
            با ثبت‌نام، می‌توانید کالاهای خود را در بازارگاه عرضه کنید. برای تسویه
            درآمد، شماره شبا و کد ملی شما لازم است.
          </p>
          <Button asChild className="mt-2">
            <Link href="/account/seller/register">شروع ثبت‌نام فروشندگی</Link>
          </Button>
        </Card>
      ) : earnings ? (
        <>
          <Card className="space-y-3 p-4">
            <div className="flex items-center gap-2">
              <BadgeCheck className="h-5 w-5 text-primary" aria-hidden="true" />
              <h2 className="text-sm font-bold text-foreground">
                {earnings.storeName}
              </h2>
            </div>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <Metric label="فروش کل" value={earnings.totalSales} />
              <Metric label="کمیسیون پلتفرم" value={earnings.commissionAmount} />
              <Metric label="درآمد خالص من" value={earnings.netEarnings} strong />
              <Metric label="تسویه‌شده" value={earnings.settledAmount} />
              <Metric label="مانده تسویه‌نشده" value={earnings.pendingSettlement} />
              <div>
                <dt className="text-[11px] text-muted-foreground">نرخ کمیسیون</dt>
                <dd className="mt-0.5 font-mono text-sm text-foreground">
                  {commission === null
                    ? "—"
                    : `${toPersianDigits(String(commission))}٪`}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-muted-foreground">تعداد سفارش</dt>
                <dd className="mt-0.5 font-mono text-sm text-foreground">
                  {earnings.totalOrders === null
                    ? "—"
                    : toPersianDigits(String(earnings.totalOrders))}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-muted-foreground">اقلام فروخته‌شده</dt>
                <dd className="mt-0.5 font-mono text-sm text-foreground">
                  {earnings.totalItems === null
                    ? "—"
                    : toPersianDigits(String(earnings.totalItems))}
                </dd>
              </div>
            </dl>
            {(earnings.periodStart || earnings.periodEnd) && (
              <p className="text-[11px] text-muted-foreground">
                بازه محاسبه: {formatJalaliDateTime(earnings.periodStart)} تا{" "}
                {formatJalaliDateTime(earnings.periodEnd)}
              </p>
            )}
          </Card>

          <Card className="space-y-3 p-4">
            <h2 className="flex items-center gap-2 text-sm font-bold text-foreground">
              <Wallet className="h-4 w-4 text-primary" aria-hidden="true" />
              تسویه درآمد
            </h2>
            <p className="text-sm leading-6 text-muted-foreground">
              مانده تسویه‌نشده توسط تیم مالی پلتفرم به شماره شبای ثبت‌شده در
              پروفایل شما واریز می‌شود. برای تغییر اطلاعات تسویه به بخش ویرایش
              پروفایل فروشگاه بروید.
            </p>
            <Button asChild variant="outline">
              <Link href="/account/seller/profile">ویرایش پروفایل فروشگاه</Link>
            </Button>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function Metric({
  label,
  value,
  strong,
}: {
  label: string;
  value: number | null;
  strong?: boolean;
}) {
  return (
    <div>
      <dt className="text-[11px] text-muted-foreground">{label}</dt>
      <dd
        className={`mt-0.5 font-mono ${strong ? "text-base font-bold" : "text-sm"} text-foreground`}
      >
        {value === null ? "—" : formatPrice(Math.trunc(value / 10))}
      </dd>
    </div>
  );
}

function XMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-12 w-12 text-destructive/60"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <path d="m15 9-6 6M9 9l6 6" />
    </svg>
  );
}
