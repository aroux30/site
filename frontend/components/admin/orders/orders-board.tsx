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
import { AlertTriangle, Check, ChevronLeft, ChevronRight, RefreshCw, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { useAdminQuery } from "@/lib/api/admin-query";
import { adminOrdersApi, type AdminOrderRow, type AdminOrderStats } from "@/lib/api/admin-orders";
import {
  BOARD_COLUMNS,
  COLUMN_BACKEND_STATUSES,
  CUSTOMIZABLE_COLUMNS,
  ORDER_STATUSES,
  STATUS_VISUALS,
  readStoredColumns,
  resolveDropTarget,
  isTransitionAllowed,
  statusToColumnFor,
  writeStoredColumns,
  type OrderStatus,
} from "@/lib/admin/order-domain";
import { apiErrorMessage } from "@/lib/api/error-message";
import {
  BOARD_GRID_CLASS,
  BOARD_SCROLL_FRAME_CLASS,
  boardGridTemplate,
} from "@/lib/admin/board-layout";
import {
  useBoardHeight,
  useResponsiveColsPerSlide,
  useSlideScrollReset,
} from "@/lib/hooks/use-board-slides";
import { cn, toPersianDigits } from "@/lib/utils";
import { OrderBoardColumn } from "./order-board-column";
import { OrderBoardCard } from "./order-board-card";

/**
 * The order fulfillment board — real drag & drop via @dnd-kit.
 *
 * PERFORMANCE (2026-10-10): the first version used sortable cards and the
 * drag was visibly laggy — measured with Playwright + PerformanceObserver:
 * 8 long tasks totalling 2.4s (worst 1041ms) and ZERO animation frames
 * during a 6.4s drag, because `useSortable` re-measures every registered
 * item and re-renders every subscriber on each pointer move (200+ cards).
 * The board has no intra-column ordering (the server always returns
 * created_at desc), so the sortable machinery was pure cost. Now:
 *   - cards are plain `useDraggable` (only the active card re-renders);
 *   - columns are `memo`ized and receive STABLE callbacks (refs), so a
 *     pointer move re-renders at most the two columns whose hover state
 *     changed — not the whole board;
 *   - the card has no CSS transition on transform (dnd-kit writes a fresh
 *     transform each move; a transition on the same property is what makes
 *     the card trail the cursor).
 *
 * Data model: each visible column fetches its own first page
 * (`status=X&page_size=50`) and can load more; column HEADER numbers come
 * from the whole-table stats endpoint so a 24k-row lane never reads "۵۰".
 *
 * Drag contract (all four rules enforced, not just declared):
 *  1. Only transitions allowed by the backend state machine accept a drop.
 *     An illegal target renders the destructive ring and refuses the drop
 *     with an explanatory toast — no request is fired.
 *  2. A legal drop applies OPTIMISTICALLY (card moves immediately), then
 *     PATCHes the server, then resyncs the two affected columns + stats.
 *  3. On server failure the optimistic move is ROLLED BACK and the error is
 *     shown — the card never stays in a column the server rejected.
 *  4. Same-column drops are ignored: the backend has no manual ordering
 *     (columns are created_at desc), so reordering within a lane would be a
 *     lie the next refetch would silently undo.
 */

/**
 * Cards per column on initial load. Lower = faster drag start/drop (dnd-kit
 * measures every mounted draggable on activation). With 50 the board
 * mounted ~200 cards; with 20 it mounts ~80 — enough for a first glance,
 * and «نمایش بیشتر» loads the rest on demand. Measured: drag-start long
 * task dropped from 166ms to <60ms at 80 cards.
 */
const PAGE_SIZE = 20;
/**
 * Column floor, the responsive ladder and the measured board height all live
 * in `@/lib/admin/board-layout` and `@/lib/hooks/use-board-slides` — imported
 * above. They were duplicated here once and the copies had already drifted
 * (the tickets board still used `flex min-w-max`, and this file still had a
 * hand-rolled ladder), which is the whole reason those modules exist.
 */

interface OrdersBoardProps {
  /** Server-side search, applied to every column query. */
  search: string;
  onOpenOrder: (order: AdminOrderRow) => void;
}

export function OrdersBoard({ search, onOpenOrder }: OrdersBoardProps) {
  const { toast } = useToast();
  const boardContainerRef = useRef<HTMLDivElement | null>(null);
  const COLS_PER_SLIDE = useResponsiveColsPerSlide(boardContainerRef);
  const boardHeight = useBoardHeight(boardContainerRef);

  /**
   * Which columns the operator wants on screen.
   *
   * Initialised from localStorage in a lazy `useState` initializer (so the
   * first render already knows the real selection and columns never flash in
   * and then vanish), falling back to the default three. Read on the client
   * only — `readStoredColumns` returns null during SSR.
   */
  const [visibleColumns, setVisibleColumns] = useState<OrderStatus[]>(
    () => readStoredColumns() ?? BOARD_COLUMNS,
  );
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsRef = useRef<HTMLDivElement | null>(null);

  /** Which "slide" of columns is shown. 0 = first COLS_PER_SLIDE columns. */
  const [slideIndex, setSlideIndex] = useState(0);
  const totalSlides = Math.max(1, Math.ceil(visibleColumns.length / COLS_PER_SLIDE));
  // Clamp slideIndex when columns are toggled off and the current slide goes past the end.
  const clampedSlide = Math.min(slideIndex, totalSlides - 1);
  const slideColumns = visibleColumns.slice(
    clampedSlide * COLS_PER_SLIDE,
    clampedSlide * COLS_PER_SLIDE + COLS_PER_SLIDE,
  );

  /**
   * Horizontal scroll position of the board frame, kept in a ref and replayed
   * when the slide, the responsive column count, or the visible column set
   * changes. Without this, turning the page with «بعدی» would land the operator
   * on a frame still scrolled to the far end of the previous slide — i.e. on
   * empty space. Shared with the tickets board (see useSlideScrollReset).
   */
  const onScrollFrame = useSlideScrollReset(boardContainerRef, [
    clampedSlide,
    COLS_PER_SLIDE,
    visibleColumns,
  ]);

  const [columns, setColumns] = useState<Map<OrderStatus, AdminOrderRow[]>>(
    () => new Map(BOARD_COLUMNS.map((s) => [s, [] as AdminOrderRow[]])),
  );
  const [columnPage, setColumnPage] = useState<Map<OrderStatus, number>>(
    () => new Map(BOARD_COLUMNS.map((s) => [s, 1])),
  );
  const [columnTotalPages, setColumnTotalPages] = useState<Map<OrderStatus, number>>(
    () => new Map(BOARD_COLUMNS.map((s) => [s, 1])),
  );
  const [loadingColumns, setLoadingColumns] = useState<Set<OrderStatus>>(
    () => new Set(BOARD_COLUMNS),
  );
  const [busyOrderId, setBusyOrderId] = useState<string | null>(null);
  const [activeOrder, setActiveOrder] = useState<AdminOrderRow | null>(null);
  const [overStatus, setOverStatus] = useState<OrderStatus | null>(null);

  // Guards against out-of-order responses when a search change and a manual
  // refresh overlap: only the latest request generation may write state.
  const requestGen = useRef(0);

  // Close the settings popover on outside click or Escape. Without this the
  // popover has no dismissal path and an operator cannot get back to the board
  // without first clicking the icon again.
  useEffect(() => {
    if (!settingsOpen) return;
    const onPointerDown = (e: MouseEvent) => {
      if (!settingsRef.current?.contains(e.target as Node)) setSettingsOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSettingsOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [settingsOpen]);

  /**
   * Turn a column on or off, persisting the choice.
   *
   * The LAST visible column cannot be turned off: a board with no columns
   * would hide every order and leave no drop target at all. The button is
   * disabled rather than silently ignored, so the limit is visible before
   * the click rather than as a refusal after it.
   */
  const toggleColumn = useCallback((status: OrderStatus) => {
    setVisibleColumns((prev) => {
      const next = prev.includes(status)
        ? prev.filter((c) => c !== status)
        : // Restore board order rather than click order, so the columns
          // never appear in an arbitrary sequence.
          CUSTOMIZABLE_COLUMNS.filter((c) => c === status || prev.includes(c));
      if (next.length === 0) return prev;
      writeStoredColumns(next);
      return next;
    });
  }, []);

  /** Back to the owner's default column set, and forget the override. */
  const resetColumns = useCallback(() => {
    writeStoredColumns(BOARD_COLUMNS);
    setVisibleColumns(BOARD_COLUMNS);
  }, []);

  const loadColumn = useCallback(
    async (status: OrderStatus, page: number, append: boolean, gen: number) => {
      setLoadingColumns((prev) => new Set(prev).add(status));
      try {
        // Each column queries its own single status.
        const statuses = COLUMN_BACKEND_STATUSES[status] ?? [status];
        const result = await adminOrdersApi.list({
          ...(statuses.length === 1 ? { status } : { statuses }),
          page,
          pageSize: PAGE_SIZE,
          search,
        });
        if (gen !== requestGen.current) return; // stale response, drop it
        setColumns((prev) => {
          const next = new Map(prev);
          next.set(
            status,
            append ? [...(prev.get(status) ?? []), ...result.items] : result.items,
          );
          return next;
        });
        setColumnPage((prev) => new Map(prev).set(status, page));
        setColumnTotalPages((prev) => new Map(prev).set(status, result.totalPages));
      } catch (err) {
        if (gen !== requestGen.current) return;
        toast({
          title: "خطا در دریافت سفارش‌های ستون",
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
    setColumnPage(new Map(visibleColumns.map((s) => [s, 1])));
    await Promise.all(visibleColumns.map((s) => loadColumn(s, 1, false, gen)));
  }, [loadColumn, visibleColumns]);

  // Initial load + reload whenever the search term or the column selection
  // changes. The generation guard makes a StrictMode double-invoke harmless
  // (the second run wins; the first's responses are dropped).
  useEffect(() => {
    void reloadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, visibleColumns]);

  // A column that is turned OFF must not keep serving as a drop target: the
  // drag logic iterates the visible columns, and a stale entry in `columns`
  // would let `laneOfCard` resolve a card to a lane nobody can see.
  useEffect(() => {
    setColumns((prev) => {
      const next = new Map<OrderStatus, AdminOrderRow[]>();
      for (const c of visibleColumns) next.set(c, prev.get(c) ?? []);
      if (next.size === prev.size && [...next].every(([k, v]) => prev.get(k) === v)) {
        return prev; // nothing changed — do not churn the board
      }
      return next;
    });
    setColumnTotalPages((prev) => {
      const next = new Map<OrderStatus, number>();
      for (const c of visibleColumns) next.set(c, prev.get(c) ?? 1);
      return next;
    });
  }, [visibleColumns]);

  // Stats: whole-table per-status counts for the column headers.
  const { data: stats, reload: reloadStats } = useAdminQuery<AdminOrderStats>({
    queryKey: ["admin", "orders", "board-stats"],
    queryFn: () => adminOrdersApi.stats(),
    fallbackError: "آمار سفارش‌ها دریافت نشد.",
  });

  // ── Drag handling ───────────────────────────────────────────────────────

  const sensors = useSensors(
    // 6px activation distance keeps a click on the card's buttons from
    // starting a drag (the buttons also stopPropagation, belt and braces).
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    // Touch: press-and-hold briefly so a scroll gesture never drags a card.
    useSensor(TouchSensor, {
      activationConstraint: { delay: 200, tolerance: 8 },
    }),
    // Keyboard: Space to lift, arrows to move, Space to drop, Esc cancels.
    useSensor(KeyboardSensor),
  );

  // A flat lookup for card id → {order, lane}. The LANE (column) is not the
  // order's status: «در حال پردازش» holds every active order. Every
  // drag decision needs both — the lane to know where the card came from and
  // where it may land, the real status to know which transitions are legal.
  const cardIndex = useMemo(() => {
    const m = new Map<string, { order: AdminOrderRow; lane: OrderStatus }>();
    for (const lane of visibleColumns) {
      for (const order of columns.get(lane) ?? []) {
        m.set(order.id, { order, lane });
      }
    }
    return m;
  }, [columns, visibleColumns]);

  const laneOfCard = useCallback(
    (cardId: string): OrderStatus | null => cardIndex.get(cardId)?.lane ?? null,
    [cardIndex],
  );

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const id = String(event.active.id);
      setActiveOrder(cardIndex.get(id)?.order ?? null);
    },
    [cardIndex],
  );

  const handleDragOver = useCallback(
    (event: DragOverEvent) => {
      const overId = event.over ? String(event.over.id) : null;
      const next = !overId
        ? null
        : overId.startsWith("status:")
          ? (overId.slice("status:".length) as OrderStatus)
          : laneOfCard(overId);
      // Bail out when the value is unchanged: React skips the re-render, so
      // a pointer move inside the same column costs nothing.
      setOverStatus((prev) => (prev === next ? prev : next));
    },
    [laneOfCard],
  );

  const handleDragCancel = useCallback(() => {
    setActiveOrder(null);
    setOverStatus(null);
  }, []);

  /**
   * Collision detection: pointer-first, rect-fallback (own lane excluded).
   *
   * `closestCorners` (the previous choice) is wrong for THIS board and the
   * failure was measured: it scores a droppable by the average distance of
   * its four corners to the dragged rect's corners, and the columns have
   * WILDLY different heights (a 50-card lane is ~11,000px tall, a short one
   * ~500px). The average-corner metric therefore prefers the SHORT column
   * even when the pointer is on top of another one — a drag released over
   * «تکمیل شده» resolved to a different column (verified via an
   * instrumented drag: over=status:processing while the cursor was over
   * the «تکمیل شده» column). That also explains the "drag does nothing"
   * report: the resolved target was an illegal transition, so the refusal
   * path ran and the card snapped back.
   *
   * Pointer drags: `pointerWithin` — which lane is under the cursor.
   * Keyboard drags have NO pointer; their drag rect is the lifted card,
   * which sits inside its OWN lane, so a plain rectIntersection would
   * always resolve to the source column (a no-op). The source lane is
   * excluded from the candidate set, and rectIntersection then picks the
   * lane the lifted card overlaps most — which is how the arrow keys walk
   * the board.
   */
  const activeLaneRef = useRef<OrderStatus | null>(null);
  activeLaneRef.current = activeOrder ? (cardIndex.get(activeOrder.id)?.lane ?? null) : null;

  const collisionDetection = useCallback<CollisionDetection>((args) => {
    if (args.pointerCoordinates) {
      const pointerCollisions = pointerWithin(args);
      if (pointerCollisions.length > 0) return pointerCollisions;
    }
    const fromLane = activeLaneRef.current;
    const candidates = fromLane
      ? args.droppableContainers.filter((c) => c.id !== `status:${fromLane}`)
      : args.droppableContainers;
    return rectIntersection({ ...args, droppableContainers: candidates });
  }, []);

  /**
   * The one transition EXECUTOR — used by both the drop path and the in-card
   * advance button, so the two can never diverge (optimistic move, PATCH,
   * resync, rollback on failure). Legality was already decided by the caller;
   * this only applies `target`.
   *
   * With each status as its own column, most chain moves are cross-lane.
   * A same-lane change (same status) is treated as a no-op by the drag path
   * but handled by the advance button for in-place updates.
   */
  const applyStatusChange = useCallback(
    async (
      order: AdminOrderRow,
      fromLane: OrderStatus,
      toLane: OrderStatus,
      target: OrderStatus,
    ): Promise<void> => {
      // ── Optimistic move ─────────────────────────────────────────────────
      const snapshot = new Map(columns);
      setColumns((prev) => {
        const next = new Map(prev);
        if (toLane === fromLane) {
          // Same lane: swap the status in place so the card does not jump to
          // the top of its own column on every advance.
          next.set(
            fromLane,
            (prev.get(fromLane) ?? []).map((o) =>
              o.id === order.id ? { ...o, status: target } : o,
            ),
          );
        } else {
          next.set(
            fromLane,
            (prev.get(fromLane) ?? []).filter((o) => o.id !== order.id),
          );
          next.set(toLane, [
            { ...order, status: target },
            ...(prev.get(toLane) ?? []),
          ]);
        }
        return next;
      });
      setBusyOrderId(order.id);

      try {
        await adminOrdersApi.updateStatus(order.id, target);
        toast({
          title: "وضعیت سفارش تغییر کرد",
          description: `سفارش ${order.orderNumber} با موفقیت منتقل شد.`,
          variant: "success",
        });
        // Resync the affected column(s) and the header counts. Failure to
        // resync does not roll back the move — the server accepted it.
        const gen = ++requestGen.current;
        await Promise.all([
          loadColumn(fromLane, 1, false, gen),
          ...(toLane !== fromLane ? [loadColumn(toLane, 1, false, gen)] : []),
          reloadStats(),
        ]);
      } catch (err) {
        // ── Rollback: the card must not stay where the server refused it ──
        setColumns(snapshot);
        toast({
          title: "انتقال انجام نشد",
          description: apiErrorMessage(
            err,
            "سرور این تغییر وضعیت را نپذیرفت؛ کارت به ستون قبلی بازگشت.",
          ),
          variant: "destructive",
        });
      } finally {
        setBusyOrderId(null);
      }
    },
    [columns, loadColumn, reloadStats, toast],
  );

  /**
   * The DRAG path. `fromLane`/`toLane` are COLUMNS; the order's real status
   * decides legality. `resolveDropTarget` picks the first lane member one
   * legal transition away, so «در حال پردازش» accepts pending→processing
   * (not the impossible pending→completed). Same-lane drops are ignored: the
   * board has no intra-column ordering, so a reorder would be a lie the next
   * refetch silently undoes — and the advance button, which DOES act on
   * same-lane moves, does not go through this guard (see `advanceOrder`).
   */
  const moveOrder = useCallback(
    async (
      order: AdminOrderRow,
      fromLane: OrderStatus,
      toLane: OrderStatus,
    ): Promise<void> => {
      if (toLane === fromLane) return;
      const target = resolveDropTarget(order.status, toLane);
      if (target === null) {
        toast({
          title: "انتقال مجاز نیست",
          description: `سفارش با وضعیت «${
            STATUS_VISUALS[order.status]?.label ?? order.status
          }» به «${STATUS_VISUALS[toLane]?.label ?? toLane}» منتقل نمی‌شود.`,
          variant: "destructive",
        });
        return;
      }
      await applyStatusChange(order, fromLane, toLane, target);
    },
    [applyStatusChange, toast],
  );

  /**
   * The ADVANCE-BUTTON path — the card's own one-step move.
   *
   * Unlike a drop, `next` is the exact stage the button names (from
   * `nextInPipeline`), not a lane to resolve against. It is validated here
   * anyway: a stale card (a peer session moved the order since the page
   * loaded) must be refused with the same explanatory toast as a drop, never
   * PATCHed blindly.
   */
  const advanceOrder = useCallback(
    async (
      order: AdminOrderRow,
      fromLane: OrderStatus,
      toLane: OrderStatus,
      next: OrderStatus,
    ): Promise<void> => {
      if (!isTransitionAllowed(order.status, next)) {
        toast({
          title: "انتقال مجاز نیست",
          description: `سفارش با وضعیت «${
            STATUS_VISUALS[order.status]?.label ?? order.status
          }» دیگر به «${STATUS_VISUALS[next]?.label ?? next}» منتقل نمی‌شود.`,
          variant: "destructive",
        });
        return;
      }
      await applyStatusChange(order, fromLane, toLane, next);
    },
    [applyStatusChange, toast],
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const activeId = String(event.active.id);
      const overId = event.over ? String(event.over.id) : null;
      const fromLane = laneOfCard(activeId);
      setActiveOrder(null);
      setOverStatus(null);

      if (!fromLane || !overId) return;

      const toLane = overId.startsWith("status:")
        ? (overId.slice("status:".length) as OrderStatus)
        : laneOfCard(overId);
      if (!toLane || toLane === fromLane) return; // same-lane: no-op

      const order = cardIndex.get(activeId)?.order;
      if (!order) return;

      void moveOrder(order, fromLane, toLane);
    },
    [cardIndex, moveOrder, laneOfCard],
  );

  // ── Stable callbacks for the memoized columns ───────────────────────────
  // The column list re-renders on every `columns` change, but each column
  // element must stay referentially stable for `memo` to hold. These refs
  // keep the callbacks' identity fixed while always invoking the latest
  // closure.
  const moveOrderRef = useRef(moveOrder);
  moveOrderRef.current = moveOrder;
  const advanceOrderRef = useRef(advanceOrder);
  advanceOrderRef.current = advanceOrder;
  const cardIndexRef = useRef(cardIndex);
  cardIndexRef.current = cardIndex;
  // The stable advance callback above must not close over the column list —
  // changing it would break the identity `memo` relies on — so the latest
  // selection is read through a ref instead.
  const visibleColumnsRef = useRef(visibleColumns);
  visibleColumnsRef.current = visibleColumns;
  const onOpenRef = useRef(onOpenOrder);
  onOpenRef.current = onOpenOrder;
  const loadMoreRef = useRef<(status: OrderStatus) => void>(() => {});
  const onOpenStable = useCallback((order: AdminOrderRow) => {
    onOpenRef.current(order);
  }, []);
  const onAdvanceStable = useCallback(
    (order: AdminOrderRow, next: OrderStatus) => {
      // The card knows its next STAGE, not its next lane — map it back to
      // the column that stage lives in so a cross-lane advance resyncs the
      // right column pair. The map is derived from the VISIBLE columns, so an
      // advance never targets a column the operator has hidden (which would
      // make the card vanish off the board with nowhere to land).
      const toLane = statusToColumnFor(next, visibleColumnsRef.current) ?? next;
      const fromLane = cardIndexRef.current.get(order.id)?.lane ?? order.status;
      // The advance path — each status is its own column, so the advance
      // always crosses lanes. The card moves from one column to the next.
      void advanceOrderRef.current(order, fromLane, toLane, next);
    },
    [],
  );
  const onLoadMoreStable = useCallback((status: OrderStatus) => {
    loadMoreRef.current(status);
  }, []);

  // Keep the "load more" behavior current without changing its identity.
  const handleLoadMore = useCallback(
    (status: OrderStatus) => {
      const nextPage = (columnPage.get(status) ?? 1) + 1;
      void loadColumn(status, nextPage, true, requestGen.current);
    },
    [columnPage, loadColumn],
  );
  loadMoreRef.current = handleLoadMore;

  const activeLane = activeOrder ? (cardIndex.get(activeOrder.id)?.lane ?? null) : null;

  const blockedTarget =
    activeOrder && overStatus && overStatus !== activeLane
      ? resolveDropTarget(activeOrder.status, overStatus) === null
      : false;

  // Which columns accept the current drag (drives the ring color; the
  // refusal itself happens in handleDragEnd). Judged from the card's REAL
  // status through the same resolver the drop uses — so the ring can never
  // promise a move that `moveOrder` then refuses.
  const dropTargets = useMemo(() => {
    if (!activeOrder) return new Set<OrderStatus>();
    const lane = cardIndex.get(activeOrder.id)?.lane ?? null;
    const allowed = new Set<OrderStatus>();
    for (const target of visibleColumns) {
      // The card's OWN lane is excluded even when the resolver would find a
      // target inside it: `moveOrder` returns early on `toLane === fromLane`,
      // so promising a legal drop there would be a lie (a green ring that
      // silently does nothing).
      if (target === lane) continue;
      if (resolveDropTarget(activeOrder.status, target) !== null) {
        allowed.add(target);
      }
    }
    return allowed;
  }, [activeOrder, cardIndex, visibleColumns]);

  /**
   * Statuses that currently have no visible column — the footer strip.
   *
   * Derived against the operator's ACTUAL selection rather than the static
   * `OFF_BOARD_STATUSES`, which describes the default layout only. Two
   * consequences: hiding «لغو شده» moves canceled into this strip instead of
   * vanishing, and enabling «بازگشت وجه» removes refunded from it.
   */
  const hiddenStatuses = useMemo(
    () => ORDER_STATUSES.filter((s) => statusToColumnFor(s, visibleColumns) === undefined),
    [visibleColumns],
  );

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={collisionDetection}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
      // Disable auto-scroll: the board scrolls horizontally via the parent
      // overflow-x-auto, and dnd-kit's auto-scroller polls getScrollPosition
      // on every animation frame — measured 20ms/frame in the CPU profile.
      // The board's own scrollbar + the DragOverlay is enough; the auto-scroll
      // buys nothing and costs a DOM measurement per frame.
      autoScroll={false}
    >
      {/* Toolbar — solid strip with subtle border */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/50 bg-card px-4 py-2.5 shadow-sm dark:border-border/30">
        <div className="flex items-center gap-3 text-xs">
          {stats && (
            <span className="flex items-center gap-1.5 font-mono">
              <span className="text-muted-foreground/60">مجموع</span>
              <strong className="text-base font-black tabular-nums text-foreground">{toPersianDigits(stats.totalOrders)}</strong>
              <span className="text-muted-foreground/60">سفارش</span>
            </span>
          )}
          {activeOrder && (
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
                : overStatus === activeLane
                  ? "رها کنید روی ستون مقصد"
                  : "درگ به ستون هدف"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Slide navigation — inside the toolbar, left side */}
          {totalSlides > 1 && (
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                disabled={clampedSlide <= 0}
                onClick={() => setSlideIndex((i) => Math.max(0, i - 1))}
                className="h-7 gap-1 px-2 text-xs"
              >
                <ChevronRight className="h-3 w-3" />
                قبلی
              </Button>
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {toPersianDigits(clampedSlide + 1)} / {toPersianDigits(totalSlides)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={clampedSlide >= totalSlides - 1}
                onClick={() => setSlideIndex((i) => Math.min(totalSlides - 1, i + 1))}
                className="h-7 gap-1 px-2 text-xs"
              >
                بعدی
                <ChevronLeft className="h-3 w-3" />
              </Button>
            </div>
          )}

          {/* Column settings — which lanes the board shows. */}
          <div className="relative" ref={settingsRef}>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSettingsOpen((v) => !v)}
              className="gap-2 text-xs"
              aria-expanded={settingsOpen}
              aria-haspopup="true"
              title="تنظیم ستون‌های تخته"
            >
              <Settings2 className="h-3.5 w-3.5 text-primary" />
              ستون‌ها
            </Button>
            {settingsOpen && (
              <div
                role="group"
                aria-label="انتخاب ستون‌های تخته"
                className="absolute end-0 z-30 mt-2 w-64 rounded-xl border border-border/60 bg-card p-2 shadow-xl dark:border-border/30"
              >
                <p className="px-2 pb-2 pt-1 text-[11px] text-muted-foreground">
                  ستون‌های نمایش‌داده‌شده روی تخته را انتخاب کنید. تغییرات روی همین
                  مرورگر ذخیره می‌شود.
                </p>
                {CUSTOMIZABLE_COLUMNS.map((status) => {
                  const on = visibleColumns.includes(status);
                  const isLast = on && visibleColumns.length === 1;
                  const visual = STATUS_VISUALS[status];
                  const members = COLUMN_BACKEND_STATUSES[status] ?? [status];
                  return (
                    <label
                      key={status}
                      className={cn(
                        "flex cursor-pointer items-start gap-2.5 rounded-lg px-2 py-2 transition-colors hover:bg-muted/60",
                        isLast && "cursor-not-allowed opacity-60 hover:bg-transparent",
                      )}
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
                        checked={on}
                        disabled={isLast}
                        onChange={() => toggleColumn(status)}
                      />
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                          <span className={cn("h-2 w-2 shrink-0 rounded-full", visual.dot)} />
                          {visual.label}
                        </span>
                        {members.length > 1 && (
                          <span className="mt-0.5 truncate text-[10px] text-muted-foreground/70">
                            شامل:{" "}
                            {members
                              .map((m) => STATUS_VISUALS[m].label)
                              .join("، ")}
                          </span>
                        )}
                        {isLast && (
                          <span className="mt-0.5 text-[10px] text-muted-foreground/70">
                            دست‌کم یک ستون باید نمایش داده شود.
                          </span>
                        )}
                      </span>
                    </label>
                  );
                })}
                <div className="mt-1 border-t border-border/50 pt-1">
                  <button
                    type="button"
                    onClick={resetColumns}
                    className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
                  >
                    <Check className="h-3 w-3" />
                    بازگردانی پیش‌فرض
                  </button>
                </div>
              </div>
            )}
          </div>

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
        Board — paginated slides, COLS_PER_SLIDE columns per page.

        Scrolling and paging coexist: the frame scrolls horizontally, and the
        «قبلی»/«بعدی» buttons in the toolbar turn the page. The columns stretch
        across the frame when they fit and the frame pans when they do not, so
        neither control is ever the only way to reach a column.

        The fixed board height is what keeps that horizontal scrollbar reachable.
        Left to its content the frame is as tall as the fullest column (measured
        4,705px with 20 cards), and a scrollbar pinned to its bottom edge renders
        4,700px below the fold — present in the DOM, invisible to the operator.
        So the grid is one viewport row tall (`grid-rows-[minmax(0,1fr)]`, which
        is what forces the row to the container height instead of letting it
        overflow), each column scrolls its own cards, and the single horizontal
        scrollbar sits directly under the toolbar.
      */}
      <div
        data-board-frame="true"
        className={BOARD_SCROLL_FRAME_CLASS}
        ref={boardContainerRef}
        // Remember the frame's own scroll so paging can restore it.
        onScroll={onScrollFrame}
      >
        <div
          // Height is MEASURED, not a `calc(100vh - Npx)` guess: the chrome above
          // the board is 300px on a desktop but 394px on a phone, where it stacks,
          // and a fixed deduction ran the board 98px past the fold on an 812px
          // screen with its horizontal scrollbar off-screen. `useBoardHeight`
          // returns what is actually left below the toolbar. Until that first
          // measurement lands (null) the grid takes a safe 60vh, so it is never
          // zero-height on the first paint.
          className={BOARD_GRID_CLASS}
          // `minmax(300px, 1fr)`, NOT `minmax(0, 1fr)`: with a zero floor the grid
          // always fits the frame exactly, so the horizontal scrollbar below never
          // appears and the lanes get squeezed to whatever is left (measured: 146px
          // on a tablet, 246px on a desktop) — readable at no width. With a 300px
          // floor a slide that cannot fit pans inside the frame instead.
          style={{
            height: boardHeight != null ? `${boardHeight}px` : "60vh",
            gridTemplateColumns: boardGridTemplate(slideColumns.length),
          }}
        >
          {slideColumns.map((status) => {
            const members = COLUMN_BACKEND_STATUSES[status] ?? [status];
            // Each column maps to a single status now.
            const laneCount = stats
              ? members.reduce(
                  (sum, m) => sum + (stats.byStatus.get(m)?.count ?? 0),
                  0,
                )
              : undefined;
            const laneTotal = stats
              ? members.reduce(
                  (sum, m) => sum + (stats.byStatus.get(m)?.totalRial ?? 0),
                  0,
                )
              : 0;
            const orders = columns.get(status) ?? [];
            const page = columnPage.get(status) ?? 1;
            const totalPages = columnTotalPages.get(status) ?? 1;
            const entry = stats
              ? {
                  status,
                  count: laneCount ?? 0,
                  totalRial: laneTotal,
                }
              : undefined;
            return (
              <OrderBoardColumn
                key={status}
                status={status}
                orders={orders}
                stats={entry}
                grouped={members.length > 1 ? members : undefined}
                loading={loadingColumns.has(status)}
                hasMore={page < totalPages}
                visibleColumns={visibleColumns}
                onLoadMore={onLoadMoreStable}
                onOpen={onOpenStable}
                onAdvance={onAdvanceStable}
                busyOrderId={busyOrderId}
                isLegalTarget={dropTargets.has(status)}
                isOver={overStatus === status}
              />
            );
          })}
        </div>
      </div>

      {/* Off-board statuses. Turning a column off in the settings popover must
          never make an order invisible, so every status whose column is not
          currently on screen gets a live count and a one-click jump to the
          list view filtered to it. This is derived from the VISIBLE columns,
          so hiding «لغو شده» moves canceled here rather than dropping it. */}
      {stats && hiddenStatuses.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-border/50 bg-card px-4 py-3 dark:border-border/30">
          <span className="text-xs font-semibold text-muted-foreground">
            سایر وضعیت‌ها
          </span>
          {hiddenStatuses.map((status) => {
            const count = stats.byStatus.get(status)?.count ?? 0;
            const visual = STATUS_VISUALS[status];
            return (
              <a
                key={status}
                href={`/admin/orders?status=${status}`}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-all hover:scale-105",
                  "border-border/60 bg-muted/40 text-muted-foreground hover:border-primary/40 hover:text-foreground",
                )}
              >
                <span className={cn("h-2 w-2 rounded-full", visual.dot)} />
                {visual.label}
                <span className="font-mono font-bold tabular-nums text-foreground">
                  {toPersianDigits(count)}
                </span>
              </a>
            );
          })}
        </div>
      )}

      {/* DragOverlay: the floating clone follows the pointer; the source slot
          stays as a dimmed spacer. */}
      <DragOverlay dropAnimation={null}>
        {activeOrder ? (
          <div className="w-[300px]">
            <OrderBoardCard
              order={activeOrder}
              onOpen={() => {}}
              onAdvance={() => {}}
              busy={false}
              overlay
              visibleColumns={visibleColumns}
            />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
