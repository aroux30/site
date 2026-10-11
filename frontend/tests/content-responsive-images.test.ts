/**
 * Pins the two live bugs in `withResponsiveImages`, both found in a real
 * import (2026-10-08):
 *
 * 1. **`sizes` was appended AFTER the tag.** For an `<img … />` the result was
 *    `<img … /> sizes="…"` — outside the element — and the browser rendered
 *    the attribute as literal text under the image. The check below asserts
 *    `sizes` lives INSIDE the `<img>` tag, which is what the leak violated.
 * 2. **404 candidates.** The uploader only writes a derivative when the
 *    original is larger than the target, so a 500px image has `-medium`
 *    (300w) but no `-medium_large`/`-large`. The first version listed all
 *    three unconditionally; the browser picked 768w (per `sizes`) and showed
 *    a broken image. Now the original is the largest candidate and no srcset
 *    is emitted at all without a `width` attribute to bound it.
 *
 * Negative test for each: re-append `sizes` after the closing `>` (test 1
 * goes red); drop the `width < imgWidth` filter (test 2 lists 768w and goes
 * red).
 */
import { describe, expect, it } from "vitest";

import { withResponsiveImages } from "@/lib/content-responsive-images";

/** The `<img …>` element out of a rewritten fragment, or null. */
function imgTagOf(html: string): string | null {
  return html.match(/<img\b[^>]*>/i)?.[0] ?? null;
}

describe("withResponsiveImages", () => {
  it("keeps `sizes` inside the img tag for a self-closing image", () => {
    const out = withResponsiveImages(
      '<figure><img src="/uploads/media/abc.jpg" width="800" alt="x" /></figure>',
    );
    const tag = imgTagOf(out);
    expect(tag).not.toBeNull();
    expect(tag).toContain('sizes="');
    // The bug: the string `sizes="…"` appeared between `/>` and `</figure>`.
    expect(out).not.toMatch(/\/>\s*sizes=/);
    expect(out.replace(tag ?? "", "")).not.toContain("sizes=");
  });

  it("never lists a candidate wider than the image", () => {
    const out = withResponsiveImages(
      '<img src="/uploads/media/abc.jpg" width="500" height="400" alt="x" />',
    );
    // 300w (medium) exists for a 500px image; 768w and 1024w do not.
    expect(out).toContain("abc-medium.jpg 300w");
    expect(out).not.toContain("medium_large");
    expect(out).not.toContain("-large.");
    // The original closes the candidate list at its own width.
    expect(out).toContain("abc.jpg 500w");
  });

  it("emits no srcset when the tag carries no width", () => {
    // Without a width there is no honest way to know which derivatives the
    // uploader wrote; guessing is the 404 bug.
    const out = withResponsiveImages('<img src="/uploads/media/abc.jpg" alt="x" />');
    expect(out).not.toContain("srcset");
    expect(out).toBe('<img src="/uploads/media/abc.jpg" alt="x" />');
  });

  it("leaves an existing srcset and remote hosts alone", () => {
    const existing = '<img src="/uploads/media/abc.jpg" srcset="/x.jpg 300w" width="800" />';
    expect(withResponsiveImages(existing)).toBe(existing);
    const remote = '<img src="https://cdn.example.com/a.jpg" width="800" alt="r" />';
    expect(withResponsiveImages(remote)).toBe(remote);
  });
});
