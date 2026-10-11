"use client";

import { memo } from "react";
import { useDroppable } from "@dnd-kit/core";
import { AlertTriangle, Inbox, Loader2, Sparkles } from "lucide-react";
import { cn, toPersianDigits } from "@/lib/utils";
import { BOARD_COLUMN_BODY_CLASS } from "@/lib/admin/board-layout";
import {
  TICKET_STATUS_VISUALS,
  isTicketStale,
  type TicketStatus,
} from "@/lib/admin/ticket-domain";
import type { TicketItem } from "@/lib/api/tickets";
import { TicketBoardCard } from "./ticket-board-card";

/**
 * Gaming-aesthetic ticket board column — same glass morphism, neon
 * indicators, and glow effects as the orders column.
 */

const COLUMN_RING_GLOW: Record<TicketStatus, string> = {
  open: "ring-sky-500/50 shadow-sky-500/20",
  in_progress: "ring-indigo-500/50 shadow-indigo-500/20",
  waiting: "ring-amber-500/50 shadow-amber-500/20",
  resolved: "ring-emerald-500/50 shadow-emerald-500/20",
  closed: "ring-slate-500/50 shadow-slate-500/20",
};

const COLUMN_HEADER_BG: Record<TicketStatus, string> = {
  open: "from-sky-500/10 via-sky-500/5 to-transparent dark:from-sky-500/15 dark:via-sky-950/30",
  in_progress: "from-indigo-500/10 via-indigo-500/5 to-transparent dark:from-indigo-500/15 dark:via-indigo-950/30",
  waiting: "from-amber-500/10 via-amber-500/5 to-transparent dark:from-amber-500/15 dark:via-amber-950/30",
  resolved: "from-emerald-500/10 via-emerald-500/5 to-transparent dark:from-emerald-500/15 dark:via-emerald-950/30",
  closed: "from-slate-500/10 via-slate-500/5 to-transparent dark:from-slate-500/15 dark:via-slate-950/30",
};

export interface TicketBoardColumnProps {
  status: TicketStatus;
  tickets: TicketItem[];
  totalCount: number | undefined;
  loading: boolean;
  hasMore: boolean;
  onLoadMore: (status: TicketStatus) => void;
  onOpen: (ticket: TicketItem) => void;
  onAdvance: (ticket: TicketItem, next: TicketStatus) => void;
  busyTicketId: string | null;
  isLegalTarget: boolean;
  isOver: boolean;
}

const TicketCardList = memo(function TicketCardList({
  tickets,
  onOpen,
  onAdvance,
  busyTicketId,
}: {
  tickets: TicketItem[];
  onOpen: (ticket: TicketItem) => void;
  onAdvance: (ticket: TicketItem, next: TicketStatus) => void;
  busyTicketId: string | null;
}) {
  return (
    <>
      {tickets.map((ticket) => (
        <TicketBoardCard
          key={ticket.id}
          ticket={ticket}
          onOpen={onOpen}
          onAdvance={onAdvance}
          busy={busyTicketId === ticket.id}
        />
      ))}
    </>
  );
});

function TicketBoardColumnInner({
  status,
  tickets,
  totalCount,
  loading,
  hasMore,
  onLoadMore,
  onOpen,
  onAdvance,
  busyTicketId,
  isLegalTarget,
  isOver,
}: TicketBoardColumnProps) {
  const visual = TICKET_STATUS_VISUALS[status];
  const { setNodeRef } = useDroppable({ id: `tstatus:${status}` });

  const staleCount = tickets.filter((t) => isTicketStale(t.status, t.updated_at)).length;
  const ringGlow = COLUMN_RING_GLOW[status];
  const headerBg = COLUMN_HEADER_BG[status];

  return (
    <div
      ref={setNodeRef}
      data-ticket-column-status={status}
      className={cn(
        // Width comes from the grid track, which carries the 300px floor
        // (`boardGridTemplate`). This column must not impose its own width:
        // the old `min-w-[300px] max-w-[340px]` capped it BELOW the track, so
        // a 300px track rendered a 300px column inside a 300px track plus 16px
        // of gap — the columns never lined up with their grid columns.
        // `w-full min-w-0` lets the track govern: the column fills its track,
        // and the track is what either fits the frame or scrolls inside it.
        "flex w-full min-w-0 flex-col overflow-hidden rounded-2xl border transition-all duration-300",
        "bg-card dark:bg-card/90",
        isOver && isLegalTarget && cn("ring-2 shadow-lg", ringGlow),
        isOver && !isLegalTarget && "ring-2 ring-destructive/60 shadow-lg shadow-destructive/20",
        !isOver && "border-border/50 shadow-sm dark:border-border/30",
      )}
    >
      {/* Neon top indicator */}
      <div className="relative">
        <div className={cn("h-1 w-full", visual.dot)} />
        <div className={cn("absolute inset-x-0 top-0 h-2 blur-md opacity-50", visual.dot)} />
      </div>

      {/* Header — gradient glass */}
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
              {totalCount !== undefined ? toPersianDigits(totalCount) : "—"}
            </span>
          </div>
        </div>
        <p className="truncate text-[11px] text-muted-foreground/70">{visual.description}</p>
      </div>

      {/* Cards — scroll INSIDE the column rather than letting the column grow.
          `min-h-0` is load-bearing: a flex child defaults to `min-height: auto`
          and would refuse to shrink, defeating the frame's fixed height (the
          orders column carries the identical class for the same reason). */}
      <div className={BOARD_COLUMN_BODY_CLASS}>
        {loading && tickets.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-primary/60" />
          </div>
        ) : tickets.length === 0 ? (
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
          <TicketCardList
            tickets={tickets}
            onOpen={onOpen}
            onAdvance={onAdvance}
            busyTicketId={busyTicketId}
          />
        )}

        {hasMore && (
          <button
            type="button"
            disabled={loading}
            onClick={() => onLoadMore(status)}
            className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-white/10 py-2 text-[11px] font-medium text-muted-foreground/60 transition-all hover:border-primary/30 hover:text-primary dark:border-white/5"
          >
            {loading && <Loader2 className="h-3 w-3 animate-spin" />}
            نمایش بیشتر
          </button>
        )}
      </div>
    </div>
  );
}

export const TicketBoardColumn = memo(TicketBoardColumnInner);
