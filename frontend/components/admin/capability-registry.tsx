"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Info, RefreshCw, Search, ShieldCheck, ShieldX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PartialDataNotice,
  UnavailableValue,
  type AsyncPhase,
} from "@/components/admin/async-state";
import { FilterSelect } from "@/components/admin/filter-select";
import {
  CAPABILITY_CATEGORIES,
  CAPABILITY_CATEGORY_LABELS,
  CAPABILITY_STATUSES,
  CAPABILITY_STATUS_LABELS,
  capabilityCategoryLabel,
  capabilityReasonLabel,
  fetchAdminCapabilities,
  type CapabilityCategory,
  type CapabilityStatus,
  type IntegrationCapability,
} from "@/lib/api/integrations";

/**
 * Integration capability registry (admin).
 *
 * Reads `GET /integrations/admin/capabilities` and renders exactly what the
 * registry reports. Two rules this view exists to enforce:
 *
 * 1. It never asserts runtime health. A status is displayed as the backend
 *    classified it, and the header says so, because "configuration present" and
 *    "provider is live" are different facts — the contract requires the registry
 *    to stay conservative and forbids claiming a provider is up from a
 *    locally entered key.
 * 2. Nothing here is authoritative for money. The registry is informational;
 *    no rendered value is read by any checkout, payment, or provider path.
 */

const ALL = "all";

type StatusFilter = CapabilityStatus | typeof ALL;
type CategoryFilter = CapabilityCategory | typeof ALL;

interface StatusFilterOption {
  value: StatusFilter;
  label: string;
}

const STATUS_OPTIONS: StatusFilterOption[] = [
  { value: ALL, label: "همه وضعیت‌ها" },
  ...CAPABILITY_STATUSES.map((status) => ({
    value: status as StatusFilter,
    label: CAPABILITY_STATUS_LABELS[status],
  })),
];

const CATEGORY_OPTIONS = [
  { value: ALL as CategoryFilter, label: "همه دسته‌بندی‌ها" },
  ...CAPABILITY_CATEGORIES.map((category) => ({
    value: category as CategoryFilter,
    label: CAPABILITY_CATEGORY_LABELS[category],
  })),
];

type BadgeVariant = "success" | "warning" | "destructive" | "secondary" | "info";

const STATUS_BADGE_VARIANTS: Record<CapabilityStatus, BadgeVariant> = {
  LIVE: "success",
  BETA: "info",
  MOCK: "secondary",
  DISABLED: "secondary",
  DEGRADED: "warning",
  MAINTENANCE: "warning",
};

export function filterCapabilities(
  capabilities: IntegrationCapability[],
  filters: {
    search?: string;
    status?: StatusFilter;
    category?: CategoryFilter;
    customerVisibleOnly?: boolean;
  },
): IntegrationCapability[] {
  const query = (filters.search ?? "").trim().toLowerCase();

  return capabilities.filter((capability) => {
    if (filters.status && filters.status !== ALL) {
      if (capability.status !== filters.status) return false;
    }
    if (filters.category && filters.category !== ALL) {
      if (capability.category !== filters.category) return false;
    }
    if (filters.customerVisibleOnly && !capability.customerVisible) {
      return false;
    }
    if (!query) return true;
    return (
      capability.id.toLowerCase().includes(query) ||
      capability.displayName.toLowerCase().includes(query)
    );
  });
}

export interface CapabilityRegistryProps {
  /** Injection seam for tests; defaults to the shared authenticated client. */
  loadCapabilities?: typeof fetchAdminCapabilities;
}

export function CapabilityRegistry({
  loadCapabilities,
}: CapabilityRegistryProps = {}) {
  const [capabilities, setCapabilities] = useState<IntegrationCapability[]>([]);
  const [invalidCount, setInvalidCount] = useState(0);
  const [phase, setPhase] = useState<AsyncPhase>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(ALL);
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>(ALL);

  const load = useCallback(async () => {
    setPhase("loading");
    setErrorMessage(null);

    try {
      const fetchCapabilities = loadCapabilities ?? fetchAdminCapabilities;
      const result = await fetchCapabilities();
      setCapabilities(result.items);
      setInvalidCount(result.invalidCount);
      setPhase("ready");
    } catch (error) {
      // A failed read is an error state, never an empty registry. Showing zero
      // capabilities would read as "this platform has no integrations".
      setCapabilities([]);
      setInvalidCount(0);
      setErrorMessage(
        error instanceof Error && error.message
          ? error.message
          : "ارتباط با سرویس فهرست قابلیت‌ها برقرار نشد. صحت اتصال و دسترسی خود را بررسی کنید.",
      );
      setPhase("error");
    }
  }, [loadCapabilities]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(
    () =>
      filterCapabilities(capabilities, {
        search,
        status: statusFilter,
        category: categoryFilter,
      }),
    [capabilities, search, statusFilter, categoryFilter],
  );

  const configuredCount = useMemo(
    () => capabilities.filter((capability) => capability.configured).length,
    [capabilities],
  );

  const isFiltered =
    search.trim().length > 0 || statusFilter !== ALL || categoryFilter !== ALL;

  const isLoading = phase === "loading";

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold text-foreground">
            فهرست قابلیت‌های یکپارچه‌سازی
          </h1>
          <p className="max-w-2xl text-xs leading-relaxed text-muted-foreground">
            وضعیت اعلام‌شده توسط رجیستری سمت سرور. این فهرست صرفاً اطلاع‌رسانی است
            و هیچ مقدار آن مبنای مجازسازی پرداخت، انتخاب درگاه یا تغییر موجودی
            نیست.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void load()}
          disabled={isLoading}
          className="shrink-0 gap-1.5 self-start text-xs"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          بروزرسانی فهرست
        </Button>
      </div>

      <div
        role="note"
        className="flex items-start gap-2.5 rounded-lg border border-blue-500/30 bg-blue-500/5 p-3 text-[11px] leading-relaxed text-blue-900 dark:text-blue-200"
      >
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>
          «پیکربندی‌شده» به‌معنای «سالم و فعال» نیست. وضعیت‌هایی مانند بتا، با
          اختلال یا شبیه‌ساز نشان می‌دهد که سلامت زمان اجرا تأیید نشده است و
          نباید به‌عنوان سرویس عملیاتی در نظر گرفته شود.
        </span>
      </div>

      <PartialDataNotice
        count={invalidCount}
        label="قابلیت‌های بازگشتی"
      />

      {phase === "error" ? (
        <ErrorState
          title="دریافت فهرست قابلیت‌ها ناموفق بود"
          message={
            errorMessage ??
            "ارتباط با سرویس فهرست قابلیت‌ها برقرار نشد. صحت اتصال و دسترسی خود را بررسی کنید."
          }
          onRetry={() => void load()}
          isRetrying={isLoading}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">کل قابلیت‌ها</p>
              {phase === "ready" ? (
                <p className="mt-1 font-mono text-xl font-bold text-foreground">
                  {capabilities.length.toLocaleString("fa-IR")}
                </p>
              ) : (
                <div className="mt-2">
                  <LoadingState label="در حال شمارش..." rows={0} />
                </div>
              )}
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">
                دارای پیکربندی محلی
              </p>
              {phase === "ready" ? (
                <p className="mt-1 font-mono text-xl font-bold text-foreground">
                  {configuredCount.toLocaleString("fa-IR")}
                </p>
              ) : (
                <div className="mt-2">
                  <LoadingState label="در حال شمارش..." rows={0} />
                </div>
              )}
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">قابل مشاهده مشتری</p>
              {phase === "ready" ? (
                <p className="mt-1 font-mono text-xl font-bold text-foreground">
                  {capabilities
                    .filter((capability) => capability.customerVisible)
                    .length.toLocaleString("fa-IR")}
                </p>
              ) : (
                <div className="mt-2">
                  <LoadingState label="در حال شمارش..." rows={0} />
                </div>
              )}
            </Card>
          </div>

          <Card className="space-y-3 p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <label
                  htmlFor="capability-search"
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
                    id="capability-search"
                    placeholder="شناسه یا نام قابلیت..."
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    className="pe-9 text-xs"
                  />
                </div>
              </div>

              <FilterSelect
                id="capability-status-filter"
                label="وضعیت"
                value={statusFilter}
                options={STATUS_OPTIONS}
                onChange={(value) => setStatusFilter(value as StatusFilter)}
              />

              <FilterSelect
                id="capability-category-filter"
                label="دسته‌بندی"
                value={categoryFilter}
                options={CATEGORY_OPTIONS}
                onChange={(value) => setCategoryFilter(value as CategoryFilter)}
              />
            </div>

            {phase === "ready" && isFiltered && (
              <p
                role="status"
                className="text-[11px] text-muted-foreground"
              >
                {filtered.length.toLocaleString("fa-IR")} مورد از{" "}
                {capabilities.length.toLocaleString("fa-IR")} قابلیت با
                فیلترهای انتخاب‌شده مطابقت دارد.
              </p>
            )}
          </Card>

          <Card className="overflow-hidden p-0">
            {phase === "loading" ? (
              <div className="p-4">
                <LoadingState label="در حال دریافت فهرست قابلیت‌ها..." rows={4} />
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                title={
                  capabilities.length === 0
                    ? "هیچ قابلیتی توسط رجیستری گزارش نشده است."
                    : "قابلیتی با فیلترهای انتخاب‌شده یافت نشد."
                }
                description={
                  capabilities.length === 0
                    ? "این وضعیت به‌معنای نبود خطا نیست؛ رجیستری در این لحظه هیچ قابلیتی اعلام نکرده است. در صورت انتظار برای وجود قابلیت، با تیم فنی بررسی کنید."
                    : "فیلترها را تغییر دهید یا جستجو را پاک کنید."
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-right text-xs">
                  <caption className="sr-only">
                    فهرست قابلیت‌های یکپارچه‌سازی و وضعیت اعلام‌شده آن‌ها
                  </caption>
                  <thead className="border-b border-border bg-muted/60 text-muted-foreground">
                    <tr>
                      <th scope="col" className="px-4 py-3">
                        شناسه
                      </th>
                      <th scope="col" className="px-4 py-3">
                        نام نمایشی
                      </th>
                      <th scope="col" className="px-4 py-3">
                        دسته‌بندی
                      </th>
                      <th scope="col" className="px-4 py-3">
                        وضعیت
                      </th>
                      <th scope="col" className="px-4 py-3">
                        پیکربندی
                      </th>
                      <th scope="col" className="px-4 py-3">
                        دسترسی مشتری
                      </th>
                      <th scope="col" className="px-4 py-3">
                        دلیل وضعیت
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filtered.map((capability) => (
                      <tr
                        key={capability.id}
                        className="transition-colors hover:bg-muted/30"
                      >
                        <td
                          className="px-4 py-3 font-mono font-bold text-foreground"
                          dir="ltr"
                        >
                          {capability.id}
                        </td>
                        <td className="px-4 py-3 font-medium text-foreground">
                          {capability.displayName}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {capabilityCategoryLabel(capability)}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={STATUS_BADGE_VARIANTS[capability.status]}
                            className="text-[11px]"
                          >
                            {CAPABILITY_STATUS_LABELS[capability.status]}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          {capability.configured ? (
                            <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
                              <ShieldCheck
                                className="h-3.5 w-3.5"
                                aria-hidden="true"
                              />
                              تنظیم شده
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-muted-foreground">
                              <ShieldX
                                className="h-3.5 w-3.5"
                                aria-hidden="true"
                              />
                              تنظیم نشده
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {capability.customerVisible ? (
                            <span className="text-foreground">
                              {capability.availableToCustomers
                                ? "در دسترس مشتری"
                                : "نمایش داده می‌شود (غیرقابل استفاده)"}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">
                              فقط اپراتور
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {capability.reasonCode
                            ? capabilityReasonLabel(capability)
                            : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {phase === "ready" && capabilities.length > 0 && (
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <span>زمان تولید رجیستری:</span>
              <RegistryUpdatedAt capabilities={capabilities} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function RegistryUpdatedAt({
  capabilities,
}: {
  capabilities: IntegrationCapability[];
}) {
  const stamp = useMemo(() => {
    const value = capabilities.find(
      (capability) => capability.updatedAt !== null,
    )?.updatedAt;
    if (!value) return null;
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
      ? null
      : parsed.toLocaleString("fa-IR");
  }, [capabilities]);

  if (!stamp) {
    return <UnavailableValue reason="زمان تولید رجیستری گزارش نشد." />;
  }

  return <span className="font-mono">{stamp}</span>;
}

export default CapabilityRegistry;
