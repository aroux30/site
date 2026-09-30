"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Repeat,
  RefreshCw,
  Pause,
  Play,
  XCircle,
  AlertTriangle,
  CheckCircle2,
  CreditCard,
  ShoppingBag,
  ArrowRight,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  subscriptionsApi,
  type Subscription,
  type SubscriptionDetail,
} from "@/lib/api/subscriptions";
import { toPersianDigits, formatPrice } from "@/lib/utils";

const STATUS_LABELS: Record<string, string> = {
  active: "فعال",
  paused: "متوقف",
  past_due: "پرداخت معوق",
  cancelled: "لغو شده",
  expired: "منقضی",
};

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  paused: "secondary",
  past_due: "destructive",
  cancelled: "outline",
  expired: "outline",
};

const INTERVAL_LABELS: Record<string, string> = {
  weekly: "هفتگی",
  monthly: "ماهانه",
  quarterly: "فصلی",
  yearly: "سالانه",
  custom_days: "روز سفارشی",
};

const BILLING_LABELS: Record<string, string> = {
  paid: "پرداخت شده",
  failed: "ناموفق",
  pending: "در انتظار",
  skipped: "در انتظار پرداخت شما",
};

function intervalText(sub: Subscription): string {
  const base = INTERVAL_LABELS[sub.interval] ?? sub.interval;
  if (sub.interval === "custom_days" && sub.custom_interval_days) {
    return `هر ${toPersianDigits(String(sub.custom_interval_days))} روز`;
  }
  if (sub.interval_count > 1) {
    return `هر ${toPersianDigits(String(sub.interval_count))} ${base}`;
  }
  return base;
}

export default function SubscriptionsPage() {
  const { toast } = useToast();
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<SubscriptionDetail | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setSubs(await subscriptionsApi.list());
    } catch {
      toast({
        title: "خطا در دریافت اشتراک‌ها",
        variant: "destructive",
      });
      setSubs([]);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleDetail = async (id: string) => {
    if (expanded === id) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    try {
      const d = await subscriptionsApi.get(id);
      setDetail(d);
      setExpanded(id);
    } catch {
      toast({ title: "خطا در دریافت جزئیات", variant: "destructive" });
    }
  };

  const act = async (
    id: string,
    action: "pause" | "resume" | "cancel",
  ) => {
    setBusyId(id);
    try {
      if (action === "pause") await subscriptionsApi.pause(id);
      else if (action === "resume") await subscriptionsApi.resume(id);
      else await subscriptionsApi.cancel(id);
      toast({
        title:
          action === "pause"
            ? "اشتراک متوقف شد"
            : action === "resume"
              ? "اشتراک فعال شد"
              : "اشتراک لغو شد",
        variant: "success",
      });
      await load();
      if (expanded === id) setExpanded(null);
    } catch {
      toast({ title: "عملیات انجام نشد", variant: "destructive" });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="container mx-auto max-w-4xl px-4 py-8" dir="rtl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-black">
            <Repeat className="h-6 w-6 text-primary" />
            اشتراک‌های من
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            خریدهای دوره‌ای خودکار — هر دوره به‌صورت خودکار از کارت ذخیره‌شده
            پرداخت می‌شود یا برای پرداخت دستی به شما اطلاع می‌دهیم.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="ms-2 h-4 w-4" />
          بروزرسانی
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : subs.length === 0 ? (
        <Card className="p-10 text-center">
          <Repeat className="mx-auto mb-4 h-10 w-10 text-muted-foreground/50" />
          <p className="mb-1 font-bold">هنوز اشتراکی ندارید</p>
          <p className="mb-6 text-sm text-muted-foreground">
            اشتراک‌ها برای خریدهای تکرارشونده (مثل شارژ ماهانه کد دیجیتال) مناسب‌اند.
          </p>
          <Link href="/products">
            <Button variant="outline" className="gap-2">
              <ShoppingBag className="h-4 w-4" />
              مشاهده محصولات
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </Card>
      ) : (
        <div className="space-y-3">
          {subs.map((sub) => (
            <Card key={sub.id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate font-bold">{sub.name}</h3>
                    <Badge variant={STATUS_VARIANTS[sub.status] ?? "outline"}>
                      {STATUS_LABELS[sub.status] ?? sub.status}
                    </Badge>
                    {sub.status === "past_due" && (
                      <span className="flex items-center gap-1 text-xs text-destructive">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        پرداخت دوره قبل ناموفق بود
                      </span>
                    )}
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span>{intervalText(sub)}</span>
                    <span className="flex items-center gap-1">
                      {sub.saved_method_id ? (
                        <>
                          <CreditCard className="h-3.5 w-3.5" />
                          پرداخت خودکار از کارت ذخیره‌شده
                        </>
                      ) : (
                        "پرداخت دستی هر دوره"
                      )}
                    </span>
                    <span>
                      مبلغ هر دوره: {formatPrice(Math.trunc(sub.total_per_cycle / 10))}
                    </span>
                    {sub.next_billing_at && sub.status === "active" && (
                      <span>
                        دوره بعد:{" "}
                        {toPersianDigits(
                          new Date(sub.next_billing_at).toLocaleDateString("fa-IR"),
                        )}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleDetail(sub.id)}
                  >
                    {expanded === sub.id ? "بستن" : "جزئیات"}
                  </Button>
                  {sub.status === "active" || sub.status === "past_due" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busyId === sub.id}
                      onClick={() => act(sub.id, "pause")}
                    >
                      <Pause className="ms-1.5 h-3.5 w-3.5" />
                      توقف
                    </Button>
                  ) : sub.status === "paused" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busyId === sub.id}
                      onClick={() => act(sub.id, "resume")}
                    >
                      <Play className="ms-1.5 h-3.5 w-3.5" />
                      فعال‌سازی
                    </Button>
                  ) : null}
                  {sub.status !== "cancelled" && sub.status !== "expired" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      disabled={busyId === sub.id}
                      onClick={() => act(sub.id, "cancel")}
                    >
                      <XCircle className="ms-1.5 h-3.5 w-3.5" />
                      لغو
                    </Button>
                  )}
                </div>
              </div>

              {expanded === sub.id && detail && detail.id === sub.id && (
                <div className="mt-4 space-y-4 border-t pt-4">
                  {/* Items */}
                  <div>
                    <p className="mb-2 text-xs font-semibold text-muted-foreground">
                      اقلام این اشتراک
                    </p>
                    <div className="space-y-1.5">
                      {detail.items.map((item) => (
                        <div
                          key={item.id}
                          className="flex items-center justify-between rounded bg-muted/40 px-3 py-2 text-xs"
                        >
                          <span>
                            {item.product_name}
                            <span className="ms-2 font-mono text-muted-foreground" dir="ltr">
                              {item.sku}
                            </span>
                          </span>
                          <span className="text-muted-foreground">
                            {toPersianDigits(String(item.quantity))} ×{" "}
                            {/* Raw DB column (Rial), same as the catalog API
                              divides on the way out. Verified: order_items
                              .unit_price equals this column exactly. */}
                            {formatPrice(Math.trunc(item.unit_price_rial / 10))}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Billing history */}
                  <div>
                    <p className="mb-2 text-xs font-semibold text-muted-foreground">
                      تاریخچه دوره‌ها
                    </p>
                    {detail.billings.length === 0 ? (
                      <p className="text-xs text-muted-foreground">
                        هنوز دوره‌ای صورتحساب نشده است.
                      </p>
                    ) : (
                      <div className="space-y-1.5">
                        {detail.billings.map((b) => (
                          <div
                            key={b.id}
                            className="flex flex-wrap items-center justify-between gap-2 rounded bg-muted/40 px-3 py-2 text-xs"
                          >
                            <span className="flex items-center gap-2">
                              <span>
                                دوره {toPersianDigits(String(b.period_index + 1))}
                              </span>
                              <Badge
                                variant={
                                  b.status === "paid"
                                    ? "default"
                                    : b.status === "failed"
                                      ? "destructive"
                                      : "secondary"
                                }
                              >
                                {BILLING_LABELS[b.status] ?? b.status}
                              </Badge>
                              {b.status === "paid" && (
                                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                              )}
                            </span>
                            <span className="flex items-center gap-3 text-muted-foreground">
                              <span>{formatPrice(Math.trunc(b.amount_rial / 10))}</span>
                              {b.billed_at && (
                                <span>
                                  {toPersianDigits(
                                    new Date(b.billed_at).toLocaleDateString("fa-IR"),
                                  )}
                                </span>
                              )}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
