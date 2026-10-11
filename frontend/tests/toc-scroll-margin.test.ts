/**
 * Pins the sticky-header scroll offset for ToC anchors.
 *
 * Live bug (owner report, 2026-10-08): clicking a ToC entry scrolled the
 * heading to viewport top:0 — exactly where the 98–179px sticky header sits
 * — so the title the reader clicked for was hidden behind the header and the
 * page appeared to land "in the middle" of the section. Worse on wide
 * screens: the header is taller (179px at 1024px), so the offset has to be
 * responsive.
 *
 * The fix is `scroll-margin-top` on `[id]` headings, declared per breakpoint
 * in globals.css. This test reads the stylesheet and asserts the contract:
 * every breakpoint that changes the header height also changes the offset.
 *
 * Negative test: delete the 1024px block and the assertion fails (that is
 * the breakpoint where the header jumps from 114px to 179px).
 */
import { readFileSync } from "fs";
import { resolve } from "path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(__dirname, "../app/globals.css"), "utf-8");

/** Extract the scroll-margin-top value inside the media block for `min` px.
 *
 *  Slice-based rather than `new RegExp`: building the pattern from a string
 *  needs double-escaping, and the first version of this helper silently
 *  matched nothing because of it — a vacuous test that would have passed on
 *  any stylesheet. The literal index search cannot drift that way.
 */
function marginAt(minPx: number | null): string | null {
  let region = css;
  if (minPx !== null) {
    const marker = `@media (min-width: ${minPx}px)`;
    const start = css.indexOf(marker);
    if (start === -1) return null;
    // The block runs until the next @media (or EOF) — the region between
    // them is this breakpoint's overrides.
    const next = css.indexOf("@media", start + marker.length);
    region = next === -1 ? css.slice(start) : css.slice(start, next);
  } else {
    // `noUncheckedIndexedAccess` — [0] is `string | undefined`.
    region = css.split("@media")[0] ?? "";
  }
  const m = region.match(/scroll-margin-top:\s*([\d.]+rem)/);
  return m ? (m[1] ?? null) : null;
}

describe("ToC scroll offset clears the sticky header", () => {
  it("declares a base offset for mobile", () => {
    expect(marginAt(null)).not.toBeNull();
  });

  it("adjusts at every breakpoint where the header height changes", () => {
    // Measured header heights: 98 / 110 / 114 / 179 / 159.
    // The 1024 breakpoint is the trap: lg shows the nav row and the header
    // jumps +65px; a missing offset there is the original bug.
    for (const bp of [640, 768, 1024, 1280]) {
      expect(marginAt(bp), `missing scroll-margin-top at ${bp}px`).not.toBeNull();
    }
  });

  it("offsets stay above their measured header height", () => {
    const toPx = (rem: string) => parseFloat(rem) * 16;
    const pairs: [number | null, number][] = [
      [null, 98],
      [640, 110],
      [768, 114],
      [1024, 179],
      [1280, 159],
    ];
    for (const [bp, headerPx] of pairs) {
      const value = marginAt(bp);
      expect(value).not.toBeNull();
      expect(toPx(value as string)).toBeGreaterThan(headerPx);
    }
  });

  it("targets every heading level the ToC can link to", () => {
    expect(css).toMatch(/h2\[id\]/);
    expect(css).toMatch(/h3\[id\]/);
  });
});
