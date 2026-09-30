"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Store, ShieldCheck, ShieldX, Wallet } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
  UnavailableValue,
} from "@/components/admin/async-state";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { formatJalali } from "@/lib/date";
import { formatRial, toPersianDigits } from "@/lib/utils";
import {
  commissionPercentLabel,
  createVendorSettlement,
  fetchVendor,
  fetchVendorEarnings,
  fetchVendorPage,
  fetchVendorSettlements,
  setVendorVerification,
  settlementStatusLabel,
  settlementStatusVariant,
  updateVendorAdmin,
  type VendorListItem,
} from "@/lib/api/vendors";

const VENDORS_QUERY_KEY = "admin-vendors" as const;
const VENDOR_DETAIL_QUERY_KEY = "admin-vendor-detail" as const;

const VERIFICATION_OPTIONS = [
  { value: "all", label: "همه وضعیت‌ها" },
  { value: "verified", label: "تأییدشده" },
  { value: "unverified", label: "تأییدنشده" },
];

/**
 * Marketplace vendors (admin back-office).
 *
 * The list endpoint returns the PUBLIC vendor projection — it deliberately
 * omits commission rate, payout IBAN, and national id, and it does not carry
 * `is_active`. Those fields exist only on the single-vendor read, so this page
 * fetches the detail row before showing them. Rendering a blank commission
 * cell from the list would read as "no commission set", which is a different
 * fact from "the list does not report it".
 */
export default function AdminVendorsPage() {
  const [verification, setVerification] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Settlement form
  const [settlementOpen, setSettlementOpen] = useState(false);
  const [settlementAmount, setSettlementAmount] = useState("");
  const [settlementReference, setSettlementReference] = useState("");
  const [settlementPeriodStart, setSettlementPeriodStart] = useState("");
  const [settlementPeriodEnd, setSettlementPeriodEnd] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Commission editor state, held separately from the settlement form so a
  // failure in one does not surface inside the other.
  const [commissionInput, setCommissionInput] = useState("");
  const [savingCommission, setSavingCommission] = useState(false);
  const [commissionError, setCommissionError] = useState<string | null>(null);

  const runMutation = useAdminMutation();

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [VENDORS_QUERY_KEY, verification],
    queryFn: () =>
      fetchVendorPage({
        isVerified:
          verification === "all" ? undefined : verification === "verified",
        pageSize: 50,
      }),
    fallbackError: "دریافت فهرست فروشندگان ناموفق بود",
  });
  const vendors: VendorListItem[] = data?.items ?? [];
  // A capped or partly unreadable list must never read as the whole
  // marketplace: a vendor hidden here is a payout the operator cannot see.
  const missingCount = data?.missingCount ?? null;
  const invalidCount = data?.invalidCount ?? 0;

  const {
    data: detail,
    loading: detailLoading,
    error: detailError,
    reload: reloadDetail,
  } = useAdminQuery({
    queryKey: [VENDOR_DETAIL_QUERY_KEY, selectedId],
    queryFn: () => fetchVendor(selectedId as string),
    enabled: selectedId !== null,
    fallbackError: "دریافت جزئیات فروشنده ناموفق بود",
  });

  const {
    data: earnings,
    loading: earningsLoading,
    error: earningsError,
    reload: reloadEarnings,
  } = useAdminQuery({
    queryKey: [VENDOR_DETAIL_QUERY_KEY, selectedId, "earnings"],
    queryFn: () => fetchVendorEarnings(selectedId as string),
    enabled: selectedId !== null,
    fallbackError: "دریافت اطلاعات مالی ناموفق بود",
  });

  const {
    data: settlements,
    loading: settlementsLoading,
    error: settlementsError,
    reload: reloadSettlements,
  } = useAdminQuery({
    queryKey: [VENDOR_DETAIL_QUERY_KEY, selectedId, "settlements"],
    queryFn: () => fetchVendorSettlements(selectedId as string, { pageSize: 50 }),
    enabled: selectedId !== null,
    fallbackError: "دریافت تسویه‌ها ناموفق بود",
  });

  // Seed the commission box from the row the operator opened, and clear any
  // stale error from a previous vendor. Without this the box starts empty and
  // a save would silently overwrite the rate with whatever was typed.
  useEffect(() => {
    setCommissionError(null);
    setCommissionInput(
      detail && detail.commissionRate !== null
        ? String(commissionPercentLabel(detail.commissionRate))
        : "",
    );
  }, [detail]);

  const toggleVerification = async (vendor: VendorListItem) => {
    setBusyId(vendor.id);
    setActionError(null);
    const result = await runMutation(
      () => setVendorVerification(vendor.id, !vendor.isVerified),
      { fallbackError: "تغییر وضعیت تأیید ناموفق بود" },
    );
    if (result.ok) {
      await load();
      if (selectedId === vendor.id) await reloadDetail();
    } else {
      setActionError(result.error);
    }
    setBusyId(null);
  };

  const saveCommission = async () => {
    if (!selectedId) return;
    setCommissionError(null);

    const percent = Number(commissionInput);
    if (!Number.isFinite(percent) || percent < 0 || percent > 100) {
      setCommissionError("نرخ کمیسیون باید عددی بین ۰ تا ۱۰۰ درصد باشد.");
      return;
    }
    // Backend takes basis points (1000 = 10%). Truncated, not rounded: the
    // stored unit is an integer and rounding a money rate is not acceptable.
    const basisPoints = Math.trunc(percent * 100);

    setSavingCommission(true);
    const result = await runMutation(
      () => updateVendorAdmin(selectedId, { commissionRate: basisPoints }),
      { fallbackError: "ذخیره نرخ کمیسیون ناموفق بود" },
    );
    if (result.ok) {
      await reloadDetail();
      // The earnings panel is computed from the rate, so it is now stale.
      await reloadEarnings();
    } else {
      setCommissionError(result.error);
    }
    setSavingCommission(false);
  };

  const submitSettlement = async () => {
    if (!selectedId) return;
    const amount = Number.parseInt(settlementAmount.replace(/[^\d]/g, ""), 10);
    if (!Number.isFinite(amount) || amount < 1) {
      setFormError("مبلغ تسویه باید یک عدد صحیح ریالی بزرگ‌تر از صفر باشد.");
      return;
    }
    setSaving(true);
    setFormError(null);
    const result = await runMutation(
      () =>
        createVendorSettlement(selectedId, {
          amount,
          periodStart: settlementPeriodStart
            ? new Date(settlementPeriodStart).toISOString()
            : null,
          periodEnd: settlementPeriodEnd
            ? new Date(`${settlementPeriodEnd}T23:59:59`).toISOString()
            : null,
          paymentReference: settlementReference.trim() || null,
        }),
      { fallbackError: "ثبت تسویه ناموفق بود" },
    );
    if (result.ok) {
      setSettlementOpen(false);
      setSettlementAmount("");
      setSettlementReference("");
      setSettlementPeriodStart("");
      setSettlementPeriodEnd("");
      await reloadSettlements();
      await reloadEarnings();
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const columns: DataTableColumn<VendorListItem>[] = [
    {
      key: "store",
      header: "فروشگاه",
      render: (v) => (
        <div>
          <div className="font-medium text-foreground">{v.storeName}</div>
          <div className="font-mono text-[11px] text-muted-foreground" dir="ltr">
            {v.slug}
          </div>
        </div>
      ),
    },
    {
      key: "verified",
      header: "تأیید",
      render: (v) =>
        v.isVerified ? (
          <Badge variant="success" className="gap-1">
            <ShieldCheck className="h-3 w-3" aria-hidden="true" />
            تأییدشده
          </Badge>
        ) : (
          <Badge variant="outline" className="gap-1">
            <ShieldX className="h-3 w-3" aria-hidden="true" />
            تأییدنشده
          </Badge>
        ),
    },
    {
      key: "rating",
      header: "امتیاز",
      hideOnMobile: true,
      render: (v) =>
        v.rating === null ? (
          <UnavailableValue reason="امتیاز گزارش نشد." />
        ) : (
          <span className="font-mono">{toPersianDigits(v.rating.toFixed(1))}</span>
        ),
    },
    {
      key: "sales",
      header: "تعداد فروش",
      hideOnMobile: true,
      render: (v) =>
        v.totalSalesCount === null ? (
          <UnavailableValue reason="گزارش نشد." />
        ) : (
          <span className="font-mono">{toPersianDigits(String(v.totalSalesCount))}</span>
        ),
    },
    {
      key: "created",
      header: "تاریخ ثبت",
      hideOnMobile: true,
      render: (v) => (
        <span className="text-xs text-muted-foreground">{formatJalali(v.createdAt)}</span>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (v) => (
        <div className="flex gap-1">
          <Button variant="outline" size="sm" onClick={() => setSelectedId(v.id)}>
            جزئیات
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={busyId === v.id}
            onClick={() => void toggleVerification(v)}
          >
            {v.isVerified ? "لغو تأیید" : "تأیید"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Store className="h-5 w-5 text-primary" />
            فروشندگان بازارگاه
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            تأیید هویت فروشندگان، مشاهده درآمد و کمیسیون پلتفرم، و ثبت تسویه‌های
            پرداختی. مبالغ به ریال صحیح نمایش داده می‌شوند.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()}>
          <RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی
        </Button>
      </section>

      <Card className="p-4">
        <div className="max-w-xs">
          <FilterSelect
            id="vendor-verification"
            label="وضعیت تأیید"
            value={verification}
            options={VERIFICATION_OPTIONS}
            onChange={setVerification}
          />
        </div>
      </Card>

      {actionError && (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
        >
          {actionError}
        </div>
      )}

      <PartialDataNotice count={invalidCount} label="فروشندگان بازگشتی" />
      <MissingDataNotice count={missingCount ?? 0} label="فروشندگان" />

      <DataTable
        columns={columns}
        rows={vendors}
        rowKey={(v) => v.id}
        loading={loading}
        error={error}
        emptyMessage="فروشنده‌ای ثبت نشده است"
        emptyDescription="پس از ثبت‌نام نخستین فروشنده، فهرست او اینجا نمایش داده می‌شود."
      />

      {/* ── Vendor detail ── */}
      <Dialog
        open={selectedId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedId(null);
            setActionError(null);
          }
        }}
      >
        <DialogContent className="max-w-3xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>جزئیات فروشنده</DialogTitle>
          </DialogHeader>

          {detailError && (
            <div
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
            >
              {detailError}
            </div>
          )}

          {detailLoading && !detail ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              در حال دریافت جزئیات...
            </p>
          ) : detail ? (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <Field label="نام فروشگاه" value={detail.storeName} />
                <Field label="اسلاگ" value={detail.slug} mono />
                <Field
                  label="نرخ کمیسیون"
                  value={
                    commissionPercentLabel(detail.commissionRate) === null ? null : (
                      <>
                        {toPersianDigits(commissionPercentLabel(detail.commissionRate) as string)}٪
                      </>
                    )
                  }
                />
                <Field
                  label="فعال"
                  value={detail.isActive === null ? null : detail.isActive ? "بله" : "خیر"}
                />
                <Field label="تلفن تماس" value={detail.contactPhone} mono />
                <Field label="کد ملی" value={detail.nationalId} mono />
                <Field label="شبا" value={detail.ibanNumber} mono />
                <Field label="تاریخ ثبت" value={formatJalali(detail.createdAt)} />
              </div>

              {/* Commission is editable here: the detail read is the only
                  endpoint that returns it, and a rate the operator cannot
                  change is a rate that drifts from the contract. */}
              <div className="space-y-2 rounded-md border border-border p-3">
                <h3 className="text-sm font-bold">ویرایش نرخ کمیسیون</h3>
                <p className="text-[11px] leading-5 text-muted-foreground">
                  نرخ به‌صورت درصد گرفته می‌شود و در سرور به واحد پایه (basis
                  point) تبدیل می‌گردد؛ ۱۰٪ معادل ۱۰۰۰ واحد پایه است. این مقدار
                  مستقیماً بر سهم پلتفرم از هر فروش اثر می‌گذارد.
                </p>
                <div className="flex flex-wrap items-end gap-2">
                  <div className="space-y-1.5">
                    <label
                      htmlFor="vendor-commission"
                      className="block text-[11px] font-medium text-muted-foreground"
                    >
                      نرخ جدید (درصد)
                    </label>
                    <Input
                      id="vendor-commission"
                      type="number"
                      step="0.01"
                      min="0"
                      max="100"
                      value={commissionInput}
                      onChange={(e) => setCommissionInput(e.target.value)}
                      dir="ltr"
                      className="w-32 font-mono"
                    />
                  </div>
                  <Button
                    size="sm"
                    disabled={savingCommission}
                    onClick={() => void saveCommission()}
                  >
                    {savingCommission ? "در حال ذخیره..." : "ذخیره نرخ کمیسیون"}
                  </Button>
                </div>
                {commissionError && (
                  <p role="alert" className="text-xs text-destructive">
                    {commissionError}
                  </p>
                )}
              </div>

              {/* ── Earnings ── */}
              <div className="space-y-2">
                <h3 className="flex items-center gap-1.5 text-sm font-bold">
                  <Wallet className="h-4 w-4 text-primary" />
                  درآمد و تسویه
                </h3>
                {earningsError ? (
                  <div
                    role="alert"
                    className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
                  >
                    {earningsError}
                  </div>
                ) : earningsLoading && !earnings ? (
                  <p className="text-sm text-muted-foreground">در حال محاسبه...</p>
                ) : earnings ? (
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    <Metric label="فروش کل" value={rialText(earnings.totalSales)} />
                    <Metric label="کمیسیون پلتفرم" value={rialText(earnings.commissionAmount)} />
                    <Metric label="درآمد خالص فروشنده" value={rialText(earnings.netEarnings)} />
                    <Metric label="تسویه‌شده" value={rialText(earnings.settledAmount)} />
                    <Metric
                      label="مانده تسویه‌نشده"
                      value={rialText(earnings.pendingSettlement)}
                    />
                    <Metric
                      label="تعداد سفارش"
                      value={
                        earnings.totalOrders === null
                          ? null
                          : toPersianDigits(String(earnings.totalOrders))
                      }
                    />
                  </div>
                ) : null}
              </div>

              {/* ── Settlements ── */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold">سابقه تسویه‌ها</h3>
                  <Button size="sm" onClick={() => setSettlementOpen(true)}>
                    ثبت تسویه جدید
                  </Button>
                </div>
                {settlementsError ? (
                  <div
                    role="alert"
                    className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
                  >
                    {settlementsError}
                  </div>
                ) : settlementsLoading && !settlements ? (
                  <p className="text-sm text-muted-foreground">در حال دریافت...</p>
                ) : !settlements || settlements.items.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    تسویه‌ای برای این فروشنده ثبت نشده است.
                  </p>
                ) : (
                  <div className="overflow-x-auto rounded-md border border-border">
                    <table className="w-full text-right text-xs">
                      <thead className="bg-muted/50 text-muted-foreground">
                        <tr>
                          <th scope="col" className="px-3 py-2">مبلغ</th>
                          <th scope="col" className="px-3 py-2">وضعیت</th>
                          <th scope="col" className="px-3 py-2">بازه</th>
                          <th scope="col" className="px-3 py-2">پیگیری بانکی</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {settlements.items.map((s) => (
                          <tr key={s.id}>
                            <td className="px-3 py-2 font-mono">
                              {rialText(s.amount)}
                            </td>
                            <td className="px-3 py-2">
                              <Badge variant={settlementStatusVariant(s.status)}>
                                {settlementStatusLabel(s.status)}
                              </Badge>
                            </td>
                            <td className="px-3 py-2 text-muted-foreground">
                              {formatJalali(s.periodStart)} ← {formatJalali(s.periodEnd)}
                            </td>
                            <td className="px-3 py-2 font-mono" dir="ltr">
                              {s.paymentReference ?? "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedId(null)}>
              بستن
            </Button>
            {detail && (
              <Button
                disabled={busyId === detail.id}
                onClick={() => void toggleVerification(detail)}
              >
                {detail.isVerified ? "لغو تأیید فروشنده" : "تأیید فروشنده"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Settlement creation ── */}
      <Dialog open={settlementOpen} onOpenChange={setSettlementOpen}>
        <DialogContent dir="rtl">
          <DialogHeader>
            <DialogTitle>ثبت تسویه جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-[11px] leading-5 text-amber-800 dark:text-amber-300">
              این فرم یک رکورد تسویه با وضعیت «در انتظار پرداخت» ثبت می‌کند و خود
              عملیات بانکی را انجام نمی‌دهد.
            </p>
            <div className="space-y-1.5">
              <label
                htmlFor="settlement-amount"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                مبلغ (ریال)
              </label>
              <Input
                id="settlement-amount"
                value={settlementAmount}
                onChange={(e) => setSettlementAmount(e.target.value)}
                placeholder="مثلاً 5000000"
                dir="ltr"
                className="font-mono"
              />
              {settlementAmount && Number.parseInt(settlementAmount, 10) >= 1 && (
                <p className="text-[11px] text-muted-foreground">
                  {formatRial(Number.parseInt(settlementAmount, 10))}
                </p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label
                  htmlFor="settlement-from"
                  className="block text-[11px] font-medium text-muted-foreground"
                >
                  از تاریخ
                </label>
                <Input
                  id="settlement-from"
                  type="date"
                  value={settlementPeriodStart}
                  onChange={(e) => setSettlementPeriodStart(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <label
                  htmlFor="settlement-to"
                  className="block text-[11px] font-medium text-muted-foreground"
                >
                  تا تاریخ
                </label>
                <Input
                  id="settlement-to"
                  type="date"
                  value={settlementPeriodEnd}
                  onChange={(e) => setSettlementPeriodEnd(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor="settlement-ref"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                کد پیگیری بانکی (اختیاری)
              </label>
              <Input
                id="settlement-ref"
                value={settlementReference}
                onChange={(e) => setSettlementReference(e.target.value)}
                dir="ltr"
                className="font-mono"
              />
            </div>
          </div>
          {formError && (
            <p role="alert" className="text-sm text-destructive">
              {formError}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSettlementOpen(false)}>
              انصراف
            </Button>
            <Button
              disabled={saving || !settlementAmount.trim()}
              onClick={() => void submitSettlement()}
            >
              {saving ? "در حال ثبت..." : "ثبت تسویه"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Renders an integer-rial amount, or an explicit "not reported" marker. */
function rialText(value: number | null): React.ReactNode {
  if (value === null) return <UnavailableValue reason="گزارش نشد." />;
  return <span className="font-mono">{formatRial(value)}</span>;
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  // A field the backend did not report is labelled as unavailable rather than
  // rendered blank — "unknown" and "empty" are different facts for an operator
  // deciding whether a payout account is on file.
  const content =
    value === null || value === undefined || value === "" ? (
      <UnavailableValue reason="توسط سرور گزارش نشد." />
    ) : (
      <span className={mono ? "font-mono" : undefined} dir={mono ? "ltr" : undefined}>
        {value}
      </span>
    );
  return (
    <div className="space-y-0.5">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="text-sm">{content}</div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Card className="p-3">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-bold">{value}</div>
    </Card>
  );
}
