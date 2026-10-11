"use client";

import { memo } from "react";
import type { Ref } from "react";
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ChevronLeft,
  Clock,
  GripVertical,
  MapPin,
  Package,
  Phone,
  RefreshCw,
  Sparkles,
  User,
  Zap,
} from "lucide-react";
import { cn, formatPrice, toPersianDigits } from "@/lib/utils";
import {
  BOARD_COLUMNS,
  STATUS_VISUALS,
  advanceActionLabel,
  formatRelativeTime,
  hoursSince,
  isOrderStale,
  nextInPipeline,
  rialsToToman,
  statusToColumnFor,
  STALE_AFTER_HOURS,
  type OrderStatus,
} from "@/lib/admin/order-domain";
import type { AdminOrderRow } from "@/lib/api/admin-orders";

/**
 * Gaming-aesthetic order card on the fulfillment board.
 *
 * Visual language:
 *  - Glass morphism: translucent bg + backdrop-blur + subtle border gradient
 *  - Colored glow shadows per status (not just a flat border)
 *  - Neon accent on the advance button + stale warning
 *  - Micro-interactions: scale on hover, pulse on stale, glow on drag overlay
 *
 * Performance architecture unchanged (shell/body split, memo, useDraggable).
 */

export interface OrderBoardCardProps {
  order: AdminOrderRow;
  onOpen: (order: AdminOrderRow) => void;
  onAdvance: (order: AdminOrderRow, next: OrderStatus) => void;
  busy: boolean;
  overlay?: boolean;
  /**
   * The columns currently on screen. The advance button is only offered when
   * the target stage has a VISIBLE column to land in — otherwise clicking
   * «تکمیل سفارش» on a board where «تکمیل شده» is hidden would move the card
   * into a column nobody can see and it would simply vanish.
   */
  visibleColumns?: readonly OrderStatus[];
}

// ── Status glow colors (CSS box-shadow) ───────────────────────────────────

const STATUS_GLOW: Record<OrderStatus, string> = {
  waiting_payment_gateway: "shadow-amber-500/20 hover:shadow-amber-500/40",
  waiting_payment_card: "shadow-violet-500/20 hover:shadow-violet-500/40",
  pending: "shadow-blue-500/20 hover:shadow-blue-500/40",
  processing: "shadow-indigo-500/20 hover:shadow-indigo-500/40",
  completed: "shadow-teal-500/20 hover:shadow-teal-500/40",
  canceled: "shadow-rose-600/20 hover:shadow-rose-600/40",
  refunded: "shadow-slate-500/20 hover:shadow-slate-500/40",
};

const STATUS_BORDER_GLOW: Record<string, string> = {
  waiting_payment_gateway: "border-amber-500/30 dark:border-amber-400/20",
  waiting_payment_card: "border-violet-500/30 dark:border-violet-400/20",
  pending: "border-blue-500/30 dark:border-blue-400/20",
  processing: "border-indigo-500/30 dark:border-indigo-400/20",
  completed: "border-teal-500/30 dark:border-teal-400/20",
};

interface OrderCardBodyProps {
  order: AdminOrderRow;
  onOpen: (order: AdminOrderRow) => void;
  onAdvance: (order: AdminOrderRow, next: OrderStatus) => void;
  busy: boolean;
  overlay: boolean;
  visibleColumns: readonly OrderStatus[];
  activatorRef?: Ref<HTMLButtonElement>;
}

const OrderCardBody = memo(function OrderCardBody({
  order,
  onOpen,
  onAdvance,
  busy,
  overlay,
  visibleColumns,
  activatorRef,
}: OrderCardBodyProps) {
  const visual = STATUS_VISUALS[order.status];
  const stale = isOrderStale(order.status, order.createdAt);
  // Advance one legal stage, and only if the target has a VISIBLE column to
  // land in: the last stage of «در حال پردازش» (processing) advances into
  // «تکمیل شده», and when that column is hidden the button must not offer a
  // move that would make the card vanish off the board.
  const candidate = nextInPipeline(order.status);
  const next =
    candidate && statusToColumnFor(candidate, visibleColumns) !== undefined && candidate !== order.status
      ? candidate
      : null;
  const advanceLabel = next ? advanceActionLabel(order.status) : null;

  return (
    <>
      {/* Stale warning — neon pulse */}
      {stale && (
        <div className="mb-2.5 flex items-center justify-between rounded-lg border border-amber-500/40 bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-transparent px-2.5 py-1.5 text-[11px] font-bold text-amber-400 dark:text-amber-300 animate-pulse">
          <span className="flex items-center gap-1.5">
            <Zap className="h-3.5 w-3.5 text-amber-500" />
            +{toPersianDigits(STALE_AFTER_HOURS)} ساعت از ثبت
          </span>
          <span className="rounded-full bg-amber-500/25 px-2 py-0.5 font-mono text-[10px] tabular-nums">
            {toPersianDigits(hoursSince(order.createdAt))}h
          </span>
        </div>
      )}

      {/* Header: grip + order number + time */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <button
            ref={activatorRef}
            type="button"
            className="shrink-0 rounded-md p-0.5 text-muted-foreground/40 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`جابه‌جایی سفارش ${order.orderNumber} با صفحه‌کلید`}
            onPointerDown={(e) => e.stopPropagation()}
          >
            <GripVertical className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => onOpen(order)}
            className="truncate font-mono text-xs font-extrabold tracking-tight text-foreground transition-colors hover:text-primary"
            title="مشاهدهٔ جزئیات سفارش"
          >
            {order.orderNumber}
          </button>
        </div>
        <span
          className="flex shrink-0 items-center gap-1 rounded-full bg-muted/60 px-2 py-0.5 text-[10px] text-muted-foreground"
          title={new Date(order.createdAt).toLocaleString("fa-IR")}
        >
          <Clock className="h-2.5 w-2.5" />
          {formatRelativeTime(order.createdAt, toPersianDigits)}
        </span>
      </div>

      {/* Customer — solid sub-card (no blur) */}
      <div className="mb-2.5 rounded-lg border border-border/50 bg-muted/50 p-2.5 text-xs dark:border-border/30 dark:bg-muted/30">
        <div className="flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-1.5 font-semibold text-foreground">
            <User className="h-3.5 w-3.5 shrink-0 text-primary" />
            <span className="truncate">{order.customerName ?? "—"}</span>
          </span>
          {order.customerPhone && (
            <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] text-muted-foreground" dir="ltr">
              <Phone className="h-2.5 w-2.5" />
              {toPersianDigits(order.customerPhone)}
            </span>
          )}
        </div>
      </div>

      {/* Items + total — clean line */}
      <div className="mb-2.5 flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 text-muted-foreground/80">
          <Package className="h-3.5 w-3.5" />
          <span className="font-mono">{toPersianDigits(order.itemsCount)}</span>
          <span className="text-[10px]">قلم</span>
        </span>
        <span className="font-mono text-sm font-black tracking-tight text-foreground">
          {formatPrice(rialsToToman(order.totalRial))}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between gap-1.5 border-t border-border/40 pt-2.5 dark:border-border/20">
        <button
          type="button"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => onOpen(order)}
          className="flex h-7 items-center gap-1 rounded-lg border border-border/50 bg-muted/60 px-2.5 text-[11px] font-medium text-muted-foreground transition-all hover:bg-muted hover:text-foreground dark:border-border/30"
        >
          <MapPin className="h-3 w-3" />
          جزئیات
        </button>

        {next && advanceLabel ? (
          <button
            type="button"
            disabled={busy}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => onAdvance(order, next)}
            className={cn(
              "flex h-7 items-center gap-1 rounded-lg px-3 text-[11px] font-bold text-white transition-all",
              "bg-gradient-to-l shadow-lg active:scale-95",
              visual.solid,
              busy && "opacity-60",
            )}
          >
            {busy ? (
              <RefreshCw className="h-3 w-3 animate-spin" />
            ) : (
              <>
                <Sparkles className="h-3 w-3" />
                {advanceLabel}
                <ChevronLeft className="h-3 w-3" />
              </>
            )}
          </button>
        ) : (
          <span className={cn(
            "flex h-6 items-center gap-1 rounded-full px-2.5 text-[10px] font-bold",
            visual.chip,
          )}>
            {visual.label}
          </span>
        )}
      </div>
    </>
  );
});

/* ── Shell: the cheap context subscriber ───────────────────────────────── */

function OrderBoardCardShell({
  order,
  onOpen,
  onAdvance,
  busy,
  overlay = false,
  visibleColumns = BOARD_COLUMNS,
}: OrderBoardCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    isDragging,
  } = useDraggable({ id: order.id, disabled: overlay });

  const stale = isOrderStale(order.status, order.createdAt);
  const glowClass = STATUS_GLOW[order.status] ?? "";
  const borderGlow = STATUS_BORDER_GLOW[order.status] ?? "border-border/40";

  const style = overlay
    ? undefined
    : {
        transform: CSS.Translate.toString(transform),
        opacity: isDragging ? 0.3 : undefined,
      };

  const card = (
    <div
      ref={overlay ? undefined : setNodeRef}
      style={style}
      {...(overlay ? {} : attributes)}
      {...(overlay ? {} : listeners)}
      className={cn(
        "group relative rounded-xl border p-3.5 transition-all duration-200",
        "cursor-grab active:cursor-grabbing select-none",
        // Solid card — NO backdrop-blur on cards (blurs 80 cards = GPU
        // overload + washed-out look in light mode). Glass effect is only
        // on the drag overlay clone and column headers.
        "bg-card shadow-md",
        // Colored glow shadow per status
        glowClass,
        // Border with status tint
        overlay
          ? "rotate-2 scale-105 border-primary/60 shadow-xl shadow-primary/30 ring-2 ring-primary/40 backdrop-blur-md"
          : cn(borderGlow, "hover:scale-[1.02] hover:shadow-lg"),
        // Stale cards get a persistent warning glow
        stale && !overlay && "border-amber-500/50 shadow-amber-500/30 ring-1 ring-amber-500/30",
      )}
      aria-label={`سفارش ${order.orderNumber}`}
    >
      {/* Top accent line — neon glow effect */}
      <div className={cn(
        "absolute inset-x-3 top-0 h-[2px] rounded-full opacity-60",
        STATUS_VISUALS[order.status].dot,
      )} />

      <OrderCardBody
        order={order}
        onOpen={onOpen}
        onAdvance={onAdvance}
        busy={busy}
        overlay={overlay}
        visibleColumns={visibleColumns}
        activatorRef={overlay ? undefined : setActivatorNodeRef}
      />
    </div>
  );

  // Overlay clone gets an entrance animation
  if (overlay) {
    return (
      <motion.div
        initial={{ scale: 0.95, opacity: 0.8 }}
        animate={{ scale: 1.05, opacity: 1 }}
        transition={{ type: "spring", stiffness: 400, damping: 25 }}
      >
        {card}
      </motion.div>
    );
  }

  return card;
}

export const OrderBoardCard = memo(OrderBoardCardShell);
