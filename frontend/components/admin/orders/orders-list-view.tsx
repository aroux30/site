"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckSquare, Eye, Loader2, Search, ShoppingCart, Square, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useConfirm } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/use-toast";
import { cn, formatPrice, toPersianDigits } from "@/lib/utils";
import {
  ORDER_STATUSES,
  STATUS_VISUALS,
  isOrderStale,
  rialsToToman,
  type OrderStatus,
} from "@/lib/admin/order-domain";

/**
 * All seven statuses shown as filter buttons — no dropdown, no grouping.
 * Each button filters by its single status.
 */
import { adminOrdersApi, type AdminOrderPage, type AdminOrderRow } from "@/lib/api/admin-orders";
import { adminBulkApi } from "@/lib/api/bulk-operations";
import { apiErrorMessage } from "@/lib/api/error-message";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";

/**
 * The bulk statuses offered here are the states a bulk run can actually move
 * an order INTO — one legal step forward, plus the two exits. Offering a
 * status no order can legally reach (the old list offered `confirmed`,
 * `shipped`, `delivered`, which the seven-status machine does not have) only
 * produces per-order rejections. Cancellation carries real side effects
 * (restock + wallet refund per order, through the single-order service), so
 * its confirm dialog spells that out — and because the backend reports
 * per-order outcomes, a partial run is shown as partial with reasons.
 *
 * `refunded` is deliberately NOT here: a refund is a money operation driven
 * through `/payments/{id}/refund`, not a status an operator stamps onto rows.
 */
const BULK_STATUS_OPTIONS: OrderStatus[] = ["pending", "processing", "completed", "canceled"];

/**
 * The list (table) view of the unified orders page.
 *
 * Differences from the old table, on purpose:
 *  - The status filter covers ALL seven statuses (the old select offered
 *    six, so a returned/partially-refunded order was unfilterable).
 *  - The status cell is a read-only badge, not an inline Select: an inline
 *    select cannot know the state machine, so the old one offered every
 *    status from every status and the server rejected most choices after
 *    the click. Transitions now happen in the drawer, which only offers
 *    legal moves (and on the board, where drag enforces them).
 *  - `meta.total_items` is read correctly (the old pager read `meta.total`,
 *    which does not exist, and showed "0 از 0").
 *  - Payment shows "بدون پرداخت" when no payment info exists — the old
 *    page defaulted to "paid".
 *  - Stale rows (24h+ in an active status) are flagged inline.
 */

const PAGE_SIZE = 50;

export interface OrdersListViewProps {
  /** Lifted search term — shared with the board view. */
  search: string;
  onSearchChange: (value: string) => void;
  onOpenOrder: (order: AdminOrderRow) => void;
  /**
   * Status the board's «سایر وضعیت‌ها» strip links here with, e.g.
   * `/admin/orders?status=refunded`. `null`/absent = no pre-filter. Only read
   * on mount and on change: the list owns the filter afterwards, so a chip
   * click is not overwritten by a stale prop.
   */
  initialStatus?: OrderStatus | null;
}

export function OrdersListView({
  search,
  onSearchChange,
  onOpenOrder,
  initialStatus = null,
}: OrdersListViewProps) {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [statusFilter, setStatusFilter] = useState<OrderStatus | "all">(
    initialStatus ?? "all",
  );
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AdminOrderPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Bulk selection — cleared on every data change (page/filter/search), so a
  // selection can never survive into a result set the operator cannot see.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkRejected, setBulkRejected] = useState<
    { orderNumber: string; detail: string }[] | null
  >(null);

  const debouncedSearch = useDebouncedValue(search, 350);

  // A board → list deep link (?status=…) re-applies the filter when it
  // changes, so the operator lands on the status they clicked.
  useEffect(() => {
    if (initialStatus) setStatusFilter(initialStatus);
  }, [initialStatus]);

  // Filter changes strand the operator on page N of a smaller result set.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, statusFilter]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await adminOrdersApi.list({
        page,
        pageSize: PAGE_SIZE,
        ...(statusFilter === "all" ? {} : { status: statusFilter }),
        search: debouncedSearch,
      });
      setData(result);
      setSelected(new Set());
    } catch (err) {
      setError(apiErrorMessage(err, "خطا در دریافت سفارش‌ها از سرور."));
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, debouncedSearch]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.totalPages ?? 1;

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allVisibleSelected = rows.length > 0 && rows.every((o) => selected.has(o.id));
  const toggleSelectAllVisible = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) rows.forEach((o) => next.delete(o.id));
      else rows.forEach((o) => next.add(o.id));
      return next;
    });
  };

  const runBulkStatus = async (newStatus: OrderStatus) => {
    if (selected.size === 0) return;
    const label = STATUS_VISUALS[newStatus].label;
    const warning =
      newStatus === "canceled"
        ? " لغو سفارش، موجودی انبار را بازمی‌گرداند و وجه پرداخت‌شده را به کیف پول مشتری برمی‌گرداند."
        : "";
    if (
      !(await confirm({
        title: "تغییر وضعیت گروهی",
        description: `${toPersianDigits(String(selected.size))} سفارش به «${label}» تغییر وضعیت داده شود؟ هر سفارش جداگانه بررسی می‌شود و موارد نامجاز در گزارش نمایش داده می‌شوند.${warning}`,
        confirmLabel: "تغییر وضعیت",
        destructive: newStatus === "canceled",
      }))
    )
      return;

    setBulkBusy(true);
    setBulkRejected(null);
    try {
      const result = await adminBulkApi.bulkUpdateOrderStatus([...selected], newStatus);
      if (result.failed > 0) {
        // A partial run is reported as partial: which orders did NOT move
        // and why, kept on screen until dismissed.
        setBulkRejected(
          result.items
            .filter((i) => !i.success)
            .map((i) => ({
              orderNumber: i.order_number ?? i.order_id.slice(0, 8),
              detail: i.detail ?? i.error_code ?? "نامشخص",
            })),
        );
        toast({
          title: "انجام شد با خطا",
          description: `موفق: ${toPersianDigits(String(result.succeeded))} — ناموفق: ${toPersianDigits(String(result.failed))}`,
          variant: "destructive",
        });
      } else {
        toast({
          title: `وضعیت ${toPersianDigits(String(result.succeeded))} سفارش تغییر کرد`,
          description: label,
          variant: "success",
        });
      }
      await load();
    } catch (err) {
      toast({
        title: "عملیات گروهی ناموفق بود",
        description: apiErrorMessage(err, "خطا در تغییر وضعیت گروهی."),
        variant: "destructive",
      });
    } finally {
      setBulkBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="جستجو در شماره سفارش..."
            className="pe-9 ps-9"
            aria-label="جستجوی سفارش"
          />
          {search && (
            <button
              type="button"
              onClick={() => onSearchChange("")}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="پاک کردن جستجو"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => setStatusFilter("all")}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
              statusFilter === "all"
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground",
            )}
          >
            همه
          </button>
          {ORDER_STATUSES.map((status) => {
            const active = statusFilter === status;
            return (
              <button
                key={status}
                type="button"
                onClick={() => setStatusFilter(active ? "all" : status)}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                  active
                    ? "border-primary bg-primary text-primary-foreground"
                    : cn("hover:border-primary/50", STATUS_VISUALS[status].chip),
                )}
              >
                {STATUS_VISUALS[status].label}
              </button>
            );
          })}
        </div>
      </Card>

      {/* Error */}
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <span className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {error}
          </span>
          <Button variant="outline" size="sm" onClick={() => void load()} className="text-xs">
            تلاش مجدد
          </Button>
        </div>
      )}

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <Card className="flex flex-wrap items-center gap-2 p-3">
          <span className="text-xs text-muted-foreground">
            {toPersianDigits(String(selected.size))} سفارش انتخاب شده:
          </span>
          {BULK_STATUS_OPTIONS.map((status) => (
            <Button
              key={status}
              size="sm"
              variant="outline"
              disabled={bulkBusy}
              onClick={() => void runBulkStatus(status)}
              className={cn("h-8 text-xs", STATUS_VISUALS[status].chip)}
            >
              {STATUS_VISUALS[status].label}
            </Button>
          ))}
          <Button
            size="sm"
            variant="ghost"
            disabled={bulkBusy}
            onClick={() => setSelected(new Set())}
            className="h-8 text-xs"
          >
            لغو انتخاب
          </Button>
        </Card>
      )}

      {/* Rejected orders from the last bulk run — kept on screen because
          "7 of 10 did not move" is only actionable with the reason beside it. */}
      {bulkRejected && bulkRejected.length > 0 && (
        <div
          role="alert"
          className="rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm"
        >
          <div className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 font-semibold text-destructive">
              <AlertTriangle className="h-4 w-4" />
              {toPersianDigits(String(bulkRejected.length))} سفارش تغییر وضعیت نیافت
            </span>
            <Button variant="ghost" size="sm" onClick={() => setBulkRejected(null)}>
              بستن
            </Button>
          </div>
          <ul className="mt-2 space-y-1 text-xs text-destructive">
            {bulkRejected.map((r) => (
              <li key={r.orderNumber}>
                <span className="font-mono">{r.orderNumber}</span> — {r.detail}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Table */}
      <Card className="overflow-hidden">
        <div className="relative overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="w-10 px-4 py-3">
                  <button
                    type="button"
                    onClick={toggleSelectAllVisible}
                    disabled={rows.length === 0}
                    aria-label={allVisibleSelected ? "برداشتن انتخاب همه" : "انتخاب همهٔ ردیف‌های این صفحه"}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    {allVisibleSelected ? (
                      <CheckSquare className="h-4 w-4 text-primary" />
                    ) : (
                      <Square className="h-4 w-4" />
                    )}
                  </button>
                </th>
                <th scope="col" className="px-4 py-3">شماره سفارش</th>
                <th scope="col" className="px-4 py-3">مشتری</th>
                <th scope="col" className="hidden px-4 py-3 lg:table-cell">تاریخ ثبت</th>
                <th scope="col" className="hidden px-4 py-3 lg:table-cell">اقلام</th>
                <th scope="col" className="px-4 py-3">مبلغ کل</th>
                <th scope="col" className="hidden px-4 py-3 md:table-cell">پرداخت</th>
                <th scope="col" className="px-4 py-3">وضعیت</th>
                <th scope="col" className="px-4 py-3">
                  <span className="sr-only">عملیات</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading && rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-0">
                    <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
                      <Loader2 className="h-5 w-5 animate-spin" />
                      در حال دریافت سفارش‌ها...
                    </div>
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-0">
                    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                      <ShoppingCart className="mb-2 h-8 w-8 opacity-40" />
                      <p className="text-sm">هیچ سفارشی با این شرایط یافت نشد.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                rows.map((order) => {
                  const visual = STATUS_VISUALS[order.status];
                  const stale = isOrderStale(order.status, order.createdAt);
                  return (
                    <tr
                      key={order.id}
                      className={cn(
                        "cursor-pointer transition-colors hover:bg-muted/30",
                        stale && "bg-amber-500/5",
                        selected.has(order.id) && "bg-muted/50",
                      )}
                      onClick={() => onOpenOrder(order)}
                    >
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          onClick={() => toggleSelect(order.id)}
                          aria-label={selected.has(order.id) ? `برداشتن انتخاب ${order.orderNumber}` : `انتخاب ${order.orderNumber}`}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          {selected.has(order.id) ? (
                            <CheckSquare className="h-4 w-4 text-primary" />
                          ) : (
                            <Square className="h-4 w-4" />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-foreground">
                            {order.orderNumber}
                          </span>
                          {stale && (
                            <span title="بیش از ۲۴ ساعت در وضعیت فعال">
                              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-xs font-medium text-foreground">
                          {order.customerName ?? "بدون نام پروفایل"}
                        </p>
                        {order.customerPhone && (
                          <p className="font-mono text-[11px] text-muted-foreground" dir="ltr">
                            {toPersianDigits(order.customerPhone)}
                          </p>
                        )}
                      </td>
                      <td className="hidden px-4 py-3 text-xs text-muted-foreground lg:table-cell">
                        {new Date(order.createdAt).toLocaleDateString("fa-IR")}
                      </td>
                      <td className="hidden px-4 py-3 font-mono text-xs lg:table-cell">
                        {toPersianDigits(order.itemsCount)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs font-bold text-foreground">
                        {formatPrice(rialsToToman(order.totalRial))}
                      </td>
                      <td className="hidden px-4 py-3 md:table-cell">
                        {/* The list endpoint carries no payment rows, so the
                            honest label is "بدون اطلاعات پرداخت" — the old
                            page printed a fabricated "پرداخت شده". */}
                        <Badge variant="outline" className="text-[10px] text-muted-foreground">
                          بدون اطلاعات پرداخت
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={cn("text-[11px]", visual.chip)}>
                          {visual.label}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="gap-1 text-xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenOrder(order);
                          }}
                        >
                          <Eye className="h-3.5 w-3.5" />
                          جزئیات
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Pager */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-xs text-muted-foreground">
            {toPersianDigits(total)} سفارش — صفحهٔ {toPersianDigits(page)} از{" "}
            {toPersianDigits(totalPages)}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              قبلی
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages || loading}
              onClick={() => setPage((p) => p + 1)}
            >
              بعدی
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
