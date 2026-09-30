"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  ArrowRightLeft,
  CheckCircle2,
  Hash,
  Link2,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { PageLoader } from "@/components/shared/page-state";
import { toPersianDigits } from "@/lib/utils";
import { accountingApi, type JournalEntry, type JournalEntryStatus } from "@/lib/api/accounting";
import { apiErrorMessage } from "@/lib/api/error-message";
import { useAdminQuery } from "@/lib/api/admin-query";

const STATUS_LABELS: Record<
  JournalEntryStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  draft: { label: "پیش‌نویس", variant: "outline" },
  posted: { label: "ثبت‌شده", variant: "secondary" },
  reversed: { label: "برگشت‌خورده", variant: "destructive" },
};

/** Operator-facing text for a failed request — see lib/api/error-message.ts. */
const apiMessage = apiErrorMessage;

const SOURCE_LABELS: Record<string, string> = {
  order: "سفارش (شناسایی درآمد)",
  payment: "پرداخت (وصول مطالبات)",
  refund: "بازگشت وجه / سند اعتباری",
  wallet: "کیف پول کاربران",
  settlement: "تسویه با فروشنده",
  manual: "سند دستی",
};

function formatRial(rial: number | undefined): string {
  if (rial === undefined || rial === null) return "—";
  return `${toPersianDigits(Math.trunc(rial).toLocaleString("en-US"))} ریال`;
}

export default function AdminJournalEntryDetailPage() {
  const params = useParams<{ id: string }>();
  const { toast } = useToast();
  const [acting, setActing] = useState(false);
  const [reason, setReason] = useState("");

  const {
    data: entry = null,
    loading,
    error,
    reload: load,
  } = useAdminQuery<JournalEntry | null>({
    queryKey: ["admin", "accounting", "journal", params.id],
    enabled: Boolean(params.id),
    queryFn: async () => {
      return await accountingApi.getEntry(params.id!);
    },
    fallbackError: "دریافت سند ناموفق بود",
  });

  const doPost = async () => {
    if (!entry) return;
    setActing(true);
    try {
      const updated = await accountingApi.postEntry(entry.id);
      await load();
      toast({ title: "سند ثبت شد", description: updated.number ?? "" });
    } catch (err: unknown) {
      toast({
        title: "خطا",
        description: apiMessage(err, "ثبت سند ناموفق بود"),
        variant: "destructive",
      });
    } finally {
      setActing(false);
    }
  };

  const doReverse = async () => {
    if (!entry) return;
    if (!reason.trim()) {
      toast({ title: "دلیل برگشت الزامی است", variant: "destructive" });
      return;
    }
    setActing(true);
    try {
      const reversal = await accountingApi.reverseEntry(entry.id, reason.trim());
      toast({
        title: "سند برگشتی ثبت شد",
        description: reversal.number ?? "",
      });
      window.location.href = `/admin/accounting/journal/${reversal.id}`;
    } catch (err: unknown) {
      toast({
        title: "خطا",
        description: apiMessage(err, "برگشت سند ناموفق بود"),
        variant: "destructive",
      });
    } finally {
      setActing(false);
    }
  };

  if (loading) return <PageLoader message="در حال دریافت سند..." />;

  if (error || !entry) {
    return (
      <Card className="p-6 text-sm text-destructive" dir="rtl">
        {error ?? "سند یافت نشد"}
      </Card>
    );
  }

  const meta = STATUS_LABELS[entry.status] ?? {
    label: entry.status,
    variant: "outline" as const,
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <ScrollText className="h-5 w-5 text-primary" />
            سند حسابداری{" "}
            <span className="font-mono text-primary">
              {entry.number ?? "(پیش‌نویس)"}
            </span>
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {SOURCE_LABELS[entry.source_type] ?? entry.source_type}
            {entry.fiscal_period && <> | دوره مالی: {toPersianDigits(entry.fiscal_period)}</>}
            {entry.source_id && (
              <>
                {" "}| مرجع: <span className="font-mono">{entry.source_id.slice(0, 12)}…</span>
              </>
            )}
          </p>
        </div>
        <Badge variant={meta.variant} className="text-sm">
          {meta.label}
        </Badge>
      </div>

      {!entry.balanced && (
        <Card className="flex items-center gap-3 border border-destructive/40 bg-destructive/5 p-4">
          <ShieldAlert className="h-5 w-5 text-destructive" />
          <span className="text-sm">
            این سند تراز نیست — بدهکار {formatRial(entry.total_debit_rial)} در برابر بستانکار{" "}
            {formatRial(entry.total_credit_rial)}
          </span>
        </Card>
      )}

      {entry.reversal_of_id && (
        <Card className="flex items-center gap-3 p-4">
          <Link2 className="h-4 w-4 text-primary" />
          <span className="text-sm">
            این سند، برگشتِ سند{" "}
            <a
              className="font-mono text-primary hover:underline"
              href={`/admin/accounting/journal/${entry.reversal_of_id}`}
            >
              {entry.reversal_of_id.slice(0, 8)}…
            </a>{" "}
            است{entry.reversal_reason ? ` — ${entry.reversal_reason}` : ""}
          </span>
        </Card>
      )}

      <Card className="flex flex-wrap items-center gap-3 p-4">
        {entry.status === "draft" && (
          <Button onClick={() => void doPost()} disabled={acting}>
            <CheckCircle2 className="h-4 w-4 ms-1" />
            ثبت سند (تخصیص شماره و هش)
          </Button>
        )}
        {entry.status === "posted" && (
          <div className="flex items-center gap-2">
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="دلیل برگشت سند…"
              className="h-9 w-64 rounded-md border border-input bg-background px-3 text-xs"
            />
            <Button variant="destructive" onClick={() => void doReverse()} disabled={acting}>
              <ArrowRightLeft className="h-4 w-4 ms-1" />
              برگشت سند
            </Button>
          </div>
        )}
        {entry.status === "reversed" && (
          <span className="text-sm text-muted-foreground">
            این سند برگشت خورده است و تغییر آن مجاز نیست؛ اصلاح فقط با سند جدید ممکن است.
          </span>
        )}
      </Card>

      <Card className="p-4">
        <h3 className="mb-2 text-sm font-bold">شرح سند</h3>
        <p className="text-sm text-muted-foreground">{entry.description || "—"}</p>
      </Card>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-3">ردیف</th>
                <th scope="col" className="px-4 py-3">کد حساب</th>
                <th scope="col" className="px-4 py-3">نام حساب</th>
                <th scope="col" className="px-4 py-3">شرح ردیف</th>
                <th scope="col" className="px-4 py-3">بدهکار</th>
                <th scope="col" className="px-4 py-3">بستانکار</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {entry.lines.map((line) => (
                <tr key={line.id}>
                  <td className="px-4 py-3 text-muted-foreground">
                    {toPersianDigits(line.position)}
                  </td>
                  <td className="px-4 py-3 font-mono">
                    {line.account_code ? toPersianDigits(line.account_code) : "—"}
                  </td>
                  <td className="px-4 py-3">{line.account_name_fa ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {line.description ?? "—"}
                  </td>
                  <td className="px-4 py-3 font-mono">
                    {line.debit_rial > 0 ? formatRial(line.debit_rial) : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono">
                    {line.credit_rial > 0 ? formatRial(line.credit_rial) : "—"}
                  </td>
                </tr>
              ))}
              <tr className="bg-muted/40 font-bold">
                <td className="px-4 py-3" colSpan={4}>
                  جمع
                </td>
                <td className="px-4 py-3 font-mono">{formatRial(entry.total_debit_rial)}</td>
                <td className="px-4 py-3 font-mono">{formatRial(entry.total_credit_rial)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      {(entry.hash || entry.previous_hash) && (
        <Card className="space-y-2 p-4 text-xs">
          <h3 className="flex items-center gap-2 text-sm font-bold">
            <Hash className="h-4 w-4" />
            زنجیره ضددستکاری
          </h3>
          {entry.status === "posted" || entry.status === "reversed" ? (
            <p className="flex items-center gap-2 text-green-600">
              <ShieldCheck className="h-3.5 w-3.5" />
              این سند در زنجیره هش دوره ثبت شده است
            </p>
          ) : null}
          <p className="text-muted-foreground" dir="ltr">
            <span className="font-mono">{entry.hash ?? "—"}</span>
          </p>
          <p className="text-muted-foreground" dir="ltr">
            <span className="font-mono">{entry.previous_hash ?? "—"}</span>
          </p>
        </Card>
      )}
    </div>
  );
}
