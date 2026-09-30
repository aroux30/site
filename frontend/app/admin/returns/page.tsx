"use client";

import { useState } from "react";
import { PackageX, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { FilterSelect } from "@/components/admin/filter-select";
import {
  MissingDataNotice,
  PartialDataNotice,
} from "@/components/admin/async-state";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { formatJalaliDateTime } from "@/lib/date";
import { formatRial, toPersianDigits } from "@/lib/utils";
import {
  INSPECTION_OUTCOMES,
  RETURN_STATUSES,
  RETURN_STATUS_LABELS,
  allowedReturnTransitions,
  fetchReturns,
  inspectionOutcomeLabel,
  returnStatusLabel,
  transitionReturn,
  type OrderReturn,
} from "@/lib/api/returns";

const RETURNS_QUERY_KEY = "admin-returns" as const;

type BadgeVariant =
  | "default"
  | "secondary"
  | "destructive"
  | "outline"
  | "success"
  | "warning"
  | "info";

const STATUS_BADGE_VARIANTS: Record<string, BadgeVariant> = {
  requested: "warning",
  under_review: "warning",
  approved: "info",
  rejected: "destructive",
  received: "secondary",
  inspected: "secondary",
  refunded: "success",
  replaced: "success",
  closed: "outline",
};

/**
 * Customer return requests (RMA) — admin processing.
 *
 * The action dialog offers ONLY the transitions the backend state machine will
 * accept for the return's current status. `RETURN_TRANSITIONS` is mirrored from
 * the domain module on purpose: presenting a move the server rejects would read
 * as a platform failure when the real answer is simply that the return has not
 * reached that stage yet.
 *
 * A refund moves money, so the amount is collected as integer rials, sent only
 * on the `refunded` move, and never computed on the client — the backend
 * validates it against the return's own items.
 */
export default function AdminReturnsPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [target, setTarget] = useState<OrderReturn | null>(null);
  const [nextStatus, setNextStatus] = useState("");
  const [notes, setNotes] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  // Inspection outcome per order item, keyed by order_item_id.
  const [outcomes, setOutcomes] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const runMutation = useAdminMutation();

  const { data, loading, error, reload } = useAdminQuery({
    queryKey: [RETURNS_QUERY_KEY, statusFilter],
    queryFn: () => fetchReturns({ status: statusFilter, pageSize: 50 }),
    fallbackError: "دریافت درخواست‌های مرجوعی ناموفق بود",
  });
  const returns: OrderReturn[] = data?.items ?? [];
  // An RMA hidden by a cap or a contract drift is a customer promise the
  // merchant cannot see, so the shortfall is stated rather than implied away.
  const missingCount = data?.missingCount ?? null;
  const invalidCount = data?.invalidCount ?? 0;

  const openTransition = (row: OrderReturn) => {
    setTarget(row);
    const allowed = allowedReturnTransitions(row.status);
    setNextStatus(allowed[0] ?? "");
    setNotes("");
    setRefundAmount(row.refundAmount ? String(row.refundAmount) : "");
    setOutcomes({});
    setFormError(null);
  };

  const allowed = target ? allowedReturnTransitions(target.status) : [];
  const needsInspection = nextStatus === "inspected";
  const needsRefund = nextStatus === "refunded";

  const submit = async () => {
    if (!target || !nextStatus) return;
    setFormError(null);

    let refundRials: number | null = null;
    if (needsRefund) {
      const parsed = Number.parseInt(refundAmount.replace(/[^\d]/g, ""), 10);
      if (!Number.isFinite(parsed) || parsed < 0) {
        setFormError("مبلغ بازپرداخت باید یک عدد صحیح ریالی نامنفی باشد.");
        return;
      }
      refundRials = parsed;
    }

    // Every returned item must carry an outcome before an inspection can post.
    if (needsInspection) {
      const missing = target.items.filter((item) => !outcomes[item.orderItemId]);
      if (missing.length > 0) {
        setFormError("برای بازرسی، تعیین نتیجه هر قلم مرجوعی الزامی است.");
        return;
      }
    }

    setSaving(true);
    const result = await runMutation(
      () =>
        transitionReturn(target.id, {
          target: nextStatus,
          notes: notes.trim() || null,
          inspectionOutcomes: needsInspection ? outcomes : null,
          refundAmount: needsRefund ? refundRials : null,
        }),
      { fallbackError: "اعمال تغییر وضعیت مرجوعی ناموفق بود" },
    );
    if (result.ok) {
      setTarget(null);
      await reload();
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const columns: DataTableColumn<OrderReturn>[] = [
    {
      key: "rma",
      header: "شماره RMA",
      render: (r) => (
        <div>
          <div className="font-mono text-xs font-bold text-foreground" dir="ltr">
            {r.rmaNumber ?? r.id.slice(0, 8)}
          </div>
          <div className="font-mono text-[11px] text-muted-foreground" dir="ltr">
            {r.orderId.slice(0, 8)}
          </div>
        </div>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (r) => (
        <Badge variant={STATUS_BADGE_VARIANTS[r.status] ?? "outline"}>
          {returnStatusLabel(r.status)}
        </Badge>
      ),
    },
    {
      key: "items",
      header: "اقلام",
      render: (r) => (
        <span className="text-xs">
          {toPersianDigits(String(r.items.length))} قلم
        </span>
      ),
    },
    {
      key: "refund",
      header: "مبلغ بازپرداخت",
      hideOnMobile: true,
      render: (r) =>
        r.refundAmount === null || r.refundAmount === 0 ? (
          <span className="text-xs text-muted-foreground">—</span>
        ) : (
          <span className="font-mono">{formatRial(r.refundAmount)}</span>
        ),
    },
    {
      key: "created",
      header: "تاریخ ثبت",
      hideOnMobile: true,
      render: (r) => (
        <span className="text-xs text-muted-foreground">
          {formatJalaliDateTime(r.createdAt)}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (r) =>
        allowedReturnTransitions(r.status).length === 0 ? (
          <span className="text-xs text-muted-foreground">بسته‌شده</span>
        ) : (
          <Button variant="outline" size="sm" onClick={() => openTransition(r)}>
            تغییر وضعیت
          </Button>
        ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <PackageX className="h-5 w-5 text-primary" />
            درخواست‌های مرجوعی (RMA)
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            رسیدگی به مرجوعی‌ها در چرخه تأیید ← دریافت ← بازرسی ← بازپرداخت یا
            جایگزینی ← بستن. هر تغییر فقط در صورت مجاز بودن در ماشین وضعیت سرور
            قابل اعمال است.
          </p>
        </div>
        <Button variant="outline" onClick={() => void reload()}>
          <RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی
        </Button>
      </section>

      <div className="max-w-xs">
        <FilterSelect
          id="return-status-filter"
          label="وضعیت"
          value={statusFilter}
          options={[
            { value: "all", label: "همه وضعیت‌ها" },
            ...RETURN_STATUSES.map((s) => ({
              value: s as string,
              label: RETURN_STATUS_LABELS[s] ?? s,
            })),
          ]}
          onChange={setStatusFilter}
        />
      </div>

      <PartialDataNotice count={invalidCount} label="مرجوعی‌های بازگشتی" />
      <MissingDataNotice count={missingCount ?? 0} label="درخواست‌های مرجوعی" />

      <DataTable
        columns={columns}
        rows={returns}
        rowKey={(r) => r.id}
        loading={loading}
        error={error}
        emptyMessage="درخواست مرجوعی‌ای ثبت نشده است"
        emptyDescription="درخواست‌های ثبت‌شده توسط مشتریان در این فهرست نمایش داده می‌شوند."
      />

      <Dialog
        open={target !== null}
        onOpenChange={(open) => {
          if (!open) setTarget(null);
        }}
      >
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>
              تغییر وضعیت مرجوعی {target?.rmaNumber ?? target?.id.slice(0, 8)}
            </DialogTitle>
          </DialogHeader>

          {target && (
            <div className="space-y-4 py-2">
              <div className="rounded-md border border-border bg-muted/30 p-3 text-xs">
                <div className="text-muted-foreground">
                  وضعیت فعلی:{" "}
                  <span className="font-medium text-foreground">
                    {returnStatusLabel(target.status)}
                  </span>
                </div>
              </div>

              <FilterSelect
                id="rma-next-status"
                label="وضعیت مقصد"
                value={nextStatus}
                options={allowed.map((s) => ({
                  value: s,
                  label: RETURN_STATUS_LABELS[s] ?? s,
                }))}
                onChange={setNextStatus}
              />

              {needsInspection && (
                <div className="space-y-3 rounded-md border border-border p-3">
                  <p className="text-[11px] font-medium text-muted-foreground">
                    نتیجه بازرسی هر قلم
                  </p>
                  {target.items.map((item) => (
                    <div key={item.orderItemId} className="space-y-1">
                      <div className="font-mono text-[11px] text-muted-foreground" dir="ltr">
                        {item.orderItemId.slice(0, 8)} — {item.reason}
                      </div>
                      <FilterSelect
                        id={`outcome-${item.orderItemId}`}
                        label="نتیجه"
                        value={outcomes[item.orderItemId] ?? ""}
                        options={[
                          { value: "", label: "— انتخاب کنید —" },
                          ...INSPECTION_OUTCOMES.map((o) => ({
                            value: o as string,
                            label: inspectionOutcomeLabel(o),
                          })),
                        ]}
                        onChange={(v) =>
                          setOutcomes({ ...outcomes, [item.orderItemId]: v })
                        }
                      />
                      {item.inspectionOutcome && (
                        <p className="text-[11px] text-muted-foreground">
                          نتیجه ثبت‌شده پیشین: {inspectionOutcomeLabel(item.inspectionOutcome)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {needsRefund && (
                <div className="space-y-1.5">
                  <label
                    htmlFor="rma-refund"
                    className="block text-[11px] font-medium text-muted-foreground"
                  >
                    مبلغ بازپرداخت (ریال)
                  </label>
                  <Input
                    id="rma-refund"
                    value={refundAmount}
                    onChange={(e) => setRefundAmount(e.target.value)}
                    dir="ltr"
                    className="font-mono"
                  />
                  {refundAmount.trim() &&
                    Number.parseInt(refundAmount, 10) >= 0 && (
                      <p className="text-[11px] text-muted-foreground">
                        {formatRial(Number.parseInt(refundAmount, 10))}
                      </p>
                    )}
                  <p className="text-[11px] text-amber-700 dark:text-amber-400">
                    با ثبت این تغییر، مبلغ بازپرداخت توسط سرور پردازش و به مشتری
                    بازگردانده می‌شود.
                  </p>
                </div>
              )}

              <div className="space-y-1.5">
                <label
                  htmlFor="rma-notes"
                  className="block text-[11px] font-medium text-muted-foreground"
                >
                  یادداشت (اختیاری)
                </label>
                <Input
                  id="rma-notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>
            </div>
          )}

          {formError && (
            <p role="alert" className="text-sm text-destructive">
              {formError}
            </p>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setTarget(null)}>
              انصراف
            </Button>
            <Button
              variant={needsRefund ? "destructive" : "default"}
              disabled={saving || !nextStatus}
              onClick={() => void submit()}
            >
              {saving ? "در حال اعمال..." : "اعمال تغییر"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
