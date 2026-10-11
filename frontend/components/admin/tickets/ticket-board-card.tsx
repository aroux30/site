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
  MessageSquare,
  Phone,
  RefreshCw,
  Sparkles,
  User,
  Zap,
} from "lucide-react";
import { cn, toPersianDigits } from "@/lib/utils";
import {
  TICKET_NEXT_STEP,
  TICKET_PRIORITY_VISUALS,
  TICKET_STATUS_VISUALS,
  TICKET_STALE_AFTER_HOURS,
  formatTicketRelativeTime,
  hoursSinceUpdate,
  isTicketStale,
  ticketAdvanceLabel,
  type TicketStatus,
} from "@/lib/admin/ticket-domain";
import type { TicketItem } from "@/lib/api/tickets";

/**
 * Gaming-aesthetic ticket card — same visual language as the orders card:
 * glass morphism, colored glow shadows, neon accents, micro-interactions.
 */

export interface TicketBoardCardProps {
  ticket: TicketItem;
  onOpen: (ticket: TicketItem) => void;
  onAdvance: (ticket: TicketItem, next: TicketStatus) => void;
  busy: boolean;
  overlay?: boolean;
}

const STATUS_GLOW: Record<TicketStatus, string> = {
  open: "shadow-sky-500/20 hover:shadow-sky-500/40",
  in_progress: "shadow-indigo-500/20 hover:shadow-indigo-500/40",
  waiting: "shadow-amber-500/20 hover:shadow-amber-500/40",
  resolved: "shadow-emerald-500/20 hover:shadow-emerald-500/40",
  closed: "shadow-slate-500/20 hover:shadow-slate-500/40",
};

const STATUS_BORDER_GLOW: Record<TicketStatus, string> = {
  open: "border-sky-500/30 dark:border-sky-400/20",
  in_progress: "border-indigo-500/30 dark:border-indigo-400/20",
  waiting: "border-amber-500/30 dark:border-amber-400/20",
  resolved: "border-emerald-500/30 dark:border-emerald-400/20",
  closed: "border-slate-500/30 dark:border-slate-400/20",
};

interface TicketCardBodyProps {
  ticket: TicketItem;
  onOpen: (ticket: TicketItem) => void;
  onAdvance: (ticket: TicketItem, next: TicketStatus) => void;
  busy: boolean;
  overlay: boolean;
  activatorRef?: Ref<HTMLButtonElement>;
}

const TicketCardBody = memo(function TicketCardBody({
  ticket,
  onOpen,
  onAdvance,
  busy,
  overlay,
  activatorRef,
}: TicketCardBodyProps) {
  const statusVisual = TICKET_STATUS_VISUALS[ticket.status];
  const priorityVisual = TICKET_PRIORITY_VISUALS[ticket.priority];
  const stale = isTicketStale(ticket.status, ticket.updated_at);
  const next = TICKET_NEXT_STEP[ticket.status];
  const advanceLabel = ticketAdvanceLabel(ticket.status);

  return (
    <>
      {stale && (
        <div className="mb-2.5 flex items-center justify-between rounded-lg border border-amber-500/40 bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-transparent px-2.5 py-1.5 text-[11px] font-bold text-amber-400 dark:text-amber-300 animate-pulse">
          <span className="flex items-center gap-1.5">
            <Zap className="h-3.5 w-3.5 text-amber-500" />
            +{toPersianDigits(TICKET_STALE_AFTER_HOURS)} ساعت بدون تغییر
          </span>
          <span className="rounded-full bg-amber-500/25 px-2 py-0.5 font-mono text-[10px] tabular-nums">
            {toPersianDigits(hoursSinceUpdate(ticket.updated_at))}h
          </span>
        </div>
      )}

      {/* Header */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <button
            ref={activatorRef}
            type="button"
            className="shrink-0 rounded-md p-0.5 text-muted-foreground/40 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={`جابه‌جایی تیکت ${ticket.ticket_number} با صفحه‌کلید`}
            onPointerDown={(e) => e.stopPropagation()}
          >
            <GripVertical className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => onOpen(ticket)}
            className="truncate font-mono text-xs font-extrabold tracking-tight text-foreground transition-colors hover:text-primary"
            title="مشاهدهٔ گفتگو"
          >
            {ticket.ticket_number}
          </button>
        </div>
        <span className={cn(
          "flex h-5 items-center gap-1 rounded-full border px-1.5 text-[10px] font-bold",
          priorityVisual.chip,
        )}>
          <span className={cn("h-1.5 w-1.5 rounded-full", priorityVisual.dot)} />
          {priorityVisual.label}
        </span>
      </div>

      {/* Subject */}
      <p className="mb-2 line-clamp-2 text-xs font-bold leading-relaxed text-foreground">
        {ticket.subject}
      </p>

      {/* Customer — frosted glass */}
      <div className="mb-2.5 rounded-lg border border-border/50 bg-muted/50 p-2.5 text-xs dark:border-border/30 dark:bg-muted/30">
        <div className="flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-1.5 font-semibold text-foreground">
            <User className="h-3.5 w-3.5 shrink-0 text-primary" />
            <span className="truncate">{ticket.customer_name ?? "—"}</span>
          </span>
          {ticket.customer_phone && (
            <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] text-muted-foreground/80" dir="ltr">
              <Phone className="h-2.5 w-2.5" />
              {toPersianDigits(ticket.customer_phone)}
            </span>
          )}
        </div>
        {ticket.last_message_preview && (
          <p className="mt-1.5 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground/70">
            {ticket.last_message_preview}
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="mb-2.5 flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 text-muted-foreground/80">
          <MessageSquare className="h-3.5 w-3.5" />
          <span className="font-mono">{toPersianDigits(ticket.messages_count ?? 0)}</span>
          <span className="text-[10px]">پیام</span>
        </span>
        <span
          className="flex items-center gap-1 rounded-full bg-muted/60 px-2 py-0.5 text-[10px] text-muted-foreground"
          title={new Date(ticket.updated_at).toLocaleString("fa-IR")}
        >
          <Clock className="h-2.5 w-2.5" />
          {formatTicketRelativeTime(ticket.updated_at, toPersianDigits)}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between gap-1.5 border-t border-border/40 pt-2.5 dark:border-border/20">
        <button
          type="button"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => onOpen(ticket)}
          className="flex h-7 items-center gap-1 rounded-lg border border-border/50 bg-muted/60 px-2.5 text-[11px] font-medium text-muted-foreground transition-all hover:bg-muted hover:text-foreground dark:border-border/30"
        >
          گفتگو
        </button>

        {next && advanceLabel ? (
          <button
            type="button"
            disabled={busy}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => onAdvance(ticket, next)}
            className={cn(
              "flex h-7 items-center gap-1 rounded-lg px-3 text-[11px] font-bold text-white transition-all",
              "bg-gradient-to-l shadow-lg active:scale-95",
              TICKET_STATUS_VISUALS[next].solid,
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
            statusVisual.chip,
          )}>
            {statusVisual.label}
          </span>
        )}
      </div>
    </>
  );
});

function TicketBoardCardShell({
  ticket,
  onOpen,
  onAdvance,
  busy,
  overlay = false,
}: TicketBoardCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    isDragging,
  } = useDraggable({ id: ticket.id, disabled: overlay });

  const stale = isTicketStale(ticket.status, ticket.updated_at);
  const glowClass = STATUS_GLOW[ticket.status] ?? "";
  const borderGlow = STATUS_BORDER_GLOW[ticket.status] ?? "border-border/40";

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
        "bg-card",
        "shadow-md",
        glowClass,
        overlay
          ? "rotate-2 scale-105 border-primary/60 shadow-xl shadow-primary/30 ring-2 ring-primary/40 backdrop-blur-md"
          : cn(borderGlow, "hover:scale-[1.02] hover:shadow-lg"),
        stale && !overlay && "border-amber-500/50 shadow-amber-500/30 ring-1 ring-amber-500/30",
      )}
      aria-label={`تیکت ${ticket.ticket_number}`}
    >
      <div className={cn(
        "absolute inset-x-3 top-0 h-[2px] rounded-full opacity-60",
        TICKET_STATUS_VISUALS[ticket.status].dot,
      )} />

      <TicketCardBody
        ticket={ticket}
        onOpen={onOpen}
        onAdvance={onAdvance}
        busy={busy}
        overlay={overlay}
        activatorRef={overlay ? undefined : setActivatorNodeRef}
      />
    </div>
  );

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

export const TicketBoardCard = memo(TicketBoardCardShell);
