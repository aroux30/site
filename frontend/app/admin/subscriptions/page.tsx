"use client";

import { useState } from "react";
import {
  Repeat,
  RefreshCw,
  PlayCircle,
  AlertTriangle,
  CheckCircle2,
  CreditCard,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { useToast } from "@/components/ui/use-toast";
import {
  adminSubscriptionsApi,
  type Subscription,
  type SubscriptionDetail,
} from "@/lib/api/subscriptions";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { toPersianDigits, formatPrice } from "@/lib/utils";

const SUBSCRIPTIONS_QUERY_KEY = "admin-subscriptions" as const;

const STATUS_LABELS: Record<string, string> = {
  active: "فعال",
  paused: "متوقف",
  past_due: "پرداخت معوق",
  cancelled: "لغو شده",
  expired: "منقضی",
};

const INTERVAL_LABELS: Record<string, string> = {
  weekly: "هفتگی",
  monthly: "ماهانه",
  quarterly: "فصلی",
  yearly: "سالانه",
  custom_days: "روز سفارشی",
};

export default function AdminSubscriptionsPage() {
  const { toast } = useToast();
  const [statusFilter, setStatusFilter] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SubscriptionDetail | null>(null);
  const [runningDue, setRunningDue] = useState(false);

  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery<Subscription[]>({
    queryKey: [SUBSCRIPTIONS_QUERY_KEY, statusFilter],
    queryFn: () =>
      adminSubscriptionsApi.list({
        status: statusFilter || undefined,
        limit: 200,
      }),
    // The old page reported a load failure ONLY as a toast and then rendered
    // an empty table, so the description travels with the message to keep
    // that text on screen.
    fallbackError: "خطا در دریافت اشتراک‌ها: دسترسی subscriptions:read لازم است.",
    toastOnError: true,
  });
  const subs: Subscription[] = data ?? [];
  const runMutation = useAdminMutation();

  const billNow = async (id: string) => {
    setBusyId(id);
    const result = await runMutation(
      () => adminSubscriptionsApi.billNow(id),
      {
        fallbackError: "صورتحساب انجام نشد",
        invalidateKeys: [[SUBSCRIPTIONS_QUERY_KEY]],
        onSuccess: (billing) => {
          toast({
            title: `نتیجه صورتحساب: ${billing.status}`,
            description: billing.last_error ?? undefined,
            variant: billing.status === "paid" ? "success" : "destructive",
          });
        },
      },
    );
    if (!result.ok) {
      toast({ title: "صورتحساب انجام نشد", variant: "destructive" });
    }
    setBusyId(null);
  };

  const runDue = async () => {
    setRunningDue(true);
    const result = await runMutation(
      () => adminSubscriptionsApi.runDue(),
      {
        fallbackError: "اجرای سراسری ناموفق بود",
        invalidateKeys: [[SUBSCRIPTIONS_QUERY_KEY]],
        onSuccess: (summary) => {
          toast({
            title: "اجرای سراسری انجام شد",
            description: `سررسید: ${toPersianDigits(String(summary.due))} | موفق: ${toPersianDigits(String(summary.paid))} | ناموفق: ${toPersianDigits(String(summary.failed))} | در انتظار: ${toPersianDigits(String(summary.skipped))}`,
            variant: summary.errors > 0 ? "destructive" : "success",
          });
        },
      },
    );
    if (!result.ok) {
      toast({ title: "اجرای سراسری ناموفق بود", variant: "destructive" });
    }
    setRunningDue(false);
  };

  const columns: DataTableColumn<Subscription>[] = [
    {
      key: "name",
      header: "اشتراک",
      render: (s) => (
        <div>
          <p className="font-medium">{s.name}</p>
          <p className="font-mono text-[10px] text-muted-foreground" dir="ltr">
            {s.id.slice(0, 8)}
          </p>
        </div>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (s) => (
        <Badge
          variant={
            s.status === "active"
              ? "default"
              : s.status === "past_due"
                ? "destructive"
                : "secondary"
          }
        >
          {STATUS_LABELS[s.status] ?? s.status}
        </Badge>
      ),
    },
    {
      key: "interval",
      header: "دوره",
      render: (s) => INTERVAL_LABELS[s.interval] ?? s.interval,
    },
    {
      key: "total",
      header: "مبلغ هر دوره",
      render: (s) => formatPrice(Math.trunc(s.total_per_cycle / 10)),
    },
    {
      key: "card",
      header: "پرداخت",
      render: (s) => (
        <span className="flex items-center gap-1 text-xs">
          <CreditCard className="h-3.5 w-3.5 text-muted-foreground" />
          {s.saved_method_id ? "خودکار" : "دستی"}
        </span>
      ),
    },
    {
      key: "failures",
      header: "خطاهای متوالی",
      render: (s) =>
        s.failure_count > 0 ? (
          <span className="flex items-center gap-1 text-destructive">
            <AlertTriangle className="h-3.5 w-3.5" />
            {toPersianDigits(String(s.failure_count))}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "next",
      header: "دوره بعد",
      render: (s) =>
        s.next_billing_at
          ? toPersianDigits(new Date(s.next_billing_at).toLocaleDateString("fa-IR"))
          : "—",
    },
    {
      key: "actions",
      header: "",
      render: (s) => (
        <Button
          variant="outline"
          size="sm"
          disabled={busyId === s.id}
          onClick={() => billNow(s.id)}
        >
          <PlayCircle className="ms-1.5 h-3.5 w-3.5" />
          صورتحساب فوری
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Repeat className="h-5 w-5 text-primary" />
            اشتراک‌های دوره‌ای
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            مدیریت اشتراک‌های کاربران — صورتحساب خودکار هر ۱۵ دقیقه برای
            دوره‌های سررسیدشده اجرا می‌شود.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="ms-2 h-4 w-4" />
            بروزرسانی
          </Button>
          <Button size="sm" disabled={runningDue} onClick={runDue}>
            <PlayCircle className="ms-2 h-4 w-4" />
            اجرای سراسری سررسیدها
          </Button>
        </div>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setStatusFilter("")}
            className={`rounded-full px-3 py-1 text-xs transition-colors ${
              statusFilter === ""
                ? "bg-primary text-primary-foreground"
                : "bg-muted hover:bg-muted/80"
            }`}
          >
            همه
          </button>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <button
              key={value}
              onClick={() => setStatusFilter(value)}
              className={`rounded-full px-3 py-1 text-xs transition-colors ${
                statusFilter === value
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-10">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : subs.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          اشتراکی یافت نشد
        </Card>
      ) : (
        <Card className="p-1">
          <DataTable
            columns={columns}
            rows={subs}
            rowKey={(s) => s.id}
            loading={loading}
            onRowClick={(s) => setDetail(s as SubscriptionDetail)}
          />
        </Card>
      )}

      {detail && (
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-bold">
              تاریخچه دوره‌ها — {detail.name}
            </h3>
            <Button variant="ghost" size="sm" onClick={() => setDetail(null)}>
              بستن
            </Button>
          </div>
          {"billings" in detail && (detail as SubscriptionDetail).billings?.length ? (
            <div className="space-y-1.5">
              {(detail as SubscriptionDetail).billings.map((b) => (
                <div
                  key={b.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded bg-muted/40 px-3 py-2 text-xs"
                >
                  <span className="flex items-center gap-2">
                    دوره {toPersianDigits(String(b.period_index + 1))}
                    <Badge
                      variant={
                        b.status === "paid"
                          ? "default"
                          : b.status === "failed"
                            ? "destructive"
                            : "secondary"
                      }
                    >
                      {b.status}
                    </Badge>
                    {b.status === "paid" && (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    )}
                    {b.last_error && (
                      <span className="text-destructive">{b.last_error}</span>
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
                    <span>تلاش: {toPersianDigits(String(b.attempt_count))}</span>
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              برای مشاهده تاریخچه، از دکمه «جزئیات» استفاده کنید یا هنوز دوره‌ای
              ثبت نشده است.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
