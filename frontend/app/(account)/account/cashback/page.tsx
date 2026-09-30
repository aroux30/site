"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Coins, RefreshCw, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiErrorMessage } from "@/lib/api/error-message";
import { formatJalaliDateTime } from "@/lib/date";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import {
  cashbackStatusLabel,
  cashbackStatusVariant,
  fetchCashbackHistory,
  type CashbackTransaction,
} from "@/lib/api/cashback-customer";

const PAGE_SIZE = 20;

/**
 * The customer's own cashback history.
 *
 * A failed read is shown as a failure, never as "you have no cashback": the
 * endpoint returns a paged slice, and both an empty page and a broken request
 * leave the list empty. The customer cannot otherwise tell whether they were
 * ever credited for a purchase, so the page states which of the two happened
 * and reports how many older entries were not loaded.
 *
 * Amounts are integer rials and are displayed as reported — no client-side
 * summing, so the page can never disagree with the ledger.
 */
export default function AccountCashbackPage() {
  const [items, setItems] = useState<CashbackTransaction[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [older, setOlder] = useState<number | null>(null);
  const [invalid, setInvalid] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    // Clear the failure as the retry starts, so a recovered read stops showing
    // a stale error.
    setError(null);
    try {
      const history = await fetchCashbackHistory({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setItems(history.items);
      setTotal(history.total);
      // Only rows AFTER this page are "older"; missingCount also counts
      // the newer rows already shown on later pages.
      setOlder(history.olderCount);
      setInvalid(history.invalidCount);
    } catch (err) {
      setError(
        apiErrorMessage(err, "دریافت تاریخچه کش‌بک ناموفق بود. لطفاً دوباره تلاش کنید."),
      );
      setItems([]);
      setTotal(null);
      setOlder(null);
      setInvalid(0);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  const totalPages = total === null ? null : Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-foreground">
            <Coins className="h-5 w-5 text-primary" />
            کش‌بک من
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            بازگشت وجه‌هایی که برای خریدهای شما محاسبه شده است.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`ms-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          تازه‌سازی
        </Button>
      </div>

      {invalid > 0 && (
        <div
          role="status"
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300"
        >
          {toPersianDigits(invalid)} مورد از تراکنش‌های بازگشتی با ساختار شناخته‌شده
          این نسخه از رابط مطابقت نداشت و نمایش داده نشد. این موارد نادیده گرفته
          نشده‌اند؛ برای بررسی با پشتیبانی تماس بگیرید.
        </div>
      )}

      {older !== null && older > 0 && (
        <div
          role="status"
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300"
        >
          {toPersianDigits(older)} تراکنش قدیمی‌تر وجود دارد که در این صفحه بارگذاری
          نشده است. برای دیدن آن‌ها صفحه را جلو ببرید.
        </div>
      )}

      {error ? (
        <Card
          role="alert"
          className="flex flex-col items-center justify-center gap-3 p-12 text-center"
        >
          <Wallet className="h-12 w-12 text-destructive/60" aria-hidden="true" />
          <p className="font-semibold text-foreground">دریافت تاریخچه کش‌بک ناموفق بود</p>
          <p className="max-w-md text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" onClick={() => void load()}>
            تلاش مجدد
          </Button>
          <p className="text-[11px] text-muted-foreground">
            این پیام به‌معنای نبود کش‌بک نیست؛ تاریخچه در این لحظه خوانده نشد.
          </p>
        </Card>
      ) : loading ? (
        <Card className="p-12 text-center text-sm text-muted-foreground">
          در حال دریافت تاریخچه...
        </Card>
      ) : items.length === 0 ? (
        <Card className="flex flex-col items-center justify-center gap-2 p-12 text-center">
          <Coins className="h-12 w-12 text-muted-foreground/40" aria-hidden="true" />
          <p className="font-semibold text-foreground">هنوز کش‌بکی ثبت نشده است</p>
          <p className="max-w-md text-sm text-muted-foreground">
            با خرید از فروشگاه، در صورت فعال بودن قواعد کش‌بک، مبلغی به کیف پول شما
            بازمی‌گردد و اینجا نمایش داده می‌شود.
          </p>
          <Button asChild variant="outline" className="mt-2">
            <Link href="/products">مشاهده فروشگاه</Link>
          </Button>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <caption className="sr-only">
                فهرست تراکنش‌های کش‌بک به ترتیب تاریخ
              </caption>
              <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3">مبلغ</th>
                  <th scope="col" className="px-4 py-3">وضعیت</th>
                  <th scope="col" className="px-4 py-3">شماره سفارش</th>
                  <th scope="col" className="px-4 py-3">تاریخ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {items.map((tx) => (
                  <tr key={tx.id}>
                    <td className="px-4 py-3 font-mono">
                      {tx.amount === null
                        ? "—"
                        : formatPrice(Math.trunc(tx.amount / 10))}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={cashbackStatusVariant(tx.status)}>
                        {cashbackStatusLabel(tx.status)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/account/orders/${tx.orderId}`}
                        className="font-mono text-xs text-primary hover:underline"
                        dir="ltr"
                      >
                        {tx.orderId.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {formatJalaliDateTime(tx.createdAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {totalPages !== null && totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0 || loading}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            قبلی
          </Button>
          <span className="text-xs text-muted-foreground">
            صفحه {toPersianDigits(String(page + 1))} از {toPersianDigits(String(totalPages))}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= totalPages || loading}
            onClick={() => setPage((p) => p + 1)}
          >
            بعدی
          </Button>
        </div>
      )}
    </div>
  );
}
