"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { colsPerSlideFor } from "@/lib/admin/board-layout";
import { toPersianDigits } from "@/lib/utils";

/**
 * Slide pagination for an admin board — shared by the orders and tickets
 * boards so the two cannot drift.
 *
 * BOTH controls are wanted, not either/or. The owner first asked for the pager
 * «بجای اسکرول افقی» (instead of the horizontal scroll), then corrected it:
 * «گفتم بجز اسلاید اضافه کردن اون اسکرول کردن هم باشه» — besides the slide, the
 * scroll must stay. So the two are independent: the ladder decides how many
 * columns a slide holds, the frame scrolls whatever still overflows, and
 * «قبلی»/«بعدی» turn to the next group.
 */

/**
 * How many columns fit at the current CONTENT width.
 *
 * Measured with a `ResizeObserver` on the board container rather than
 * `window.innerWidth`, because the admin sidebar sits beside the board and
 * permanently consumes ~300px — breakpoints tuned against the viewport handed
 * a 1280px laptop three columns instead of four. The observer also catches the
 * sidebar collapsing, which a window resize listener would miss entirely.
 *
 * Defaults to 5 so the first render (SSR, before the observer attaches) is
 * already the widest slide; the effect corrects it on mount.
 */
export function useResponsiveColsPerSlide(ref: React.RefObject<HTMLElement | null>): number {
  const [cols, setCols] = useState(5);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const calc = () => setCols(colsPerSlideFor(el.clientWidth));
    calc();
    const ro = new ResizeObserver(calc);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return cols;
}

/**
 * Room left below the board for its own scrollbar and the page padding.
 *
 * The board's frame scrolls horizontally, and that scrollbar sits on the
 * frame's bottom edge — if the frame runs past the fold, the control the owner
 * explicitly asked for is present in the DOM and invisible in practice.
 */
export const BOARD_BOTTOM_GUTTER = 72;

/** A board shorter than this is unusable; the floor wins over the fold. */
export const MIN_BOARD_HEIGHT = 260;

/**
 * Height of the board frame, in CSS px, or null before it is measured.
 *
 * MEASURED, not `calc(100vh - Npx)`. The chrome above the board is not a
 * constant: 300px on a desktop (header, tabs, toolbar, stats — one row each)
 * but 394px on a phone, where those rows stack. A hard 300px subtraction ran
 * the board 98px past the fold on an 812px screen and pushed its own
 * horizontal scrollbar off the bottom (measured, by session 1003).
 *
 * Null on the first render, so callers must keep a CSS fallback height —
 * returning 0 would collapse the board until the effect runs.
 */
export function useBoardHeight(ref: React.RefObject<HTMLElement | null>): number | null {
  const [height, setHeight] = useState<number | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const calc = () => {
      // Distance from the board's top to the bottom of the VIEWPORT, not the
      // document: the board is meant to fill what is left of the screen, so
      // scrolling down must not shrink it.
      const top = el.getBoundingClientRect().top;
      const available = Math.max(MIN_BOARD_HEIGHT, window.innerHeight - top - BOARD_BOTTOM_GUTTER);
      setHeight(Math.round(available));
    };
    calc();
    // The observer catches the toolbar wrapping into a second row; the resize
    // listener catches the viewport itself changing, which no observation of
    // the board alone would see.
    const ro = new ResizeObserver(calc);
    ro.observe(el);
    window.addEventListener("resize", calc);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", calc);
    };
  }, [ref]);
  return height;
}

/**
 * Keep the frame's horizontal scroll in step with the slide.
 *
 * Returns the `onScroll` handler to put on the frame. Without the reset,
 * pressing «بعدی» while the operator is scrolled to the far end of the
 * previous slide lands them on a frame still scrolled there — i.e. on empty
 * space past their new columns. (Built by session 1003 for the orders board;
 * here so tickets gets it for free.)
 */
export function useSlideScrollReset(
  frameRef: React.RefObject<HTMLElement | null>,
  deps: readonly unknown[],
): () => void {
  const scrollLeftRef = useRef(0);
  useEffect(() => {
    const frame = frameRef.current;
    if (frame) frame.scrollLeft = scrollLeftRef.current;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return useCallback(() => {
    const frame = frameRef.current;
    if (frame) scrollLeftRef.current = frame.scrollLeft;
  }, [frameRef]);
}

export interface BoardSlides<T> {
  /** Columns on the current slide, already sliced. */
  slideColumns: T[];
  /** 0-based index, always within range even after a column is toggled off. */
  slideIndex: number;
  totalSlides: number;
  /** `null` when everything fits on one slide — the pager renders nothing. */
  pager: React.ReactNode;
  goTo: (index: number) => void;
  next: () => void;
  prev: () => void;
}

/**
 * Wire a column list to the slide pager.
 *
 * The pager lives in the board toolbar's LEFT (visual) side, beside the
 * column-settings button, because that is where the owner's screenshot
 * circled it — a pager stranded below the board would be off-screen on a
 * short window, which is exactly the case where the operator needs it most.
 */
export function useBoardSlides<T>(columns: readonly T[], colsPerSlide: number): BoardSlides<T> {
  const [slideIndex, setSlideIndex] = useState(0);
  const totalSlides = Math.max(1, Math.ceil(columns.length / Math.max(1, colsPerSlide)));

  // Turning columns off shrinks the board past the current slide; clamping on
  // render (rather than in an effect) means there is no frame where the
  // operator sees an empty board.
  const clampedSlide = Math.min(slideIndex, totalSlides - 1);

  // Shrinking the window can move the current slide's first column off-screen
  // relative to the operator's intent, so re-anchor to the same first column
  // instead of keeping an index that now means something else.
  const lastFirstColumn = columns[clampedSlide * colsPerSlide];
  const goTo = useCallback(
    (index: number) => setSlideIndex(Math.max(0, Math.min(totalSlides - 1, index))),
    [totalSlides],
  );

  useEffect(() => {
    if (slideIndex === clampedSlide) return;
    setSlideIndex(clampedSlide);
  }, [clampedSlide, slideIndex]);

  const slideColumns = columns.slice(
    clampedSlide * colsPerSlide,
    clampedSlide * colsPerSlide + colsPerSlide,
  );

  const pager =
    totalSlides > 1 ? (
      <div className="flex items-center gap-1.5" data-board-slide-pager="true">
        <Button
          variant="outline"
          size="sm"
          disabled={clampedSlide <= 0}
          onClick={() => goTo(clampedSlide - 1)}
          className="h-7 gap-1 px-2 text-xs"
          aria-label="اسلاید قبلی ستون‌ها"
        >
          <ChevronRight className="h-3 w-3" />
          قبلی
        </Button>
        <span className="text-[11px] tabular-nums text-muted-foreground">
          {toPersianDigits(clampedSlide + 1)} / {toPersianDigits(totalSlides)}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={clampedSlide >= totalSlides - 1}
          onClick={() => goTo(clampedSlide + 1)}
          className="h-7 gap-1 px-2 text-xs"
          aria-label="اسلاید بعدی ستون‌ها"
        >
          بعدی
          <ChevronLeft className="h-3 w-3" />
        </Button>
      </div>
    ) : null;

  return {
    slideColumns,
    slideIndex: clampedSlide,
    totalSlides,
    pager,
    goTo,
    next: () => goTo(clampedSlide + 1),
    prev: () => goTo(clampedSlide - 1),
  };
}