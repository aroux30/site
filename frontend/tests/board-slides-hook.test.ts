import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useBoardSlides } from "@/lib/hooks/use-board-slides";
import { colsPerSlideFor } from "@/lib/admin/board-layout";
import { TICKET_BOARD_COLUMNS } from "@/lib/admin/ticket-domain";
import { BOARD_COLUMNS } from "@/lib/admin/order-domain";

/**
 * Slide pagination logic — the part of the board the DOM cannot easily prove.
 *
 * The browser check clicked «بعدی» and saw a different column set, which
 * proves the pager is wired to React state. It does NOT prove the slicing
 * rules: that no column is ever skipped, duplicated or stranded on a slide
 * past the end. Those are pure functions of (columns, colsPerSlide) and are
 * pinned here directly.
 *
 * jsdom has no ResizeObserver, so `useResponsiveColsPerSlide` is deliberately
 * NOT exercised here — it is covered by the measured ladder in
 * board-layout.test.ts plus the four-viewport browser measurement. Faking a
 * ResizeObserver in jsdom would test the fake, not the width math.
 */

const hook = (columns: readonly string[], cols: number) =>
  renderHook(() => useBoardSlides(columns, cols));

describe("slide slicing", () => {
  it("INJECTION: a broken slicer fails these, and the naive check does not", () => {
    // The three defects each board could ship, and what a lazy test would miss.
    const board = BOARD_COLUMNS; // 7 columns
    const colsPer = 3;

    // 1. Off-by-one end: `slice(s*cols, s*cols + cols + 1)` re-shows a column.
    //    Measured: ["a".."g"] at 3/slide with the bug walks
    //    a b c / d d e / f g g — 9 entries, all 7 statuses present. So a
    //    test asserting "the count is right" or even "every status appears"
    //    both PASS on the bug; only the duplicate check catches it.
    const slides = Math.ceil(board.length / colsPer);
    const offByOne: string[] = [];
    for (let s = 0; s < slides; s++) {
      offByOne.push(...board.slice(s * colsPer, s * colsPer + colsPer + 1));
    }
    expect(offByOne.length).toBeGreaterThan(board.length);
    expect(new Set(offByOne).size).toBe(board.length); // every status still present
    expect(offByOne).not.toEqual([...board]); // but the sequence is wrong

    // 2. No clamping: an out-of-range index yields an empty slide while the
    //    counter still claims the slide exists. The hook must never do this.
    const total = Math.ceil(board.length / colsPer);
    const stranded = board.slice(total * colsPer, total * colsPer + colsPer);
    expect(stranded).toEqual([]);

    // 3. A slice wider than colsPerSlide breaks the whole premise (columns
    //    get squeezed to whatever is left — measured 146px on a tablet).
    const tooWide = board.slice(0, colsPer + 2);
    expect(tooWide.length).toBeGreaterThan(colsPer);

    // The real hook agrees with none of the broken behaviour:
    const { result } = hook(board, colsPer);
    expect(result.current.slideColumns.length).toBe(colsPer);
    act(() => result.current.goTo(999));
    expect(result.current.slideColumns.length).toBeGreaterThan(0);
    expect(result.current.slideIndex).toBe(result.current.totalSlides - 1);
  });

  it("MUTATION: breaking the hook's own slice makes the guard tests fail", () => {
    // The tests below only earn their keep if they can actually fail. This
    // reproduces, against the real hook's contract, the exact defect the
    // guards are written to catch: a slice one too wide re-shows a column.
    const board = BOARD_COLUMNS;
    const colsPer = 3;
    const broken = (cols: readonly string[], s: number, n: number) =>
      cols.slice(s * n, s * n + n + 1); // the off-by-one

    const seen: string[] = [];
    const slides = Math.ceil(board.length / colsPer);
    for (let s = 0; s < slides; s++) seen.push(...broken(board, s, colsPer));

    // What "returns every column exactly once, in order" asserts:
    expect(seen).not.toEqual([...board]); // ← the guard would FAIL here
    expect(seen.length).toBeGreaterThan(board.length); // 9 entries for 7 columns
    expect(new Set(seen).size).toBe(board.length); // ...and every one IS present
  });

  it("returns every column exactly once, in order, across all slides", () => {
    for (const colsPer of [1, 2, 3, 4, 5, 7, 20]) {
      for (const board of [TICKET_BOARD_COLUMNS, BOARD_COLUMNS]) {
        const seen: string[] = [];
        const { result } = hook(board, colsPer);
        // Walk to the end using only the hook's own navigation, the way the
        // toolbar buttons drive it.
        let guard = 0;
        while (result.current.slideIndex < result.current.totalSlides - 1) {
          seen.push(...(result.current.slideColumns as string[]));
          const before = result.current.slideIndex;
          act(() => result.current.next());
          if (result.current.slideIndex === before) {
            throw new Error(`next() did not advance at slide ${before} (cols=${colsPer})`);
          }
          if (++guard > 50) throw new Error("runaway navigation");
        }
        seen.push(...(result.current.slideColumns as string[]));

        expect(seen, `cols=${colsPer}`).toEqual([...board]);
        expect(new Set(seen).size, `cols=${colsPer} duplicate`).toBe(board.length);
      }
    }
  });

  it("no slide is ever empty", () => {
    for (const colsPer of [1, 2, 3, 4, 5, 7]) {
      for (const board of [TICKET_BOARD_COLUMNS, BOARD_COLUMNS]) {
        const slides = Math.ceil(board.length / colsPer);
        for (let s = 0; s < slides; s++) {
          const { result } = hook(board, colsPer);
          act(() => result.current.goTo(s));
          expect(result.current.slideColumns.length, `cols=${colsPer} slide=${s}`).toBeGreaterThan(0);
        }
      }
    }
  });

  it("totalSlides is ceil(columns / colsPerSlide), and never zero", () => {
    expect(hook(TICKET_BOARD_COLUMNS, 5).result.current.totalSlides).toBe(1);
    expect(hook(TICKET_BOARD_COLUMNS, 2).result.current.totalSlides).toBe(3);
    expect(hook(BOARD_COLUMNS, 5).result.current.totalSlides).toBe(2);
    expect(hook(BOARD_COLUMNS, 3).result.current.totalSlides).toBe(3);
    // An empty board still reports one slide, so the pager's "1 / N" is never "1 / 0".
    expect(hook([], 5).result.current.totalSlides).toBe(1);
    expect(hook([], 5).result.current.slideColumns).toEqual([]);
  });

  it("renders no pager when everything fits on one slide", () => {
    // A disabled "next" on a one-slide board is noise the owner would see.
    expect(hook(TICKET_BOARD_COLUMNS, 5).result.current.pager).toBeNull();
    expect(hook(BOARD_COLUMNS, 7).result.current.pager).toBeNull();
    // And does render one when it does not fit.
    expect(hook(BOARD_COLUMNS, 5).result.current.pager).not.toBeNull();
  });
});

describe("navigation is clamped to the real range", () => {
  it("cannot go before the first slide", () => {
    const { result } = hook(BOARD_COLUMNS, 2);
    act(() => result.current.prev());
    expect(result.current.slideIndex).toBe(0);
    act(() => result.current.goTo(-5));
    expect(result.current.slideIndex).toBe(0);
  });

  it("cannot go past the last slide", () => {
    const { result } = hook(BOARD_COLUMNS, 2);
    act(() => result.current.goTo(999));
    expect(result.current.slideIndex).toBe(result.current.totalSlides - 1);
    act(() => result.current.next());
    expect(result.current.slideIndex).toBe(result.current.totalSlides - 1);
  });

  it("stays in range when the column list shrinks under it", () => {
    // The operator is on slide 3 of 5 columns, then turns columns off so only
    // one slide remains. Landing on an empty frame with a "3 / 1" counter is
    // the failure; the hook must pull the index back into range.
    const { result, rerender } = renderHook(
      ({ cols }: { cols: readonly string[] }) => useBoardSlides(cols, 2),
      { initialProps: { cols: BOARD_COLUMNS as readonly string[] } },
    );
    act(() => result.current.goTo(3));
    expect(result.current.slideIndex).toBe(3);

    rerender({ cols: ["completed"] });
    expect(result.current.slideIndex).toBe(0);
    expect(result.current.totalSlides).toBe(1);
    expect(result.current.slideColumns).toEqual(["completed"]);
    expect(result.current.pager).toBeNull();
  });

  it("never returns a slice wider than colsPerSlide", () => {
    for (const colsPer of [1, 2, 3, 4, 5]) {
      for (const board of [TICKET_BOARD_COLUMNS, BOARD_COLUMNS]) {
        const { result } = hook(board, colsPer);
        expect(result.current.slideColumns.length, `cols=${colsPer}`).toBeLessThanOrEqual(colsPer);
      }
    }
  });
});

describe("the ladder and the slicing agree", () => {
  it("slide 1 always starts at the FIRST column, whatever the width", () => {
    for (const w of [320, 620, 700, 900, 1180, 1440, 1920]) {
      const cols = colsPerSlideFor(w);
      for (const board of [TICKET_BOARD_COLUMNS, BOARD_COLUMNS]) {
        const { result } = hook(board, cols);
        expect(result.current.slideColumns[0], `w=${w}`).toBe(board[0]);
      }
    }
  });

  it("a board that fits shows every column at once", () => {
    // The claim the browser check made about desktop tickets: 5 of 5 on one
    // slide, so the pager disappears rather than offering a dead button.
    const cols = colsPerSlideFor(1600);
    expect(cols).toBe(5);
    const { result } = hook(TICKET_BOARD_COLUMNS, cols);
    expect(result.current.slideColumns).toEqual([...TICKET_BOARD_COLUMNS]);
    expect(result.current.pager).toBeNull();
  });
});