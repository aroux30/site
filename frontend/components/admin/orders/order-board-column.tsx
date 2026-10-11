"use client";

import { memo } from "react";
import { useDroppable } from "@dnd-kit/core";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Inbox, Loader2, Sparkles } from "lucide-react";
import { cn, formatPrice, toPersianDigits } from "@/lib/utils";
import { BOARD_COLUMN_BODY_CLASS } from "@/lib/admin/board-layout";
import {
  STATUS_VISUALS,
  isOrderStale,
  rialsToToman,
  type OrderStatus,
} from "@/lib/admin/order-domain";
import type { AdminOrderRow } from "@/lib/api/admin-orders";
import type { AdminOrderStatusCount } from "@/lib/api/admin-orders";
import { OrderBoardCard } from "./order-board-card";

/**
 * Gaming-aesthetic board column.
 *
 * Visual language:
 *  - Top neon indicator bar with CSS glow
 *  - Header with gradient background + glass morphism
 *  - Drop target: pulsing ring (legal) / red ring (illegal)
 *  - Empty state: subtle animated pulse
 *  - Card list memoized separately from column chrome
 */

// ── Column glow effects ──────────────────────────────────────────────────

// Keyed by COLUMN status, not by any status a card may hold: only the
// customizable lanes can become a column, so a card status missing here just
// falls back to the primary ring (see `ringGlow` below).
const COLUMN_RING_GLOW: Record<string, string> = {
  processing: "ring-indigo-500/50 shadow-indigo-500/20",
  completed: "ring-teal-500/50 shadow-teal-500/20",
  canceled: "ring-rose-600/50 shadow-rose-600/20",
  refunded: "ring-slate-500/50 shadow-slate-500/20",
};

const COLUMN_HEADER_BG: Record<string, string> = {
  processing: "from-indigo-500/10 via-indigo-500/5 to-transparent dark:from-indigo-500/15 dark:via-indigo-950/30",
  completed: "from-teal-500/10 via-teal-500/5 to-transparent dark:from-teal-500/15 dark:via-teal-950/30",
  canceled: "from-rose-500/10 via-rose-500/5 to-transparent dark:from-rose-500/15 dark:via-rose-950/30",
  refunded: "from-slate-500/10 via-slate-500/5 to-transparent dark:from-slate-500/15 dark:via-slate-950/30",
};

export interface OrderBoardColumnProps {
  status: OrderStatus;
  orders: AdminOrderRow[];
  stats: AdminOrderStatusCount | undefined;
  /**
   * When the lane groups several backend statuses (e.g. «در حال پردازش» =
   * waiting_payment_gateway + waiting_payment_card + pending + processing), the header says
   * so. Without this the lane would claim one status while holding four, and a
   * card whose label reads «در انتظار تایید کارت به کارت» would sit under a
   * column titled «در حال پردازش» with no explanation.
   */
  grouped?: readonly OrderStatus[];
  loading: boolean;
  hasMore: boolean;
  /** The columns currently on screen; forwarded to each card so its advance
   *  button only offers stages with a visible column to land in. */
  visibleColumns: readonly OrderStatus[];
  onLoadMore: (status: OrderStatus) => void;
  onOpen: (order: AdminOrderRow) => void;
  onAdvance: (order: AdminOrderRow, next: OrderStatus) => void;
  busyOrderId: string | null;
  isLegalTarget: boolean;
  isOver: boolean;
}

const OrderCardList = memo(function OrderCardList({
  orders,
  onOpen,
  onAdvance,
  busyOrderId,
  visibleColumns,
}: {
  orders: AdminOrderRow[];
  onOpen: (order: AdminOrderRow) => void;
  onAdvance: (order: AdminOrderRow, next: OrderStatus) => void;
  busyOrderId: string | null;
  visibleColumns: readonly OrderStatus[];
}) {
  return (
    <>
      {orders.map((order) => (
        <OrderBoardCard
          key={order.id}
          order={order}
          onOpen={onOpen}
          onAdvance={onAdvance}
          busy={busyOrderId === order.id}
          visibleColumns={visibleColumns}
        />
      ))}
    </>
  );
});

function OrderBoardColumnInner({
  status,
  orders,
  stats,
  grouped,
  loading,
  hasMore,
  visibleColumns,
  onLoadMore,
  onOpen,
  onAdvance,
  busyOrderId,
  isLegalTarget,
  isOver,
}: OrderBoardColumnProps) {
  const visual = STATUS_VISUALS[status];
  const { setNodeRef } = useDroppable({ id: `status:${status}` });

  const staleCount = orders.filter((o) => isOrderStale(o.status, o.createdAt)).length;
  const ringGlow = COLUMN_RING_GLOW[status] ?? "ring-primary/50";
  const headerBg = COLUMN_HEADER_BG[status] ?? "";

  return (
    <div
      ref={setNodeRef}
      data-column-status={status}
      className={cn(
        // `min-w-0` so the column can actually shrink below its content's
        // intrinsic width — the grid track (`minmax(260px, 1fr)`) sets the floor
        // and the frame scrolls when the slide cannot fit. Content that genuinely
        // cannot shrink is clipped by `overflow-hidden`, not pushed out of the board.
        "flex h-full w-full min-w-0 max-w-none flex-col overflow-hidden rounded-2xl border transition-all duration-300",
        // Solid background — blur only on the header, not the whole column
        "bg-card dark:bg-card/90",
        // Drop state rings with glow
        isOver && isLegalTarget && cn("ring-2 shadow-lg", ringGlow),
        isOver && !isLegalTarget && "ring-2 ring-destructive/60 shadow-lg shadow-destructive/20",
        !isOver && "border-border/50 shadow-sm dark:border-border/30",
      )}
    >
      {/* Neon top indicator with glow */}
      <div className="relative">
        <div className={cn("h-1 w-full", visual.dot)} />
        <div className={cn("absolute inset-x-0 top-0 h-2 blur-md opacity-50", visual.dot)} />
      </div>

      {/* Header — gradient, solid in light, subtle blur only in dark */}
      <div className={cn("border-b border-border/40 p-3.5 bg-gradient-to-b dark:border-border/20 dark:backdrop-blur-sm", headerBg)}>
        <div className="mb-1.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={cn("h-2.5 w-2.5 rounded-full shadow-sm", visual.dot)} />
            <h3 className="text-sm font-extrabold tracking-tight text-foreground">{visual.label}</h3>
          </div>
          <div className="flex items-center gap-1.5">
            {staleCount > 0 && (
              <span className="flex h-5 items-center gap-1 rounded-full bg-amber-500/20 px-1.5 font-mono text-[10px] font-bold text-amber-500 animate-pulse">
                <AlertTriangle className="h-2.5 w-2.5" />
                {toPersianDigits(staleCount)}
              </span>
            )}
            <span className={cn(
              "flex h-6 items-center rounded-full border px-2.5 font-mono text-xs font-black tabular-nums",
              visual.chip,
            )}>
              {stats ? toPersianDigits(stats.count) : "—"}
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between text-[11px]">
          <span className="truncate text-muted-foreground/70">{visual.description}</span>
          <span className="shrink-0 font-mono font-bold text-foreground/60">
            {stats ? formatPrice(rialsToToman(stats.totalRial)) : ""}
          </span>
        </div>
        {/* Grouped lane: name the statuses it holds, so the column title is
            never a claim the cards below it contradict. */}
        {grouped && grouped.length > 1 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {grouped.map((member) => (
              <span
                key={member}
                className="rounded-full border border-border/50 bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground"
              >
                {STATUS_VISUALS[member].label}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Cards — scrolls inside the board's fixed-height frame so the frame's own
          horizontal scrollbar stays just under the toolbar instead of 4,700px
          below the fold. `min-h-0` is what lets the flex child shrink below its
          content and scroll instead of pushing the frame taller. */}
      <div className={BOARD_COLUMN_BODY_CLASS}>
        {loading && orders.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-primary/60" />
          </div>
        ) : orders.length === 0 ? (
          <div
            className={cn(
              "flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed p-6 text-center transition-all",
              isOver && isLegalTarget
                ? "border-primary/40 bg-primary/5"
                : "border-border/50 dark:border-border/30",
              isOver && !isLegalTarget && "border-destructive/40 bg-destructive/5",
            )}
          >
            <div className="relative">
              <Inbox className="h-8 w-8 text-muted-foreground/20" />
              {isOver && isLegalTarget && (
                <Sparkles className="absolute -right-1 -top-1 h-4 w-4 text-primary animate-pulse" />
              )}
            </div>
            <p className="mt-2 text-xs text-muted-foreground/40">آماده دریافت</p>
          </div>
        ) : (
          <OrderCardList
            orders={orders}
            onOpen={onOpen}
            onAdvance={onAdvance}
            busyOrderId={busyOrderId}
            visibleColumns={visibleColumns}
          />
        )}
      </div>

      {/* «نمایش بیشتر» — OUTSIDE the scrolling card list, pinned to the foot of
          the column. Inside the list it is the last thing to scroll past, and on
          a column holding 20 cards that is twenty cards down. */}
      {hasMore && (
        <div className="shrink-0 px-2.5 pb-2.5 pt-1">
          <button
            type="button"
            disabled={loading}
            onClick={() => onLoadMore(status)}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-border/50 py-2 text-[11px] font-medium text-muted-foreground/60 transition-all hover:border-primary/30 hover:text-primary dark:border-border/30"
          >
            {loading && <Loader2 className="h-3 w-3 animate-spin" />}
            نمایش بیشتر
            {stats && stats.count > orders.length && (
              <span className="rounded-full bg-muted/50 px-2 py-0.5 font-mono text-[9px]">
                +{toPersianDigits(stats.count - orders.length)}
              </span>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

export const OrderBoardColumn = memo(OrderBoardColumnInner);
