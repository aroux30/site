"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Ban,
  CheckCircle2,
  Download,
  FileText,
  Hash,
  Link2,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { saveBlob } from "@/lib/api/data-exchange";
import { toPersianDigits } from "@/lib/utils";
import { apiErrorMessage } from "@/lib/api/error-message";
import { useAdminQuery } from "@/lib/api/admin-query";
import {
  invoicingApi,
  type ChainVerification,
  type Invoice,
} from "@/lib/api/invoicing";

const STATUS_LABELS: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  posted: { label: "صادرشده", variant: "secondary" },
  paid: { label: "پرداخت‌شده", variant: "default" },
  cancelled: { label: "باطل", variant: "destructive" },
};

function formatToman(rial: number | undefined): string {
  if (rial === undefined || rial === null) return "—";
  const sign = rial < 0 ? "- " : "";
  return `${sign}${toPersianDigits(Math.trunc(Math.abs(rial) / 10).toLocaleString("en-US"))} تومان`;
}

function formatDate(dt: string | null): string {
  return dt ? new Date(dt).toLocaleString("fa-IR") : "—";
}

export default function AdminInvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const { toast } = useToast();
  const [acting, setActing] = useState(false);
  const [cancelReason, setCancelReason] = useState("");

  const {
    data: detail,
    loading,
    error,
    reload: load,
  } = useAdminQuery<{ invoice: Invoice; chain: ChainVerification | null }>({
    queryKey: ["admin", "invoices", params.id],
    enabled: Boolean(params.id),
    queryFn: async () => {
      const [inv, report] = await Promise.all([
        invoicingApi.get(params.id!),
        invoicingApi.verifyChain().catch(() => null),
      ]);
      return { invoice: inv, chain: report };
    },
    fallbackError: "دریافت سند ناموفق بود",
  });
  const invoice = detail?.invoice ?? null;
  const chain = detail?.chain ?? null;

  const doPost = async () => {
    if (!invoice) return;
    setActing(true);
    try {
      const updated = await invoicingApi.post(invoice.id);
      await load();
      toast({ title: "سند صادر شد", description: updated.number ?? "" });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({ title: "خطا", description: detail ?? "صدور سند ناموفق بود", variant: "destructive" });
    } finally {
      setActing(false);
    }
  };

  const doCancel = async () => {
    if (!invoice || !cancelReason.trim()) {
      toast({ title: "دلیل ابطال الزامی است", variant: "destructive" });
      return;
    }
    setActing(true);
    try {
      await invoicingApi.cancel(invoice.id, cancelReason.trim());
      await load();
      setCancelReason("");
      toast({ title: "سند باطل شد" });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({ title: "خطا", description: detail ?? "ابطال سند ناموفق بود", variant: "destructive" });
    } finally {
      setActing(false);
    }
  };

  const doMarkPaid = async () => {
    if (!invoice) return;
    setActing(true);
    try {
      await invoicingApi.markPaid(invoice.id);
      await load();
      toast({ title: "سند پرداخت‌شده ثبت شد" });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({ title: "خطا", description: detail ?? "ثبت پرداخت ناموفق بود", variant: "destructive" });
    } finally {
      setActing(false);
    }
  };

  const doDownload = async () => {
    if (!invoice) return;
    try {
      const blob = await invoicingApi.downloadArchive(invoice.id);
      saveBlob(blob, `${invoice.number ?? invoice.id}.html`);
    } catch {
      toast({ title: "فایل بایگانی یافت نشد", variant: "destructive" });
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-muted-foreground">در حال بارگذاری...</div>;
  }
  if (error || !invoice) {
    return <div className="p-8 text-center text-destructive">{error ?? "سند یافت نشد"}</div>;
  }

  const statusMeta = STATUS_LABELS[invoice.status] ?? { label: invoice.status, variant: "outline" as const };
  const isCredit = invoice.type === "credit_note";

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            {isCredit ? "سند اعتباری" : "فاکتور"}{" "}
            <span className="font-mono text-primary">{invoice.number ?? "(پیش‌نویس)"}</span>
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            سفارش:{" "}
            <a className="text-primary hover:underline" href={`/admin/orders/${invoice.order_id}`}>
              {invoice.order_id.slice(0, 8)}…
            </a>
            {invoice.fiscal_period && (
              <> | دوره مالی: {toPersianDigits(invoice.fiscal_period)}</>
            )}
          </p>
        </div>
        <Badge variant={statusMeta.variant} className="text-sm">
          {statusMeta.label}
        </Badge>
      </div>

      {/* Chain status banner */}
      {chain && (
        <Card
          className={`p-4 flex items-center gap-3 border ${
            chain.valid ? "border-green-500/40 bg-green-500/5" : "border-destructive/40 bg-destructive/5"
          }`}
        >
          {chain.valid ? (
            <ShieldCheck className="h-5 w-5 text-green-600" />
          ) : (
            <ShieldAlert className="h-5 w-5 text-destructive" />
          )}
          <span className="text-sm">
            {chain.valid
              ? `زنجیره رمزنگاری سالم است (${toPersianDigits(chain.documents_checked)} سند بررسی شد)`
              : `زنجیره شکسته است — اولین سند مخدوش: ${chain.first_broken?.number ?? "نامشخص"}`}
          </span>
        </Card>
      )}

      {/* Credit note linkage */}
      {isCredit && invoice.credit_for_id && (
        <Card className="p-4 flex items-center gap-3">
          <Link2 className="h-4 w-4 text-primary" />
          <span className="text-sm">
            این سند اعتباری متصل به فاکتور{" "}
            <a className="font-mono text-primary hover:underline" href={`/admin/invoices/${invoice.credit_for_id}`}>
              {invoice.credit_for_id.slice(0, 8)}…
            </a>{" "}
            است{invoice.credit_reason ? ` — ${invoice.credit_reason}` : ""}
          </span>
        </Card>
      )}

      {/* Actions */}
      <Card className="p-4 flex flex-wrap items-center gap-3">
        {invoice.status === "draft" && (
          <Button onClick={() => void doPost()} disabled={acting}>
            <CheckCircle2 className="h-4 w-4 ms-1" />
            صدور سند (تخصیص شماره و هش)
          </Button>
        )}
        {invoice.status === "posted" && (
          <Button variant="outline" onClick={() => void doMarkPaid()} disabled={acting}>
            <CheckCircle2 className="h-4 w-4 ms-1" />
            ثبت پرداخت
          </Button>
        )}
        {invoice.has_archive && (
          <Button variant="outline" onClick={() => void doDownload()}>
            <Download className="h-4 w-4 ms-1" />
            دانلود سند بایگانی‌شده
          </Button>
        )}
        {(invoice.status === "draft" || invoice.status === "posted") && (
          <div className="flex items-center gap-2">
            <input
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="دلیل ابطال…"
              className="h-9 w-56 rounded-md border border-input bg-background px-3 text-xs"
            />
            <Button variant="destructive" onClick={() => void doCancel()} disabled={acting}>
              <Ban className="h-4 w-4 ms-1" />
              ابطال
            </Button>
          </div>
        )}
      </Card>

      {/* Totals + customer */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-6 space-y-2">
          <h3 className="mb-3 font-semibold">خلاصه مالی</h3>
          {[
            ["جمع اقلام", invoice.totals?.subtotal],
            ["تخفیف", invoice.totals?.discount],
            ["مالیات ارزش افزوده", invoice.totals?.tax],
            ["هزینه ارسال", invoice.totals?.shipping],
          ].map(([label, val]) => (
            <div key={label as string} className="flex justify-between text-sm">
              <span className="text-muted-foreground">{label}</span>
              <span className="font-mono">{formatToman(val as number | undefined)}</span>
            </div>
          ))}
          <div className="mt-2 flex justify-between border-t pt-2 text-base font-bold">
            <span>مبلغ نهایی</span>
            <span className={`font-mono ${isCredit ? "text-destructive" : "text-primary"}`}>
              {formatToman(invoice.totals?.total)}
            </span>
          </div>
        </Card>

        <Card className="p-6 space-y-2">
          <h3 className="mb-3 font-semibold">مشخصات خریدار</h3>
          {[
            ["نام", invoice.customer?.name],
            ["تلفن", invoice.customer?.phone],
            ["کد ملی", invoice.customer?.national_code],
            ["استان / شهر", [invoice.customer?.province, invoice.customer?.city].filter(Boolean).join(" / ") || null],
            ["نشانی", invoice.customer?.address],
            ["کد پستی", invoice.customer?.postal_code],
          ].map(([label, val]) => (
            <div key={label as string} className="flex justify-between gap-4 text-sm">
              <span className="shrink-0 text-muted-foreground">{label}</span>
              <span className="text-left">{(val as string | null) ?? "—"}</span>
            </div>
          ))}
        </Card>
      </div>

      {/* Lines */}
      <Card className="p-6">
        <h3 className="mb-4 font-semibold">اقلام سند</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground">
                <th className="py-2 text-right">ردیف</th>
                <th className="text-right">شرح کالا</th>
                <th className="text-right">کد</th>
                <th className="text-center">تعداد</th>
                <th className="text-left">مبلغ واحد</th>
                <th className="text-left">مبلغ کل</th>
              </tr>
            </thead>
            <tbody>
              {invoice.lines.map((ln) => (
                <tr key={ln.id} className="border-b last:border-0">
                  <td className="py-2 font-mono">{toPersianDigits(ln.position)}</td>
                  <td>{ln.product_name}</td>
                  <td className="font-mono text-xs">{ln.sku ?? "—"}</td>
                  <td className="text-center font-mono">{toPersianDigits(ln.quantity)}</td>
                  <td className="text-left font-mono">{formatToman(ln.unit_price)}</td>
                  <td className="text-left font-mono font-bold">{formatToman(ln.total_price)}</td>
                </tr>
              ))}
              {invoice.lines.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-muted-foreground">
                    قلمی ثبت نشده است
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Hash chain metadata */}
      <Card className="p-6 space-y-3">
        <h3 className="flex items-center gap-2 font-semibold">
          <Hash className="h-4 w-4 text-primary" />
          اثر انگشت رمزنگاری (زنجیره ضددستکاری)
        </h3>
        <div className="space-y-2 text-xs">
          <div>
            <span className="text-muted-foreground">هش سند: </span>
            <span className="font-mono break-all" dir="ltr">{invoice.hash ?? "—"}</span>
          </div>
          <div>
            <span className="text-muted-foreground">هش سند قبلی در زنجیره: </span>
            <span className="font-mono break-all" dir="ltr">{invoice.previous_hash ?? "—"}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 pt-2 text-muted-foreground sm:grid-cols-4">
            <span>صدور: {formatDate(invoice.issued_at)}</span>
            <span>پست: {formatDate(invoice.posted_at)}</span>
            <span>پرداخت: {formatDate(invoice.paid_at)}</span>
            <span>ابطال: {formatDate(invoice.cancelled_at)}</span>
          </div>
          {invoice.cancel_reason && (
            <p className="text-destructive">دلیل ابطال: {invoice.cancel_reason}</p>
          )}
        </div>
      </Card>
    </div>
  );
}
