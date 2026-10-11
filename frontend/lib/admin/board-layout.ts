/**
 * Shared board layout — the geometry every admin board (orders, tickets) uses.
 *
 * WHY THIS FILE EXISTS: the orders board and the tickets board are deliberate
 * copies of each other — same slide pagination, same responsive ladder, same
 * grid tracks. They were built separately and had already drifted. Two copies
 * of the same idea WILL drift again, so the geometry lives here once and both
 * boards import it.
 *
 * THE OWNER WANTS BOTH CONTROLS, NOT EITHER/OR. Two instructions in sequence,
 * the second explicitly correcting the first:
 *
 *   01:47 «فقط بجای اسکرول افقی یک دکمه صفحه بعد یا ادامه بزار» — add a pager
 *        INSTEAD of the horizontal scroll.
 *   01:54 «گفتم بجز اسلاید اضافه کردن اون اسکرول کردن هم باشه تو اسکرول افقی رو
 *        حذف کردی» — BESIDES the slide, the scroll must be there too. You
 *        removed the horizontal scroll.
 *
 * So a board frame is `overflow-x-auto` and the columns carry a 300px floor:
 * a slide that does not fit pans INSIDE the frame, and «قبلی»/«بعدی» turn to
 * the next group. Neither control is the only way to reach a column, and the
 * two stay independent — the ladder decides how many columns a slide holds,
 * the frame decides whether that slide still overflows.
 */

/**
 * The column floor, in px.
 *
 * The floor is what makes the two controls independent. With `minmax(0, 1fr)`
 * the grid always fits its frame exactly — `scrollWidth === clientWidth` at
 * every width (measured at 375/768/1280/1600) — so the horizontal scrollbar is
 * dead and the pager becomes the only control, which is precisely what the
 * owner objected to.
 *
 * 300px also keeps a column readable: measured across ten viewport widths, the
 * narrowest column the ladder produces is 207px (content 652px, three columns),
 * against 146px when all seven statuses shared one unpaged slide.
 */
export const MIN_COL_WIDTH = 300;

/** Gap between board columns — must match the grid's `gap-4`. */
export const BOARD_GAP_PX = 16;

/**
 * How many columns one slide holds, from the width of the CONTENT area.
 *
 * Not the viewport: the admin sidebar permanently eats ~300px, so the first
 * breakpoints measured against `window.innerWidth` handed four squeezed lanes
 * to a 1280px laptop. `ResizeObserver` on the board container is also what
 * makes this react to the sidebar collapsing, not just to a window resize.
 *
 * A deliberate LADDER, not "however many fit": two on a narrow screen, then
 * three, four, and five on the widest. Owner decision 2026-10-11.
 *
 *   < 620px → 2 · < 900px → 3 · < 1180px → 4 · ≥ 1180px → 5
 *
 * Verified against the measured content width at ten viewport sizes: the
 * prediction matched reality in 10 of 10.
 */
export function colsPerSlideFor(contentWidth: number): number {
  if (contentWidth < 620) return 2;
  if (contentWidth < 900) return 3;
  if (contentWidth < 1180) return 4;
  return 5;
}

/**
 * The grid template for one slide: N tracks, each at least `MIN_COL_WIDTH`.
 *
 * The `1fr` lets each track GROW past the floor when the frame is wider than
 * the slide needs, so a four-column slide on a wide screen fills it rather than
 * hugging 300px against the right edge.
 */
export function boardGridTemplate(columns: number): string {
  return `repeat(${columns}, minmax(${MIN_COL_WIDTH}px, 1fr))`;
}

/**
 * The board frame: fixed height, horizontally scrollable.
 *
 * `overflow-x-auto` is REQUIRED, not decorative — see the owner's correction
 * at the top of this file. Without it the 300px floor overflows into nothing
 * and the fifth column is simply invisible off the left edge, which is the
 * exact bug this layout exists to fix.
 *
 * This is the ONE-PIECE form (frame and grid are the same element), which the
 * tickets board uses. The orders board needs the two-piece form below because
 * its measured height belongs on the grid while its scrollbar must stay on an
 * element that is not also the grid — but both forms carry the same geometry.
 */
export const BOARD_FRAME_CLASS =
  "grid min-h-[380px] w-full items-stretch gap-4 overflow-x-auto pb-1 " +
  "h-[calc(100vh-300px)] grid-rows-[minmax(0,1fr)]";

/**
 * The OUTER half of the two-piece frame: the scroll container only.
 *
 * The scrollbar belongs here because the measured height is applied to the
 * inner grid; putting both on one element would put the scrollbar at the top
 * of the board instead of under it.
 */
export const BOARD_SCROLL_FRAME_CLASS = "overflow-x-auto pb-1";

/** The INNER half of the two-piece frame: the column grid. */
export const BOARD_GRID_CLASS =
  "grid w-full grid-rows-[minmax(0,1fr)] items-stretch gap-4";

/**
 * The inline style for the board frame: the MEASURED height once known.
 *
 * `h-[calc(100vh-300px)]` on the class is only a first-paint fallback. The
 * chrome above the board is not a constant — 300px on a desktop, 394px on a
 * phone where those rows stack — so the fixed subtraction ran the board 98px
 * past the fold on an 812px screen and pushed its own horizontal scrollbar off
 * the bottom (measured, by session 1003). `useBoardHeight` supplies the real
 * number; this merges it in.
 *
 * Returns `{}` before the first measurement rather than `{height: 0}` — a zero
 * height would collapse the board for one frame.
 */
export function boardHeightStyle(height: number | null): Record<string, string> {
  return height == null ? {} : { height: `${height}px` };
}

/**
 * Class for a board column's card area: fills the remaining height of the
 * column and scrolls internally.
 *
 * `min-h-0` is load-bearing. A flex child defaults to `min-height: auto`,
 * which refuses to shrink below its content — the column would grow to its
 * tallest card's height and the frame's fixed height would be defeated
 * anyway. `min-h-0` lets it actually take the space it is given.
 */
export const BOARD_COLUMN_BODY_CLASS = "flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto p-2.5";