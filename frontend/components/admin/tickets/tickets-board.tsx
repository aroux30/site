"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  pointerWithin,
  rectIntersection,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
  type DragOverEvent,
} from "@dnd-kit/core";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { useAdminQuery } from "@/lib/api/admin-query";
import {
  fetchAdminTickets,
  fetchAdminTicketStats,
  updateAdminTicketStatus,
  type TicketItem,
  type TicketStats,
} from "@/lib/api/tickets";
import {
  BOARD_FRAME_CLASS,
  boardGridTemplate,
  boardHeightStyle,
} from "@/lib/admin/board-layout";
import {
  useBoardHeight,
  useBoardSlides,
  useResponsiveColsPerSlide,
  useSlideScrollReset,
} from "@/lib/hooks/use-board-slides";
import {
  TICKET_BOARD_COLUMNS,
  isTicketTransitionAllowed,
  type TicketStatus,
} from "@/lib/admin/ticket-domain";
import { apiErrorMessage } from "@/lib/api/error-message";
import { cn, toPersianDigits } from "@/lib/utils";
import { TicketBoardColumn } from "./ticket-board-column";
import { TicketBoardCard } from "./ticket-board-card";

/**
 * The support-ticket board — real drag & drop, same architecture as the
 * orders board (which was measured and tuned; see orders-board.tsx):
 * pointer-first collision detection (columns have wildly different
 * heights, so closestCorners picks the wrong lane), plain draggables (no
 * sortable — no intra-column ordering exists), memoized columns with
 * stable callbacks, optimistic move + rollback.
 *
 * Differences from orders, on purpose:
 *  - Status changes go through `PATCH /admin/tickets/{id}` which accepts
 *    ANY status (no backend state machine); the transition table in
 *    ticket-domain.ts is a UI guard rail.
 *  - The board pages by column with skip/limit (the endpoint is offset
 *    based, not page based).
 */

/**
 * Cards per column on initial load. Same reasoning as the orders board:
 * fewer mounted draggables = faster drag start (dnd-kit measures every one).
 */
const PAGE_SIZE = 20;

interface TicketsBoardProps {
  /** Server-side search, applied to every column query. */
  search: string;
  onOpenTicket: (ticket: TicketItem) => void;
}

export function TicketsBoard({ search, onOpenTicket }: TicketsBoardProps) {
  const { toast } = useToast();
  const boardContainerRef = useRef<HTMLDivElement | null>(null);
  const colsPerSlide = useResponsiveColsPerSlide(boardContainerRef);
  const { slideColumns, slideIndex, totalSlides, pager } = useBoardSlides(
    TICKET_BOARD_COLUMNS,
    colsPerSlide,
  );
  // MEASURED height, not calc(100vh - 300px): the chrome above the board is
  // 300px on a desktop but 394px on a phone, where those rows stack, and the
  // fixed subtraction ran the board past the fold and pushed its own
  // horizontal scrollbar off the bottom (measured, by session 1003).
  const boardHeight = useBoardHeight(boardContainerRef);
  // Replaying the frame's scroll on every slide change: without it, «بعدی»
  // pressed while scrolled to the end of one slide lands the operator on a
  // frame still scrolled there — empty space past their new columns.
  const onScrollFrame = useSlideScrollReset(boardContainerRef, [slideIndex, colsPerSlide]);

  const [columns, setColumns] = useState<Map<TicketStatus, TicketItem[]>>(
    () => new Map(TICKET_BOARD_COLUMNS.map((s) => [s, [] as TicketItem[]])),
  );
  const [columnOffset, setColumnOffset] = useState<Map<TicketStatus, number>>(
    () => new Map(TICKET_BOARD_COLUMNS.map((s) => [s, 0])),
  );
  const [columnHasMore, setColumnHasMore] = useState<Map<TicketStatus, boolean>>(
    () => new Map(TICKET_BOARD_COLUMNS.map((s) => [s, false])),
  );
  const [loadingColumns, setLoadingColumns] = useState<Set<TicketStatus>>(
    () => new Set(TICKET_BOARD_COLUMNS),
  );
  const [busyTicketId, setBusyTicketId] = useState<string | null>(null);
  const [activeTicket, setActiveTicket] = useState<TicketItem | null>(null);
  const [overStatus, setOverStatus] = useState<TicketStatus | null>(null);

  const requestGen = useRef(0);

  // Mirror for loadColumn's hasMore computation without making it a dep.
  const columnHasMoreRef = useRef(columnHasMore);
  columnHasMoreRef.current = columnHasMore;

  const loadColumn = useCallback(
    async (status: TicketStatus, offset: number, append: boolean, gen: number) => {
      setLoadingColumns((prev) => new Set(prev).add(status));
      try {
        const result = await fetchAdminTickets({
          status,
          skip: offset,
          limit: PAGE_SIZE,
          search: search || undefined,
        });
        if (gen !== requestGen.current) return;
        setColumns((prev) => {
          const next = new Map(prev);
          next.set(status, append ? [...(prev.get(status) ?? []), ...result.items] : result.items);
          return next;
        });
        setColumnOffset((prev) => new Map(prev).set(status, offset));
        setColumnHasMore(
          new Map(columnHasMoreRef.current).set(status, offset + result.items.length < result.total),
        );
      } catch (err) {
        if (gen !== requestGen.current) return;
        toast({
          title: "خطا در دریافت تیکت‌های ستون",
          description: apiErrorMessage(err, "ارتباط با سرور برقرار نشد."),
          variant: "destructive",
        });
      } finally {
        if (gen === requestGen.current) {
          setLoadingColumns((prev) => {
            const next = new Set(prev);
            next.delete(status);
            return next;
          });
        }
      }
    },
    [search, toast],
  );

  const reloadAll = useCallback(async () => {
    const gen = ++requestGen.current;
    setColumnOffset(new Map(TICKET_BOARD_COLUMNS.map((s) => [s, 0])));
    await Promise.all(TICKET_BOARD_COLUMNS.map((s) => loadColumn(s, 0, false, gen)));
  }, [loadColumn]);

  useEffect(() => {
    void reloadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const { data: stats, reload: reloadStats } = useAdminQuery<TicketStats>({
    queryKey: ["admin", "tickets", "board-stats"],
    queryFn: () => fetchAdminTicketStats(),
    fallbackError: "آمار تیکت‌ها دریافت نشد.",
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
    useSensor(KeyboardSensor),
  );

  const cardIndex = useMemo(() => {
    const m = new Map<string, { ticket: TicketItem; status: TicketStatus }>();
    for (const status of TICKET_BOARD_COLUMNS) {
      for (const ticket of columns.get(status) ?? []) {
        m.set(ticket.id, { ticket, status });
      }
    }
    return m;
  }, [columns]);

  const statusOfCard = useCallback(
    (cardId: string): TicketStatus | null => cardIndex.get(cardId)?.status ?? null,
    [cardIndex],
  );

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const id = String(event.active.id);
      setActiveTicket(cardIndex.get(id)?.ticket ?? null);
    },
    [cardIndex],
  );

  const handleDragOver = useCallback(
    (event: DragOverEvent) => {
      const overId = event.over ? String(event.over.id) : null;
      const next = !overId
        ? null
        : overId.startsWith("tstatus:")
          ? (overId.slice("tstatus:".length) as TicketStatus)
          : statusOfCard(overId);
      setOverStatus((prev) => (prev === next ? prev : next));
    },
    [statusOfCard],
  );

  const handleDragCancel = useCallback(() => {
    setActiveTicket(null);
    setOverStatus(null);
  }, []);

  // See orders-board.tsx for the measured reason this is pointer-first.
  const activeStatusRef = useRef<TicketStatus | null>(null);
  activeStatusRef.current = activeTicket?.status ?? null;

  const collisionDetection = useCallback<CollisionDetection>((args) => {
    if (args.pointerCoordinates) {
      const pointerCollisions = pointerWithin(args);
      if (pointerCollisions.length > 0) return pointerCollisions;
    }
    const fromStatus = activeStatusRef.current;
    const candidates = fromStatus
      ? args.droppableContainers.filter((c) => c.id !== `tstatus:${fromStatus}`)
      : args.droppableContainers;
    return rectIntersection({ ...args, droppableContainers: candidates });
  }, []);

  const moveTicket = useCallback(
    async (ticket: TicketItem, fromStatus: TicketStatus, toStatus: TicketStatus) => {
      if (toStatus === fromStatus) return;
      if (!isTicketTransitionAllowed(fromStatus, toStatus)) {
        toast({
          title: "انتقال مجاز نیست",
          description: "این تغییر وضعیت در گردش‌کار پشتیبانی مجاز نیست.",
          variant: "destructive",
        });
        return;
      }

      const snapshot = new Map(columns);
      setColumns((prev) => {
        const next = new Map(prev);
        next.set(fromStatus, (prev.get(fromStatus) ?? []).filter((t) => t.id !== ticket.id));
        next.set(toStatus, [{ ...ticket, status: toStatus }, ...(prev.get(toStatus) ?? [])]);
        return next;
      });
      setBusyTicketId(ticket.id);

      try {
        await updateAdminTicketStatus(ticket.id, toStatus);
        toast({
          title: "وضعیت تیکت تغییر کرد",
          description: `تیکت ${ticket.ticket_number} با موفقیت منتقل شد.`,
          variant: "success",
        });
        const gen = ++requestGen.current;
        await Promise.all([
          loadColumn(fromStatus, 0, false, gen),
          loadColumn(toStatus, 0, false, gen),
          reloadStats(),
        ]);
      } catch (err) {
        setColumns(snapshot);
        toast({
          title: "انتقال انجام نشد",
          description: apiErrorMessage(err, "سرور این تغییر وضعیت را نپذیرفت؛ کارت برگشت."),
          variant: "destructive",
        });
      } finally {
        setBusyTicketId(null);
      }
    },
    [columns, loadColumn, reloadStats, toast],
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const activeId = String(event.active.id);
      const overId = event.over ? String(event.over.id) : null;
      const fromStatus = statusOfCard(activeId);
      setActiveTicket(null);
      setOverStatus(null);

      if (!fromStatus || !overId) return;

      const toStatus = overId.startsWith("tstatus:")
        ? (overId.slice("tstatus:".length) as TicketStatus)
        : statusOfCard(overId);

      if (!toStatus || toStatus === fromStatus) return;

      const ticket = (columns.get(fromStatus) ?? []).find((t) => t.id === activeId);
      if (!ticket) return;

      void moveTicket(ticket, fromStatus, toStatus);
    },
    [columns, moveTicket, statusOfCard],
  );

  // Stable callbacks for the memoized columns (refs carry the latest
  // closures — see orders-board.tsx for the pattern and why).
  const moveTicketRef = useRef(moveTicket);
  moveTicketRef.current = moveTicket;
  const onOpenRef = useRef(onOpenTicket);
  onOpenRef.current = onOpenTicket;
  const loadMoreRef = useRef<(status: TicketStatus) => void>(() => {});
  const onOpenStable = useCallback((ticket: TicketItem) => {
    onOpenRef.current(ticket);
  }, []);
  const onAdvanceStable = useCallback((ticket: TicketItem, next: TicketStatus) => {
    void moveTicketRef.current(ticket, ticket.status, next);
  }, []);
  const onLoadMoreStable = useCallback((status: TicketStatus) => {
    loadMoreRef.current(status);
  }, []);

  const handleLoadMore = useCallback(
    (status: TicketStatus) => {
      const nextOffset = (columnOffset.get(status) ?? 0) + PAGE_SIZE;
      void loadColumn(status, nextOffset, true, requestGen.current);
    },
    [columnOffset, loadColumn],
  );
  loadMoreRef.current = handleLoadMore;

  const blockedTarget =
    activeTicket && overStatus && overStatus !== activeTicket.status
      ? !isTicketTransitionAllowed(activeTicket.status, overStatus)
      : false;

  const dropTargets = new Set<TicketStatus>();
  if (activeTicket) {
    for (const target of TICKET_BOARD_COLUMNS) {
      if (target !== activeTicket.status && isTicketTransitionAllowed(activeTicket.status, target)) {
        dropTargets.add(target);
      }
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={collisionDetection}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
      autoScroll={false}
    >
      {/* Toolbar — solid strip, matching the orders board's chrome so the two
          pages read as one system */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/50 bg-card px-4 py-2.5 shadow-sm dark:border-border/30">
        <div className="flex items-center gap-3 text-xs">
          {stats && (
            <span className="flex items-center gap-1.5 font-mono">
              <span className="text-muted-foreground/60">مجموع</span>
              <strong className="text-base font-black tabular-nums text-foreground">
                {toPersianDigits(stats.totalTickets)}
              </strong>
              <span className="text-muted-foreground/60">تیکت</span>
            </span>
          )}
          {stats && stats.urgentOpen > 0 && (
            <span className="flex items-center gap-1 rounded-full border border-rose-400/40 bg-rose-500/10 px-3 py-1 text-[11px] font-bold text-rose-700 dark:text-rose-300">
              <AlertTriangle className="h-3.5 w-3.5" />
              {toPersianDigits(stats.urgentOpen)} تیکت فوری باز
            </span>
          )}
          {stats && stats.unassigned > 0 && (
            <span className="rounded-full border border-border bg-muted/50 px-3 py-1 text-[11px] font-medium">
              {toPersianDigits(stats.unassigned)} بدون کارشناس
            </span>
          )}
          {activeTicket && (
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-bold backdrop-blur-sm transition-all",
                blockedTarget
                  ? "border-destructive/50 bg-destructive/10 text-destructive shadow-sm shadow-destructive/20 animate-pulse"
                  : "border-primary/50 bg-primary/10 text-primary shadow-sm shadow-primary/20",
              )}
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              {blockedTarget
                ? "ممنوع — مسیر غیرمجاز"
                : overStatus === activeTicket.status
                  ? "رها کنید روی ستون مقصد"
                  : "درگ به ستون هدف"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Slide navigation — inside the toolbar, left side (same position as
              the orders board's pager; see useBoardSlides). */}
          {pager}
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void reloadAll();
              void reloadStats();
            }}
            className="gap-2 text-xs"
          >
            <RefreshCw className="h-3.5 w-3.5 text-primary" />
            بروزرسانی
          </Button>
        </div>
      </div>

      {/*
        Board — paginated slides, `colsPerSlide` columns per slide.

        No horizontal scrollbar: the grid's zero-floored tracks
        (`minmax(0, 1fr)`) plus `w-full` on each column make the slide exactly
        as wide as the frame, so «قبلی»/«بعدی» in the toolbar are the only way
        to turn the slide — which is what the owner asked for. The old
        `flex min-w-max` inside `overflow-x-auto` put the last column past the
        left edge instead.

        The frame is pinned to the viewport and each column scrolls its own
        cards, so every column's header and drop target stay on screen for the
        whole drag (left to its content this frame measured 4,705px tall).
      */}
      <div className="pb-6" ref={boardContainerRef}>
        <div
          className={BOARD_FRAME_CLASS}
          style={{
            gridTemplateColumns: boardGridTemplate(slideColumns.length),
            ...boardHeightStyle(boardHeight),
          }}
          onScroll={onScrollFrame}
        >
          {slideColumns.map((status) => (
            <TicketBoardColumn
              key={status}
              status={status}
              tickets={columns.get(status) ?? []}
              totalCount={stats?.byStatus.get(status)}
              loading={loadingColumns.has(status)}
              hasMore={columnHasMore.get(status) ?? false}
              onLoadMore={onLoadMoreStable}
              onOpen={onOpenStable}
              onAdvance={onAdvanceStable}
              busyTicketId={busyTicketId}
              isLegalTarget={dropTargets.has(status)}
              isOver={overStatus === status}
            />
          ))}
        </div>
      </div>

      <DragOverlay dropAnimation={null}>
        {activeTicket ? (
          <div className="w-[300px]">
            <TicketBoardCard
              ticket={activeTicket}
              onOpen={() => {}}
              onAdvance={() => {}}
              busy={false}
              overlay
            />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
