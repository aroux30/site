"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  Check,
  Info,
  RefreshCw,
  ScanSearch,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PartialDataNotice,
  MissingDataNotice,
  UnavailableValue,
  type AsyncPhase,
} from "@/components/admin/async-state";
import { FilterSelect } from "@/components/admin/filter-select";
import {
  FindingActionDialog,
  type FindingAction,
} from "@/components/admin/finding-action-dialog";
import { useToast } from "@/components/ui/use-toast";
import {
  RECONCILIATION_SEVERITIES,
  RECONCILIATION_SEVERITY_LABELS,
  RECONCILIATION_STATUSES,
  RECONCILIATION_STATUS_LABELS,
  RECONCILIATION_TYPE_LABELS,
  dismissReconciliationFinding,
  fetchReconciliationFindings,
  fetchReconciliationSummary,
  filterFindings,
  formatRialAmount,
  requestLifecycleAudit,
  requestReconciliationScan,
  resolveReconciliationFinding,
  type ReconciliationFinding,
  type ReconciliationSeverity,
  type ReconciliationStatus,
  type ReconciliationSummary,
} from "@/lib/api/reconciliation";

/**
 * Durable reconciliation findings (admin).
 *
 * This view surfaces scanner output only. The scanner is read-only; a lifecycle
 * action here changes the finding's status and stores the operator's note, and
 * deliberately cannot touch the underlying payment, order, refund, or wallet
 * record. The copy says so, because an operator who believes "resolve" moves
 * money would make a different decision than one who knows it does not.
 *
 * Every count and amount is rendered as the backend reported it. A missing
 * number renders as "نامشخص" rather than zero — an unavailable count that reads
 * as zero looks like a clean reconciliation when it is actually an unknown one.
 */

const ALL = "all";

type SeverityFilter = ReconciliationSeverity | typeof ALL;
type StatusFilter = ReconciliationStatus | typeof ALL;
type TypeFilter = string;

const SEVERITY_OPTIONS = [
  { value: ALL as SeverityFilter, label: "همه سطوح شدت" },
  ...RECONCILIATION_SEVERITIES.map((severity) => ({
    value: severity as SeverityFilter,
    label: RECONCILIATION_SEVERITY_LABELS[severity],
  })),
];

const STATUS_OPTIONS = [
  { value: ALL as StatusFilter, label: "همه وضعیت‌ها" },
  ...RECONCILIATION_STATUSES.map((status) => ({
    value: status as StatusFilter,
    label: RECONCILIATION_STATUS_LABELS[status],
  })),
];

type BadgeVariant =
  "success" | "warning" | "destructive" | "secondary" | "info";

const SEVERITY_BADGE_VARIANTS: Record<ReconciliationSeverity, BadgeVariant> = {
  CRITICAL: "destructive",
  HIGH: "warning",
  MEDIUM: "info",
  LOW: "secondary",
};

const STATUS_BADGE_VARIANTS: Record<ReconciliationStatus, BadgeVariant> = {
  OPEN: "warning",
  INVESTIGATING: "info",
  RESOLVED: "success",
  DISMISSED: "secondary",
};

export interface ReconciliationFindingsProps {
  /**
   * False when the host page already renders the section title, so this view
   * does not repeat it. The informational notices always render: they carry the
   * "unavailable is not zero" and "this does not move money" statements, which
   * are load-bearing wherever the view appears.
   */
  showHeading?: boolean;
  /** Injection seams for tests; default to the shared authenticated client. */
  loadFindings?: typeof fetchReconciliationFindings;
  loadSummary?: typeof fetchReconciliationSummary;
  resolveFinding?: typeof resolveReconciliationFinding;
  dismissFinding?: typeof dismissReconciliationFinding;
  runScan?: typeof requestReconciliationScan;
  runLifecycleAudit?: typeof requestLifecycleAudit;
}

export function ReconciliationFindings({
  showHeading = true,
  loadFindings,
  loadSummary,
  resolveFinding,
  dismissFinding,
  runScan,
  runLifecycleAudit,
}: ReconciliationFindingsProps = {}) {
  const { toast } = useToast();

  const [findings, setFindings] = useState<ReconciliationFinding[]>([]);
  const [invalidCount, setInvalidCount] = useState(0);
  /** Findings the backend holds but this read did not load; null = unreported. */
  const [missingCount, setMissingCount] = useState(0);
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [summaryPhase, setSummaryPhase] = useState<AsyncPhase>("loading");
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [phase, setPhase] = useState<AsyncPhase>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>(ALL);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(ALL);
  const [typeFilter, setTypeFilter] = useState<TypeFilter>(ALL);

  const [scanning, setScanning] = useState(false);
  const [auditing, setAuditing] = useState(false);

  const [actionTarget, setActionTarget] =
    useState<ReconciliationFinding | null>(null);
  const [actionType, setActionType] = useState<FindingAction>("resolve");
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setPhase("loading");
    setErrorMessage(null);
    setSummaryPhase("loading");
    setSummaryError(null);

    // Findings and summary are independent reads: a summary outage must not
    // blank the table, and vice versa. Both settle before the phase resolves.
    const findingsRequest = (async () => {
      try {
        const fetchFindings = loadFindings ?? fetchReconciliationFindings;
        const result = await fetchFindings();
        setFindings(result.items);
        setInvalidCount(result.invalidCount);
        setMissingCount(result.missingCount ?? 0);
        setPhase("ready");
      } catch (error) {
        setFindings([]);
        setInvalidCount(0);
        setMissingCount(0);
        setErrorMessage(
          error instanceof Error && error.message
            ? error.message
            : "ارتباط با سرویس مغایرت‌های حسابرسی برقرار نشد. صحت اتصال و سطح دسترسی خود را بررسی کنید.",
        );
        setPhase("error");
      }
    })();

    const summaryRequest = (async () => {
      try {
        const fetchSummary = loadSummary ?? fetchReconciliationSummary;
        const result = await fetchSummary();
        setSummary(result);
        setSummaryPhase("ready");
      } catch (error) {
        setSummary(null);
        setSummaryError(
          error instanceof Error && error.message
            ? error.message
            : "خلاصه آماری مغایرت‌ها دریافت نشد.",
        );
        setSummaryPhase("error");
      }
    })();

    await Promise.all([findingsRequest, summaryRequest]);
  }, [loadFindings, loadSummary]);

  useEffect(() => {
    void load();
  }, [load]);

  const typeOptions = useMemo(() => {
    const present = Array.from(
      new Set(findings.map((finding) => finding.findingType)),
    ).sort();
    return [
      { value: ALL as TypeFilter, label: "همه انواع مغایرت" },
      ...present.map((type) => ({
        value: type,
        label: RECONCILIATION_TYPE_LABELS[type] ?? type,
      })),
    ];
  }, [findings]);

  const filtered = useMemo(
    () =>
      filterFindings(findings, {
        search,
        severity: severityFilter,
        status: statusFilter,
        type: typeFilter,
      }),
    [findings, search, severityFilter, statusFilter, typeFilter],
  );

  const isLoading = phase === "loading";
  const isBusy = isLoading || scanning || auditing;
  const isFiltered =
    search.trim().length > 0 ||
    severityFilter !== ALL ||
    statusFilter !== ALL ||
    typeFilter !== ALL;

  const handleRunScan = async () => {
    setScanning(true);
    try {
      const scan = runScan ?? requestReconciliationScan;
      const outcome = await scan();
      // An injected stub (or an older backend) may return nothing; that is
      // "not reported", never a claim of full coverage.
      toast({
        title: "اسکن خواندنی اجرا شد",
        description:
          outcome?.truncated === true
            ? "این اسکن هیچ پرداخت، سفارش یا بازپرداختی را تغییر نمی‌دهد و فقط یافته‌ها را بروزرسانی می‌کند. توجه: بازهٔ اسکن به سقف تعداد خورد و همهٔ سوابق بررسی نشدند."
            : "این اسکن هیچ پرداخت، سفارش یا بازپرداختی را تغییر نمی‌دهد و فقط یافته‌ها را بروزرسانی می‌کند.",
      });
      await load();
    } catch (error) {
      toast({
        variant: "destructive",
        title: "اجرای اسکن ناموفق بود",
        description:
          error instanceof Error && error.message
            ? error.message
            : "درخواست اجرای اسکن ثبت نشد. سطح دسترسی و اتصال را بررسی کنید.",
      });
    } finally {
      setScanning(false);
    }
  };

  /**
   * Runs the order lifecycle audit. Like the payment scan it is read-only:
   * it derives the payment/fulfilment/return axes and records findings, and
   * never moves money or changes an order, shipment or refund.
   */
  const handleRunLifecycleAudit = async () => {
    setAuditing(true);
    try {
      const audit = runLifecycleAudit ?? requestLifecycleAudit;
      const outcome = await audit();
      // An injected stub (or an older backend) may return nothing; that is
      // "not reported", never a claim of full coverage.
      toast({
        title: "ممیزی چرخهٔ سفارش اجرا شد",
        description:
          outcome?.truncated === true
            ? "این ممیزی فقط‌خواندنی است و هیچ سفارش، مرسوله یا بازپرداختی را تغییر نمی‌دهد. توجه: بازهٔ ممیزی به سقف تعداد خورد و همهٔ سفارش‌ها پوشش داده نشدند."
            : "این ممیزی فقط‌خواندنی است و هیچ سفارش، مرسوله یا بازپرداختی را تغییر نمی‌دهد.",
      });
      await load();
    } catch (error) {
      toast({
        variant: "destructive",
        title: "اجرای ممیزی چرخهٔ سفارش ناموفق بود",
        description:
          error instanceof Error && error.message
            ? error.message
            : "درخواست اجرای ممیزی ثبت نشد. سطح دسترسی و اتصال را بررسی کنید.",
      });
    } finally {
      setAuditing(false);
    }
  };

  const handleOpenAction = (
    finding: ReconciliationFinding,
    type: FindingAction,
  ) => {
    setActionTarget(finding);
    setActionType(type);
    setActionError(null);
  };

  const handleConfirmAction = async (notes: string) => {
    if (!actionTarget) return;

    setActionSubmitting(true);
    setActionError(null);

    try {
      if (actionType === "resolve") {
        const resolve = resolveFinding ?? resolveReconciliationFinding;
        await resolve(actionTarget.id, notes);
      } else {
        const dismiss = dismissFinding ?? dismissReconciliationFinding;
        await dismiss(actionTarget.id, notes);
      }

      // The write succeeded; the list is re-read rather than patched locally so
      // the rendered lifecycle state always comes from the backend.
      setActionTarget(null);
      toast({
        title:
          actionType === "resolve"
            ? "یافته حسابرسی حل شد"
            : "یافته حسابرسی نادیده گرفته شد",
        description:
          "وضعیت یافته ثبت شد. هیچ رکورد مالی در این عملیات تغییر نکرد.",
      });
      await load();
    } catch (error) {
      // A failed write stays in the dialog with the operator's note intact.
      // Applying it locally would show a resolved finding that the backend
      // still considers open.
      setActionError(
        error instanceof Error && error.message
          ? error.message
          : "ثبت اقدام ناموفق بود. یادداشت شما حفظ شده است؛ دوباره تلاش کنید.",
      );
    } finally {
      setActionSubmitting(false);
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        {showHeading && (
          <div className="space-y-1">
            <h2 className="text-2xl font-bold text-foreground">
              مغایرت‌های مالی پایدار (حسابرسی)
            </h2>
            <p className="max-w-2xl text-xs leading-relaxed text-muted-foreground">
              یافته‌های اسکنر خواندنی مغایرت‌های پرداخت، سفارش و وب‌هوک. حل یا
              نادیده‌گرفتن هر یافته فقط وضعیت همان یافته را ثبت میکند و هیچ
              اصلاح خودکار مالی انجام نمی‌شود.
            </p>
          </div>
        )}

        <div className="flex shrink-0 gap-2 self-start">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void load()}
            disabled={isBusy}
            className="gap-1.5 text-xs"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            بروزرسانی
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void handleRunScan()}
            disabled={isBusy}
            className="gap-1.5 text-xs"
          >
            <ScanSearch
              className={`h-3.5 w-3.5 ${scanning ? "animate-pulse" : ""}`}
              aria-hidden="true"
            />
            اجرای اسکن خواندنی
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void handleRunLifecycleAudit()}
            disabled={isBusy}
            className="gap-1.5 text-xs"
          >
            <ShieldCheck
              className={`h-3.5 w-3.5 ${auditing ? "animate-pulse" : ""}`}
              aria-hidden="true"
            />
            ممیزی چرخهٔ سفارش
          </Button>
        </div>
      </div>

      <div
        role="note"
        className="flex items-start gap-2.5 rounded-lg border border-blue-500/30 bg-blue-500/5 p-3 text-[11px] leading-relaxed text-blue-900 dark:text-blue-200"
      >
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>
          مبالغ به ریال و به‌صورت عدد صحیح نمایش داده می‌شوند. «نامشخص» به‌معنای
          صفر نیست؛ یعنی سرویس آن مقدار را گزارش نکرده است.
        </span>
      </div>

      <SummaryRow
        phase={summaryPhase}
        summary={summary}
        errorMessage={summaryError}
        onRetry={() => void load()}
        isRetrying={isLoading}
      />

      <PartialDataNotice count={invalidCount} label="یافته‌های بازگشتی" />
      <MissingDataNotice count={missingCount} label="یافته‌های مغایرت" />

      {phase === "error" ? (
        <ErrorState
          title="دریافت یافته‌های حسابرسی ناموفق بود"
          message={
            errorMessage ??
            "ارتباط با سرویس مغایرت‌های حسابرسی برقرار نشد. صحت اتصال و سطح دسترسی خود را بررسی کنید."
          }
          onRetry={() => void load()}
          isRetrying={isLoading}
        />
      ) : (
        <>
          <Card className="space-y-3 p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="finding-search"
                  className="block text-[11px] font-medium text-muted-foreground"
                >
                  جستجو
                </label>
                <div className="relative">
                  <Search
                    className="pointer-events-none absolute end-3 top-2.5 h-4 w-4 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <Input
                    id="finding-search"
                    placeholder="شناسه، نوع یا مورد وابسته..."
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    className="pe-9 text-xs"
                  />
                </div>
              </div>

              <FilterSelect
                id="finding-type-filter"
                label="نوع مغایرت"
                value={typeFilter}
                options={typeOptions}
                onChange={setTypeFilter}
              />

              <FilterSelect
                id="finding-severity-filter"
                label="شدت"
                value={severityFilter}
                options={SEVERITY_OPTIONS}
                onChange={(value) => setSeverityFilter(value as SeverityFilter)}
              />

              <FilterSelect
                id="finding-status-filter"
                label="وضعیت بررسی"
                value={statusFilter}
                options={STATUS_OPTIONS}
                onChange={(value) => setStatusFilter(value as StatusFilter)}
              />
            </div>

            {phase === "ready" && isFiltered && (
              <p role="status" className="text-[11px] text-muted-foreground">
                {filtered.length.toLocaleString("fa-IR")} مورد از{" "}
                {findings.length.toLocaleString("fa-IR")} یافته با فیلترهای
                انتخاب‌شده مطابقت دارد.
              </p>
            )}
          </Card>

          <Card className="overflow-hidden p-0">
            {phase === "loading" ? (
              <div className="p-4">
                <LoadingState
                  label="در حال دریافت یافتههای حسابرسی..."
                  rows={4}
                />
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                title={
                  findings.length === 0
                    ? "هیچ مغایرت مالی ثبت‌شده‌ای وجود ندارد."
                    : "یافته‌ای با فیلترهای انتخاب‌شده یافت نشد."
                }
                description={
                  findings.length === 0
                    ? "این فهرست از اسکنر سمت سرور تغذیه می‌شود. خالی بودن آن یعنی آخرین اسکن یافته‌ای ثبت نکرده است؛ برای اطمینان می‌توانید اسکن خواندنی را اجرا کنید."
                    : "فیلترها را تغییر دهید یا جستجو را پاک کنید."
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs">
                  <caption className="sr-only">
                    یافتههای مغایرت مالی و وضعیت بررسی آن‌ها
                  </caption>
                  <thead className="border-b border-border bg-muted/60 text-muted-foreground">
                    <tr>
                      <th scope="col" className="px-4 py-3">
                        نوع مغایرت
                      </th>
                      <th scope="col" className="px-4 py-3">
                        شدت
                      </th>
                      <th scope="col" className="px-4 py-3">
                        مورد وابسته
                      </th>
                      <th scope="col" className="px-4 py-3">
                        مبلغ مورد انتظار
                      </th>
                      <th scope="col" className="px-4 py-3">
                        مبلغ واقعی
                      </th>
                      <th scope="col" className="px-4 py-3">
                        تکرار
                      </th>
                      <th scope="col" className="px-4 py-3">
                        وضعیت
                      </th>
                      <th scope="col" className="px-4 py-3 text-center">
                        اقدامات
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filtered.map((finding) => (
                      <FindingRow
                        key={finding.id}
                        finding={finding}
                        onAction={handleOpenAction}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      <FindingActionDialog
        finding={actionTarget}
        action={actionType}
        isSubmitting={actionSubmitting}
        submitError={actionError}
        onCancel={() => {
          if (actionSubmitting) return;
          setActionTarget(null);
          setActionError(null);
        }}
        onConfirm={(notes) => void handleConfirmAction(notes)}
      />
    </div>
  );
}

function FindingRow({
  finding,
  onAction,
}: {
  finding: ReconciliationFinding;
  onAction: (finding: ReconciliationFinding, action: FindingAction) => void;
}) {
  const isOpen =
    finding.status === "OPEN" || finding.status === "INVESTIGATING";
  const expected = formatRialAmount(finding.expectedAmountIrr);
  const actual = formatRialAmount(finding.actualAmountIrr);

  return (
    <tr className="transition-colors hover:bg-muted/30">
      <td className="px-4 py-3">
        <p className="font-bold text-foreground">{finding.findingTypeLabel}</p>
        <p className="font-mono text-[10px] text-muted-foreground" dir="ltr">
          {finding.id}
        </p>
      </td>
      <td className="px-4 py-3">
        <Badge
          variant={SEVERITY_BADGE_VARIANTS[finding.severity]}
          className="text-[11px]"
        >
          {RECONCILIATION_SEVERITY_LABELS[finding.severity]}
        </Badge>
      </td>
      <td className="px-4 py-3">
        <p className="text-muted-foreground">{finding.entityTypeLabel}</p>
        {finding.entityId && (
          <p className="font-mono text-[10px] text-foreground" dir="ltr">
            {finding.entityId}
          </p>
        )}
      </td>
      <td className="px-4 py-3 font-medium text-foreground">
        {expected !== null ? (
          <span dir="ltr" className="font-mono">
            {expected}
          </span>
        ) : (
          <UnavailableValue reason="مبلغ مورد انتظار گزارش نشد." />
        )}
      </td>
      <td className="px-4 py-3 font-medium text-amber-700 dark:text-amber-400">
        {actual !== null ? (
          <span dir="ltr" className="font-mono">
            {actual}
          </span>
        ) : (
          <UnavailableValue reason="مبلغ واقعی گزارش نشد." />
        )}
      </td>
      <td className="px-4 py-3 text-muted-foreground">
        {finding.occurrenceCount !== null ? (
          `${finding.occurrenceCount.toLocaleString("fa-IR")} بار`
        ) : (
          <UnavailableValue reason="تعداد تکرار گزارش نشد." />
        )}
      </td>
      <td className="px-4 py-3">
        <Badge
          variant={STATUS_BADGE_VARIANTS[finding.status]}
          className="text-[11px]"
        >
          {RECONCILIATION_STATUS_LABELS[finding.status]}
        </Badge>
        {finding.resolutionNotes && (
          <p className="mt-1 max-w-[16rem] truncate text-[10px] text-muted-foreground">
            {finding.resolutionNotes}
          </p>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-center gap-1.5">
          {isOpen ? (
            <>
              <Button
                type="button"
                size="sm"
                variant="default"
                className="h-7 gap-1 bg-emerald-600 text-[11px] font-bold hover:bg-emerald-700"
                onClick={() => onAction(finding, "resolve")}
                aria-label={`حل یافته ${finding.findingTypeLabel}`}
              >
                <Check className="h-3 w-3" aria-hidden="true" />
                حل
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7 gap-1 text-[11px]"
                onClick={() => onAction(finding, "dismiss")}
                aria-label={`نادیده‌گرفتن یافته ${finding.findingTypeLabel}`}
              >
                <XCircle className="h-3 w-3" aria-hidden="true" />
                نادیده‌گیری
              </Button>
            </>
          ) : (
            <span className="text-[11px] text-muted-foreground">
              بررسی بسته شده
            </span>
          )}
        </div>
      </td>
    </tr>
  );
}

/**
 * Counts are not money, but they follow the same rule: a partial backend report
 * yields "unavailable" rather than a total that silently assumes zero for the
 * half it did not send.
 */
function closedFindingCount(
  summary: ReconciliationSummary | null,
): number | null {
  if (!summary) return null;
  if (summary.resolved === null && summary.dismissed === null) return null;
  if (summary.resolved === null || summary.dismissed === null) return null;
  return summary.resolved + summary.dismissed;
}

function SummaryRow({
  phase,
  summary,
  errorMessage,
  onRetry,
  isRetrying,
}: {
  phase: AsyncPhase;
  summary: ReconciliationSummary | null;
  errorMessage: string | null;
  onRetry: () => void;
  isRetrying: boolean;
}) {
  if (phase === "error") {
    return (
      <ErrorState
        title="خلاصه آماری دریافت نشد"
        message={
          errorMessage ??
          "خلاصه آماری مغایرت‌ها دریافت نشد. فهرست یافته‌ها در ادامه نمایش داده می‌شود."
        }
        onRetry={onRetry}
        isRetrying={isRetrying}
      />
    );
  }

  const cells: Array<{
    key: string;
    label: string;
    value: number | null;
    icon: React.ReactNode;
    tone: string;
  }> = [
    {
      key: "total",
      label: "کل یافته‌ها",
      value: summary?.total ?? null,
      icon: <AlertTriangle className="h-4 w-4" aria-hidden="true" />,
      tone: "text-foreground",
    },
    {
      key: "open",
      label: "در انتظار بررسی",
      value: summary?.open ?? null,
      icon: <AlertOctagon className="h-4 w-4" aria-hidden="true" />,
      tone: "text-amber-600",
    },
    {
      key: "investigating",
      label: "در حال بررسی",
      value: summary?.investigating ?? null,
      icon: <Search className="h-4 w-4" aria-hidden="true" />,
      tone: "text-blue-600",
    },
    {
      key: "resolved",
      label: "حل‌شده / نادیده‌گرفته‌شده",
      value: closedFindingCount(summary),
      icon: <Check className="h-4 w-4" aria-hidden="true" />,
      tone: "text-emerald-600",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {cells.map((cell) => (
        <Card key={cell.key} className="flex items-center justify-between p-4">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">{cell.label}</p>
            {phase === "loading" ? (
              <LoadingState label="در حال دریافت..." rows={0} />
            ) : cell.value === null ? (
              <UnavailableValue reason="این شمارش توسط سرویس گزارش نشد." />
            ) : (
              <p className={`font-mono text-xl font-bold ${cell.tone}`}>
                {cell.value.toLocaleString("fa-IR")}
              </p>
            )}
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
            {cell.icon}
          </div>
        </Card>
      ))}
    </div>
  );
}

export default ReconciliationFindings;
