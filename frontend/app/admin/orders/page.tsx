"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Kanban, List, Search, ShoppingCart, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { OrdersBoard } from "@/components/admin/orders/orders-board";
import { OrdersListView } from "@/components/admin/orders/orders-list-view";
import { OrderDetailSheet } from "@/components/admin/orders/order-detail-sheet";
import type { AdminOrderRow } from "@/lib/api/admin-orders";
import { ORDER_STATUSES, type OrderStatus } from "@/lib/admin/order-domain";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";

/** Guards the `?status=` deep link against junk values (any string in the URL). */
function isOrderStatus(value: string | null): value is OrderStatus {
  return value != null && (ORDER_STATUSES as readonly string[]).includes(value);
}

/**
 * مدیریت سفارش‌ها — one page, two views.
 *
 * `/admin/orders` (list) and `/admin/kanban` (board) used to be two separate
 * pages with two separate nav entries, two data mappers, two status
 * vocabularies and two detail modals. They are now ONE page with a view
 * switch: the list is for scanning/filtering, the board is for moving
 * orders through the pipeline by drag & drop. `/admin/kanban` redirects
 * here with `?view=board`.
 *
 * The view is kept in the URL (`?view=board`) so the choice survives a
 * refresh, a bookmark, and the sidebar link.
 *
 * The drawer (`OrderDetailSheet`) is shared by both views — opening an
 * order from a list row and from a board card lands in the same surface,
 * with the same legal transitions.
 */

type ViewMode = "list" | "board";

const VIEW_STORAGE_KEY = "admin-orders-view";

function OrdersPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const urlView = searchParams.get("view");
  const [view, setView] = useState<ViewMode>(urlView === "board" ? "board" : "list");
  // The board's «سایر وضعیت‌ها» strip deep-links here (?status=refunded), so
  // the list must open already filtered — otherwise the link looks dead.
  const deepLinkStatus = searchParams.get("status");
  const [initialStatus, setInitialStatus] = useState<OrderStatus | null>(
    isOrderStatus(deepLinkStatus) ? deepLinkStatus : null,
  );
  useEffect(() => {
    setInitialStatus(isOrderStatus(deepLinkStatus) ? deepLinkStatus : null);
  }, [deepLinkStatus]);
  const [search, setSearch] = useState("");
  const [openOrderId, setOpenOrderId] = useState<string | null>(null);
  // Bumped to force the board to resync after a drawer transition.
  const [boardSyncToken, setBoardSyncToken] = useState(0);
  // The board fetches 7 columns per keystroke without this.
  const debouncedSearch = useDebouncedValue(search, 350);

  // Restore the operator's last view when the URL does not pin one.
  useEffect(() => {
    if (urlView === "board" || urlView === "list") return;
    try {
      const saved = window.localStorage.getItem(VIEW_STORAGE_KEY);
      if (saved === "board") setView("board");
    } catch {
      /* preference is optional */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchView = (next: ViewMode) => {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, next);
    } catch {
      /* preference is optional */
    }
    const params = new URLSearchParams(searchParams.toString());
    if (next === "board") params.set("view", "board");
    else params.delete("view");
    const qs = params.toString();
    router.replace(qs ? `/admin/orders?${qs}` : "/admin/orders", { scroll: false });
  };

  const openOrder = (order: AdminOrderRow) => setOpenOrderId(order.id);

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
            <ShoppingCart className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              مدیریت سفارش‌ها
            </h1>
            <p className="text-xs text-muted-foreground sm:text-sm">
              مشاهده، جستجو و انتقال سفارش‌ها در خط پردازش (نمای لیست و کانبان)
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Search — shared by both views */}
          <div className="relative w-full sm:w-64">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجو در شماره سفارش..."
              className="h-9 ps-9 pe-9 text-xs sm:text-sm"
              aria-label="جستجوی سفارش"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label="پاک کردن جستجو"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* View switch */}
          <div
            role="tablist"
            aria-label="حالت نمایش سفارش‌ها"
            className="flex items-center rounded-lg border border-border bg-muted/40 p-0.5"
          >
            <button
              role="tab"
              aria-selected={view === "list"}
              type="button"
              onClick={() => switchView("list")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                view === "list"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <List className="h-3.5 w-3.5" />
              لیست
            </button>
            <button
              role="tab"
              aria-selected={view === "board"}
              type="button"
              onClick={() => switchView("board")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                view === "board"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Kanban className="h-3.5 w-3.5" />
              کانبان
            </button>
          </div>
        </div>
      </div>

      {/* Views. The board is keyed by the sync token so a drawer transition
          remounts it with fresh column data. */}
      {view === "list" ? (
        <OrdersListView
          search={search}
          onSearchChange={setSearch}
          onOpenOrder={openOrder}
          initialStatus={initialStatus}
        />
      ) : (
        <OrdersBoard
          key={boardSyncToken}
          search={debouncedSearch}
          onOpenOrder={openOrder}
        />
      )}

      {/* Shared detail drawer */}
      <OrderDetailSheet
        orderId={openOrderId}
        onClose={() => setOpenOrderId(null)}
        onStatusChanged={() => {
          if (view === "board") setBoardSyncToken((t) => t + 1);
        }}
      />
    </div>
  );
}

/**
 * `useSearchParams` opts the subtree out of static prerendering; the
 * Suspense boundary is what keeps the build from failing on it (the same
 * pattern the products admin page uses).
 */
export default function AdminOrdersPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-64 items-center justify-center text-muted-foreground">
          در حال بارگذاری...
        </div>
      }
    >
      <OrdersPageInner />
    </Suspense>
  );
}
