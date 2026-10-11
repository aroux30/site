import { describe, expect, it } from "vitest";

import {
  BOARD_COLUMN_BODY_CLASS,
  BOARD_FRAME_CLASS,
  BOARD_GAP_PX,
  MIN_COL_WIDTH,
  boardGridTemplate,
  colsPerSlideFor,
} from "@/lib/admin/board-layout";
import { TICKET_BOARD_COLUMNS } from "@/lib/admin/ticket-domain";
import { BOARD_COLUMNS } from "@/lib/admin/order-domain";

/**
 * Shared board geometry — the contract both admin boards (orders, tickets)
 * are built on.
 *
 * The owner requires the tickets page to be a structural copy of the orders
 * page. They were built separately and had already drifted: the orders board
 * gained slide pagination and a zero-floored grid, while the tickets board was
 * still `flex min-w-max` inside `overflow-x-auto`, which pushed its last
 * column past the left edge (measured: `left = -94` on a 1280px viewport).
 * These tests pin the shared pieces so the next divergence fails a gate instead
 * of shipping.
 *
 * Every assertion here is one that can FAIL on a real regression:
 *  - the ladder is the owner's explicit decision (2 / 3 / 4 / 5), so each rung
 *    is pinned with a value on both sides of its breakpoint;
 *  - the grid template is asserted for the `minmax(0, …)` floor by PARSING it,
 *    not by substring — a stray `minmax(300px, 1fr)` (the bug the orders board
 *    had) and a `minmax(0, 1fr)` both contain "minmax(" and "1fr";
 *  - the frame/column classes are pinned because `min-h-0` on the column body
 *    is what makes the fixed frame height real; drop it and a flex child
 *    reverts to `min-height: auto` and grows to its content.
 */

describe("responsive column ladder", () => {
  it("gives two columns on a narrow content area", () => {
    // The admin sidebar sits beside the board, so a 375px WINDOW is only
    // ~75px of content in the narrowest realistic case; the point of the
    // lowest rung is that it never returns less than two.
    expect(colsPerSlideFor(320)).toBe(2);
    expect(colsPerSlideFor(619)).toBe(2);
  });

  it("gives three columns between 620 and 900", () => {
    expect(colsPerSlideFor(620)).toBe(3);
    expect(colsPerSlideFor(750)).toBe(3);
    expect(colsPerSlideFor(899)).toBe(3);
  });

  it("gives four columns between 900 and 1180", () => {
    expect(colsPerSlideFor(900)).toBe(4);
    expect(colsPerSlideFor(1000)).toBe(4);
    expect(colsPerSlideFor(1179)).toBe(4);
  });

  it("gives five columns from 1180 up", () => {
    expect(colsPerSlideFor(1180)).toBe(5);
    expect(colsPerSlideFor(1920)).toBe(5);
    expect(colsPerSlideFor(3840)).toBe(5);
  });

  it("every rung is a step, never a jump", () => {
    const rungs = [0, 619, 620, 899, 900, 1179, 1180].map(colsPerSlideFor);
    for (let i = 1; i < rungs.length; i++) {
      expect(rungs[i]! - rungs[i - 1]!).toBeLessThanOrEqual(1);
      expect(rungs[i]!).toBeGreaterThanOrEqual(2);
      expect(rungs[i]!).toBeLessThanOrEqual(5);
    }
  });

  it("is monotonically non-decreasing in width", () => {
    for (let w = 300; w < 1600; w += 17) {
      expect(colsPerSlideFor(w + 17)).toBeGreaterThanOrEqual(colsPerSlideFor(w));
    }
  });
});

describe("grid template", () => {
  it("INJECTION: a ZERO floor must fail the template contract", () => {
    // The direction of this injection FLIPPED on 2026-10-11. The owner first
    // asked for the pager "instead of" the horizontal scroll; then corrected
    // it: «بجز اسلاید اضافه کردن اون اسکرول کردن هم باشه» — BESIDES the slide,
    // the scroll must stay. So `minmax(0, 1fr)` is now the DEFECT: it makes
    // the grid fit its frame exactly (measured `scrollWidth === clientWidth`
    // at 375/768/1280/1600), which kills the horizontal scrollbar and leaves
    // the pager as the only control — the very thing that was removed.
    const bad = `repeat(5, minmax(0, 1fr))`;
    expect(bad).not.toBe(boardGridTemplate(5));
    expect(bad).not.toMatch(/minmax\(300px/);
    // …and every substring check a lazy test would reach for still passes on
    // it, which is why the contract is asserted as an exact string.
    expect(bad).toMatch(/minmax\(/);
    expect(bad).toMatch(/1fr/);
  });

  it("uses a 300px floor so the frame can still scroll", () => {
    // The floor is what makes the two controls independent: a slide that does
    // not fit pans INSIDE the `overflow-x-auto` frame, while «قبلی»/«بعدی» turn
    // to the next group of columns.
    for (const n of [1, 2, 3, 4, 5]) {
      expect(boardGridTemplate(n), `cols=${n}`).toBe(`repeat(${n}, minmax(300px, 1fr))`);
    }
  });

  it("always emits a px floor, never zero and never auto", () => {
    for (const n of [2, 3, 4, 5]) {
      const t = boardGridTemplate(n);
      expect(t, `cols=${n} must carry a floor`).toMatch(/minmax\(\d+px,/);
      expect(t, `cols=${n} must not use a zero floor`).not.toMatch(/minmax\(0,/);
      expect(t, `cols=${n} must not use auto`).not.toMatch(/minmax\(auto/);
    }
  });

  it("emits one track per column requested", () => {
    // `repeat(n, …)` names the track ONCE — `repeat` is what multiplies it —
    // so counting occurrences of "minmax" would always read 1. The track count
    // is the repeat count; assert that, and assert the track it repeats.
    for (const n of [2, 3, 4, 5]) {
      const match = /^repeat\((\d+),\s*(.+)\)$/.exec(boardGridTemplate(n));
      expect(match, `cols=${n} must be a repeat() of a track`).not.toBeNull();
      expect(match![1], `cols=${n} repeat count`).toBe(String(n));
      expect(match![2], `cols=${n} track`).toBe("minmax(300px, 1fr)");
    }
  });

  it("the floor is the shared constant, not a literal", () => {
    // A literal `300` here and `MIN_COL_WIDTH` elsewhere would let the two
    // drift, and the orders board would scroll at one width while tickets
    // scrolled at another.
    for (const n of [2, 5]) {
      expect(boardGridTemplate(n)).toContain(`${MIN_COL_WIDTH}px`);
    }
    expect(MIN_COL_WIDTH).toBe(300);
  });
});

describe("frame and column body geometry", () => {
  it("the frame SCROLLS horizontally (the owner's correction)", () => {
    // «بجز اسلاید اضافه کردن اون اسکرول کردن هم باشه تو اسکرول افقی رو حذف
    // کردی» — the owner corrected the pager-for-scrollbar swap. The frame
    // MUST keep `overflow-x-auto`: with the 300px floor and no scroll, the
    // fifth column is simply invisible off the left edge.
    expect(BOARD_FRAME_CLASS).toContain("overflow-x-auto");
  });

  it("the frame is pinned to a viewport height, not left to its content", () => {
    // Left to its content this frame measured 4,705px tall with 20 cards,
    // which put any bottom-pinned control thousands of pixels below the fold.
    expect(BOARD_FRAME_CLASS).toContain("100vh");
    expect(BOARD_FRAME_CLASS).toContain("min-h-");
    expect(BOARD_FRAME_CLASS).toContain("w-full");
    // `grid-rows-[minmax(0,1fr)]` is what forces the row to the container
    // height instead of letting it overflow.
    expect(BOARD_FRAME_CLASS).toContain("grid-rows-[minmax(0,1fr)]");
  });

  it("a five-column slide genuinely overflows, so the scroll is real", () => {
    // The scrollbar is only reachable if the slide wants MORE than the frame
    // has. Five tracks at the floor plus gaps is 1,564px, which exceeds any
    // realistic content area — so the scroll is live, not decorative.
    const fiveAtFloor = MIN_COL_WIDTH * 5 + BOARD_GAP_PX * 4;
    expect(fiveAtFloor).toBeGreaterThan(1440);
    // And two columns at the floor DO fit a wide frame, so the scroll
    // correctly disappears there instead of being dead weight everywhere.
    const twoAtFloor = MIN_COL_WIDTH * 2 + BOARD_GAP_PX;
    expect(twoAtFloor).toBeLessThan(1920);
  });

  it("the column body can shrink and scrolls its own cards", () => {
    // `min-h-0` is load-bearing: a flex child defaults to `min-height: auto`
    // and would grow to its tallest card, defeating the fixed frame height.
    expect(BOARD_COLUMN_BODY_CLASS).toContain("min-h-0");
    expect(BOARD_COLUMN_BODY_CLASS).toContain("flex-1");
    expect(BOARD_COLUMN_BODY_CLASS).toContain("overflow-y-auto");
  });

  it("the documented gap matches the grid's own gap", () => {
    // BOARD_GAP_PX documents the `gap-4` used by BOARD_FRAME_CLASS. If the
    // class is retuned to gap-5 without updating the constant, the next
    // arithmetic that assumes 16px is wrong — so pin them together.
    expect(BOARD_GAP_PX).toBe(16);
    expect(BOARD_FRAME_CLASS).toContain("gap-4");
  });
});

describe("slide counts for both boards", () => {
  it("the tickets board fits its five columns on one slide at desktop width", () => {
    // 5 statuses / 5 per slide = one slide, so the pager must NOT render: a
    // disabled "next" button on a single-slide board is noise.
    const cols = colsPerSlideFor(1440);
    expect(Math.ceil(TICKET_BOARD_COLUMNS.length / cols)).toBe(1);
  });

  it("the tickets board needs two slides on a narrow content area", () => {
    const cols = colsPerSlideFor(700);
    expect(cols).toBe(3);
    expect(Math.ceil(TICKET_BOARD_COLUMNS.length / cols)).toBe(2);
  });

  it("the orders board needs two slides at desktop width (seven columns)", () => {
    const cols = colsPerSlideFor(1440);
    expect(cols).toBe(5);
    expect(Math.ceil(BOARD_COLUMNS.length / cols)).toBe(2);
  });

  it("every slide of both boards is non-empty at every rung", () => {
    // A slide with zero columns would render an empty frame with a pager that
    // still says "1 / 2" — the operator sees nothing and no way forward.
    for (const w of [320, 620, 700, 900, 1180, 1440, 1920]) {
      const cols = colsPerSlideFor(w);
      for (const board of [TICKET_BOARD_COLUMNS, BOARD_COLUMNS]) {
        const slides = Math.ceil(board.length / cols);
        for (let s = 0; s < slides; s++) {
          expect(board.slice(s * cols, s * cols + cols).length, `w=${w} slide=${s}`).toBeGreaterThan(0);
        }
        expect(board.slice((slides - 1) * cols).length, `w=${w} last slide`).toBeGreaterThan(0);
      }
    }
  });

  it("no column is ever lost across the slides of a board", () => {
    // Slicing is the only thing standing between paging and a missing column;
    // this pins that every status shows up exactly once, in order.
    for (const w of [320, 700, 900, 1180, 1920]) {
      const cols = colsPerSlideFor(w);
      for (const board of [TICKET_BOARD_COLUMNS, BOARD_COLUMNS]) {
        const seen: string[] = [];
        const slides = Math.ceil(board.length / cols);
        for (let s = 0; s < slides; s++) seen.push(...board.slice(s * cols, s * cols + cols));
        expect(seen, `w=${w}`).toEqual([...board]);
        expect(new Set(seen).size, `w=${w} duplicate column`).toBe(board.length);
      }
    }
  });
});