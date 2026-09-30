"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  Check,
  CheckCircle2,
  CreditCard,
  DollarSign,
  FileText,
  Boxes,
  RefreshCw,
  Search,
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
  UnavailableValue,
  type AsyncPhase,
} from "@/components/admin/async-state";
import { FilterSelect } from "@/components/admin/filter-select";
import { ReconciliationFindings } from "@/components/admin/reconciliation-findings";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";
import { toPersianDigits } from "@/lib/utils";
import { ServiceHealthBanner } from "@/components/admin/service-health-banner";
import {
  EXCEPTION_SEVERITY_LABELS,
  EXCEPTION_STATUS_LABELS,
  EXCEPTION_TYPE_LABELS,
  filterExceptions,
  normalizeOperationalException,
  readOptionalString,
  validateResolution,
  type ExceptionSeverity,
  type ExceptionStatus,
  type ProviderHealthStatus,
  type SystemException,
  type SystemExceptionType,
} from "@/lib/ops-exceptions";

/**
 * Operational exception center.
 *
 * Reads only `GET /audit/admin/exceptions`. The previous revision of this screen
 * filled the table with hard-coded sample findings whenever the backend returned
 * nothing or failed — fake critical price and payment mismatches presented as
 * live operational data, and an offline fallback that "resolved" records the
 * server never saw. Both are gone. An unavailable service now renders as an
 * error, and an empty registry renders as empty; neither is invented.
 *
 * Amount comparison is not shown here because this endpoint does not report
 * amounts. It belongs to the durable reconciliation findings view, which reads
 * the scanner's integer-rial values.
 */

const ALL = "all";

type BadgeVariant = "success" | "warning" | "destructive" | "secondary" | "info";

const SEVERITY_BADGE_VARIANTS: Record<ExceptionSeverity, BadgeVariant> = {
  CRITICAL: "destructive",
  HIGH: "destructive",
  MEDIUM: "warning",
  LOW: "secondary",
  WARNING: "warning",
  INFO: "info",
};

const STATUS_BADGE_VARIANTS: Record<ExceptionStatus, BadgeVariant> = {
  OPEN: "warning",
  INVESTIGATING: "info",
  RESOLVED: "success",
  IGNORED: "secondary",
};

const TYPE_OPTIONS = [
  { value: ALL, label: "همه انواع مغایرت" },
  ...(
    Object.keys(EXCEPTION_TYPE_LABELS) as SystemExceptionType[]
  ).map((type) => ({ value: type, label: EXCEPTION_TYPE_LABELS[type] })),
];

const SEVERITY_OPTIONS = [
  { value: ALL, label: "همه سطوح شدت" },
  { value: "CRITICAL", label: EXCEPTION_SEVERITY_LABELS.CRITICAL },
  { value: "HIGH", label: EXCEPTION_SEVERITY_LABELS.HIGH },
  { value: "MEDIUM", label: EXCEPTION_SEVERITY_LABELS.MEDIUM },
  { value: "LOW", label: EXCEPTION_SEVERITY_LABELS.LOW },
];

const STATUS_OPTIONS = [
  { value: ALL, label: "همه وضعیت‌ها" },
  { value: "OPEN", label: EXCEPTION_STATUS_LABELS.OPEN },
  { value: "INVESTIGATING", label: EXCEPTION_STATUS_LABELS.INVESTIGATING },
  { value: "RESOLVED", label: EXCEPTION_STATUS_LABELS.RESOLVED },
  { value: "IGNORED", label: EXCEPTION_STATUS_LABELS.IGNORED },
];

const EXCEPTIONS_PATH = "/audit/admin/exceptions";

export default function AdminExceptionsPage() {
  return (
    <div className="space-y-6" dir="rtl">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold text-foreground">
          مرکز عملیات و حسابرسی مالی
        </h1>
        <p className="max-w-2xl text-xs leading-relaxed text-muted-foreground">
          خطاهای عملیاتی ثبت‌شده و یافته‌های اسکنر خواندنی مغایرتهای مالی. هیچ‌کدام
          از این دو نما مجوز یا مبنای تغییر خودکار پرداخت، سفارش یا موجودی نیست.
        </p>
      </div>

      <Tabs defaultValue="exceptions" className="space-y-4" dir="rtl">
        <TabsList>
          <TabsTrigger value="exceptions">خطاهای عملیاتی</TabsTrigger>
          <TabsTrigger value="reconciliation">مغایرت‌های مالی پایدار</TabsTrigger>
        </TabsList>
        <TabsContent value="exceptions">
          <ExceptionsPanel />
        </TabsContent>
        <TabsContent value="reconciliation">
          <ReconciliationFindings showHeading={false} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ExceptionsPanel() {
  const { toast } = useToast();

  const [exceptions, setExceptions] = useState<SystemException[]>([]);
  const [phase, setPhase] = useState<AsyncPhase>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [providers, setProviders] = useState<ProviderHealthStatus[]>([]);

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState(ALL);
  const [severityFilter, setSeverityFilter] = useState(ALL);
  const [statusFilter, setStatusFilter] = useState(ALL);

  const [actionTarget, setActionTarget] = useState<SystemException | null>(null);
  const [actionType, setActionType] = useState<"resolve" | "ignore">("resolve");
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchExceptions = useCallback(async () => {
    setPhase("loading");
    setErrorMessage(null);

    try {
      const res = await apiClient.get<unknown>(EXCEPTIONS_PATH);
      const payload = res.data;
      const raw = Array.isArray(payload)
        ? payload
        : payload &&
            typeof payload === "object" &&
            Array.isArray((payload as Record<string, unknown>).items)
          ? ((payload as Record<string, unknown>).items as unknown[])
          : [];

      const list: SystemException[] = [];
      for (const item of raw) {
        const normalized = normalizeOperationalException(item);
        if (normalized) list.push(normalized);
      }

      setExceptions(list);
      setPhase("ready");
    } catch (error) {
      // No offline fallback: showing invented findings here previously meant an
      // operator could act on records the backend never produced.
      setExceptions([]);
      setErrorMessage(
        error instanceof Error && error.message
          ? error.message
          : "ارتباط با سرویس مرکز خطاهای عملیاتی برقرار نشد. صحت اتصال و سطح دسترسی خود را بررسی کنید.",
      );
      setPhase("error");
    }
  }, []);

  const fetchProviderHealth = useCallback(async () => {
    try {
      // GET /settings/admin/sms-providers returns configured SMS providers.
      // `is_active` is a configuration flag, not a runtime health result, so
      // health stays unverified until a health signal supplies it.
      const res = await apiClient.get<unknown>("/settings/admin/sms-providers");
      const raw = Array.isArray(res.data)
        ? res.data
        : res.data &&
            typeof res.data === "object" &&
            Array.isArray((res.data as Record<string, unknown>).providers)
          ? ((res.data as Record<string, unknown>).providers as unknown[])
          : [];

      const mapped: ProviderHealthStatus[] = [];
      for (const entry of raw) {
        if (!entry || typeof entry !== "object") continue;
        const record = entry as Record<string, unknown>;
        const name =
          readOptionalString(record.name) ?? readOptionalString(record.id);
        if (!name) continue;

        // The row exists because an operator configured this provider, so
        // configuration is present. `is_active` is a settings flag and is not a
        // runtime health result, so no status is asserted here at all.
        mapped.push({
          service: "sms",
          provider: name,
          isConfigured: true,
          healthVerified: false,
        });
      }

      setProviders(mapped);
    } catch {
      // A settings read failure must not be reported as a provider outage. The
      // banner simply receives no providers and states that nothing was checked.
      setProviders([]);
    }
  }, []);

  useEffect(() => {
    void fetchExceptions();
    void fetchProviderHealth();
  }, [fetchExceptions, fetchProviderHealth]);

  const filtered = useMemo(
    () =>
      filterExceptions(exceptions, {
        search,
        type: typeFilter,
        severity: severityFilter,
        status: statusFilter,
      }),
    [exceptions, search, typeFilter, severityFilter, statusFilter],
  );

  const metrics = useMemo(
    () => ({
      total: exceptions.length,
      critical: exceptions.filter(
        (exception) =>
          exception.severity === "CRITICAL" && exception.status === "OPEN",
      ).length,
      open: exceptions.filter((exception) => exception.status === "OPEN").length,
      resolved: exceptions.filter(
        (exception) => exception.status === "RESOLVED",
      ).length,
    }),
    [exceptions],
  );

  const isLoading = phase === "loading";
  const isFiltered =
    search.trim().length > 0 ||
    typeFilter !== ALL ||
    severityFilter !== ALL ||
    statusFilter !== ALL;

  const handleOpenAction = (
    exception: SystemException,
    type: "resolve" | "ignore",
  ) => {
    setActionTarget(exception);
    setActionType(type);
    setResolutionNotes("");
    setActionError(null);
  };

  const handleConfirmAction = async () => {
    if (!actionTarget) return;

    const validation = validateResolution({
      action: actionType,
      notes: resolutionNotes,
    });

    if (!validation.isValid) {
      setActionError(validation.error);
      return;
    }

    setActionSubmitting(true);
    setActionError(null);

    try {
      const action = actionType === "resolve" ? "resolve" : "dismiss";
      await apiClient.patch(
        `${EXCEPTIONS_PATH}/${actionTarget.id}/${action}`,
        { resolution_notes: resolutionNotes.trim() },
      );

      setActionTarget(null);
      toast({
        title:
          actionType === "resolve" ? "مغایرت برطرف شد" : "مغایرت نادیده گرفته شد",
        description: "وضعیت رکورد از سرور بازخوانی می‌شود.",
      });
      await fetchExceptions();
    } catch (error) {
      // The write did not land, so the row must not be shown as handled.
      setActionError(
        error instanceof Error && error.message
          ? error.message
          : "ثبت اقدام ناموفق بود. یادداشت شما حفظ شده است؛ دوباره تلاش کنید.",
      );
    } finally {
      setActionSubmitting(false);
    }
  };

  const getTypeIcon = (type: SystemExceptionType) => {
    switch (type) {
      case "PRICE_MISMATCH":
        return <DollarSign className="h-4 w-4 text-amber-500" aria-hidden="true" />;
      case "PAYMENT_MISMATCH":
      case "PAYMENT_TIMEOUT":
        return <CreditCard className="h-4 w-4 text-red-500" aria-hidden="true" />;
      case "INVENTORY_CONFLICT":
        return <Boxes className="h-4 w-4 text-blue-500" aria-hidden="true" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-muted-foreground" aria-hidden="true" />;
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h2 className="text-lg font-bold text-foreground">
            خطاهای عملیاتی ثبت‌شده
          </h2>
          <p className="max-w-2xl text-xs leading-relaxed text-muted-foreground">
            خطاهای عملیاتی ثبتشده در سرویس حسابرسی. مغایرت‌های مالی مبلغ‌محور در
            زبانه مغایرتهای پایدار بررسی می‌شوند.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void fetchExceptions()}
          disabled={isLoading}
          className="shrink-0 gap-1.5 self-start text-xs"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          بروزرسانی
        </Button>
      </div>

      <ServiceHealthBanner
        providers={providers}
        onRefresh={() => void fetchProviderHealth()}
        isLoading={isLoading}
      />

      {phase === "error" ? (
        <ErrorState
          title="دریافت خطاهای عملیاتی ناموفق بود"
          message={
            errorMessage ??
            "ارتباط با سرویس مرکز خطاهای عملیاتی برقرار نشد. صحت اتصال و سطح دسترسی خود را بررسی کنید."
          }
          onRetry={() => void fetchExceptions()}
          isRetrying={isLoading}
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <MetricCard
              label="کل خطاها"
              value={phase === "ready" ? metrics.total : null}
              tone="text-foreground"
              icon={<FileText className="h-5 w-5" aria-hidden="true" />}
            />
            <MetricCard
              label="بحرانی باز"
              value={phase === "ready" ? metrics.critical : null}
              tone="text-red-600"
              icon={<AlertOctagon className="h-5 w-5" aria-hidden="true" />}
            />
            <MetricCard
              label="در انتظار بررسی"
              value={phase === "ready" ? metrics.open : null}
              tone="text-amber-600"
              icon={<AlertTriangle className="h-5 w-5" aria-hidden="true" />}
            />
            <MetricCard
              label="حل‌شده"
              value={phase === "ready" ? metrics.resolved : null}
              tone="text-emerald-600"
              icon={<CheckCircle2 className="h-5 w-5" aria-hidden="true" />}
            />
          </div>


          <Card className="space-y-3 p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="exception-search"
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
                    id="exception-search"
                    placeholder="شناسه، عنوان یا متن خطا..."
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    className="pe-9 text-xs"
                  />
                </div>
              </div>

              <FilterSelect
                id="exception-type-filter"
                label="نوع خطا"
                value={typeFilter}
                options={TYPE_OPTIONS}
                onChange={setTypeFilter}
              />
              <FilterSelect
                id="exception-severity-filter"
                label="شدت"
                value={severityFilter}
                options={SEVERITY_OPTIONS}
                onChange={setSeverityFilter}
              />
              <FilterSelect
                id="exception-status-filter"
                label="وضعیت بررسی"
                value={statusFilter}
                options={STATUS_OPTIONS}
                onChange={setStatusFilter}
              />
            </div>

            {phase === "ready" && isFiltered && (
              <p role="status" className="text-[11px] text-muted-foreground">
                {filtered.length.toLocaleString("fa-IR")} مورد از{" "}
                {exceptions.length.toLocaleString("fa-IR")} خطا با فیلترهای
                انتخاب‌شده مطابقت دارد.
              </p>
            )}
          </Card>

          <Card className="overflow-hidden p-0">
            {phase === "loading" ? (
              <div className="p-4">
                <LoadingState label="در حال دریافت خطاهای عملیاتی..." rows={4} />
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                title={
                  exceptions.length === 0
                    ? "هیچ خطای عملیاتی ثبت نشده است."
                    : "خطایی با فیلترهای انتخاب‌شده یافت نشد."
                }
                description={
                  exceptions.length === 0
                    ? "این سرویس در این لحظه هیچ خطای عملیاتی ثبت‌شدهای گزارش نکرده است."
                    : "فیلترها را تغییر دهید یا جستجو را پاک کنید."
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs">
                  <caption className="sr-only">
                    خطاهای عملیاتی ثبت‌شده و وضعیت بررسی آن‌ها
                  </caption>
                  <thead className="border-b border-border bg-muted/60 text-muted-foreground">
                    <tr>
                      <th scope="col" className="px-4 py-3">
                        شناسه
                      </th>
                      <th scope="col" className="px-4 py-3">
                        نوع خطا
                      </th>
                      <th scope="col" className="px-4 py-3">
                        شدت
                      </th>
                      <th scope="col" className="px-4 py-3">
                        شرح
                      </th>
                      <th scope="col" className="px-4 py-3">
                        مورد وابسته
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
                    {filtered.map((exception) => {
                      const isOpen =
                        exception.status === "OPEN" ||
                        exception.status === "INVESTIGATING";

                      return (
                        <tr
                          key={exception.id}
                          className="transition-colors hover:bg-muted/30"
                        >
                          <td
                            className="px-4 py-3 font-mono font-bold text-foreground"
                            dir="ltr"
                          >
                            {exception.id}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1.5 font-medium">
                              {getTypeIcon(exception.type)}
                              <span>{EXCEPTION_TYPE_LABELS[exception.type]}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <Badge
                              variant={SEVERITY_BADGE_VARIANTS[exception.severity]}
                              className="text-[11px]"
                            >
                              {EXCEPTION_SEVERITY_LABELS[exception.severity]}
                            </Badge>
                          </td>
                          <td className="max-w-xs px-4 py-3">
                            <p className="truncate font-bold text-foreground">
                              {exception.title}
                            </p>
                            {exception.message && (
                              <p className="truncate text-[11px] text-muted-foreground">
                                {exception.message}
                              </p>
                            )}
                          </td>
                          <td
                            className="px-4 py-3 font-mono text-muted-foreground"
                            dir="ltr"
                          >
                            {exception.entityId || "-"}
                          </td>
                          <td className="px-4 py-3">
                            <Badge
                              variant={STATUS_BADGE_VARIANTS[exception.status]}
                              className="text-[11px]"
                            >
                              {EXCEPTION_STATUS_LABELS[exception.status]}
                            </Badge>
                            {exception.notes && (
                              <p className="mt-1 max-w-[16rem] truncate text-[10px] text-muted-foreground">
                                {exception.notes}
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
                                    onClick={() =>
                                      handleOpenAction(exception, "resolve")
                                    }
                                    aria-label={`حل خطای ${EXCEPTION_TYPE_LABELS[exception.type]}`}
                                  >
                                    <Check className="h-3 w-3" aria-hidden="true" />
                                    حل
                                  </Button>
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    className="h-7 gap-1 text-[11px]"
                                    onClick={() =>
                                      handleOpenAction(exception, "ignore")
                                    }
                                    aria-label={`نادیده‌گرفتن خطای ${EXCEPTION_TYPE_LABELS[exception.type]}`}
                                  >
                                    <XCircle
                                      className="h-3 w-3 text-muted-foreground"
                                      aria-hidden="true"
                                    />
                                    نادیدهگیری
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
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      <Dialog
        open={Boolean(actionTarget)}
        onOpenChange={(open) => {
          if (!open && !actionSubmitting) {
            setActionTarget(null);
            setActionError(null);
          }
        }}
      >
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              {actionType === "resolve" ? (
                <>
                  <CheckCircle2
                    className="h-5 w-5 text-emerald-600"
                    aria-hidden="true"
                  />
                  حل خطای عملیاتی ({actionTarget?.id})
                </>
              ) : (
                <>
                  <XCircle
                    className="h-5 w-5 text-amber-600"
                    aria-hidden="true"
                  />
                  نادیده‌گرفتن خطای عملیاتی ({actionTarget?.id})
                </>
              )}
            </DialogTitle>
            <DialogDescription className="text-xs leading-relaxed">
              در هر دو حالت یادداشت اپراتور الزامی است. این اقدام هیچ رکورد مالی
              را تغییر نمی‌دهد و فقط وضعیت بررسی همین خطا را ثبت می‌کند.
            </DialogDescription>
          </DialogHeader>

          {actionTarget && (
            <div className="space-y-4 py-2 text-xs">
              <div className="space-y-1 rounded-lg border border-border bg-muted/40 p-3">
                <p className="font-bold text-foreground">{actionTarget.title}</p>
                {actionTarget.message ? (
                  <p className="text-muted-foreground">{actionTarget.message}</p>
                ) : (
                  <UnavailableValue reason="شرح تکمیلی از سرویس دریافت نشد." />
                )}
                {actionTarget.entityId && (
                  <p
                    className="pt-1 font-mono text-[11px] text-primary"
                    dir="ltr"
                  >
                    شناسه: {actionTarget.entityId}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="exception-action-notes" className="text-xs">
                  یادداشت اپراتور (الزامی — حداقل ۵ کاراکتر)
                </Label>
                <Textarea
                  id="exception-action-notes"
                  value={resolutionNotes}
                  onChange={(event) => {
                    setResolutionNotes(event.target.value);
                    setActionError(null);
                  }}
                  rows={4}
                  className="text-xs"
                  aria-required="true"
                  aria-invalid={actionError ? true : undefined}
                  aria-describedby={
                    actionError ? "exception-action-error" : undefined
                  }
                  placeholder={
                    actionType === "resolve"
                      ? "مثلاً: با هماهنگی واحد مالی بررسی و از مسیر رسمی اصلاح شد..."
                      : "مثلاً: ناشی از تأخیر شناخته‌شده بود و نیاز به اقدام مالی ندارد..."
                  }
                />
                {actionError && (
                  <p
                    id="exception-action-error"
                    role="alert"
                    className="text-[11px] font-medium text-red-600"
                  >
                    {actionError}
                  </p>
                )}
              </div>
            </div>
          )}

          <DialogFooter className="flex flex-row items-center justify-between gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setActionTarget(null)}
              disabled={actionSubmitting}
              className="text-xs"
            >
              انصراف
            </Button>
            <Button
              type="button"
              size="sm"
              variant={actionType === "resolve" ? "default" : "secondary"}
              onClick={() => void handleConfirmAction()}
              disabled={actionSubmitting}
              className="text-xs font-bold"
            >
              {actionSubmitting
                ? "در حال ثبت..."
                : actionType === "resolve"
                  ? "تأیید و حل خطا"
                  : "تأیید نادیده‌گیری"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function MetricCard({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: number | null;
  tone: string;
  icon: React.ReactNode;
}) {
  return (
    <Card className="flex items-center justify-between p-4">
      <div className="space-y-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        {value === null ? (
          <UnavailableValue reason="این شمارش از سرویس دریافت نشد." />
        ) : (
          <p className={`font-mono text-xl font-bold ${tone}`}>
            {toPersianDigits(value)}
          </p>
        )}
      </div>
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        {icon}
      </div>
    </Card>
  );
}