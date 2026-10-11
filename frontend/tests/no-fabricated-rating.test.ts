/**
 * A fabricated rating is a lie told to every customer.
 *
 * The storefront shipped `average_rating || 4.7` in three places: the product
 * header printed "۴.۷ (بر اساس ۰ نظر ثبتشده)" for a product with zero
 * reviews, the reviews tab drew a fake 80%/20% five/four-star distribution,
 * and the compare payload carried the 4.7 forward. The JSON-LD had no rating
 * at all — so the display lied while the structured data stayed silent.
 *
 * This test is a source-scanning gate: the pattern `|| 4.7` (or any numeric
 * literal fallback for a rating) must not reappear in storefront code. It
 * fails on the exact code that shipped, which is what makes it a gate rather
 * than a comment.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const STOREFRONT_ROOTS = [
  path.join(__dirname, "..", "app", "(store)"),
  path.join(__dirname, "..", "components", "store"),
];

function walk(dir: string): string[] {
  const out: string[] = [];
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      out.push(...walk(full));
    } else if (/\.(ts|tsx)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

/** Strip comments — documenting the old bug must not fail the gate. */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("no fabricated ratings in storefront code", () => {
  it("no file falls back to a NON-ZERO rating literal", () => {
    const offenders: string[] = [];
    for (const root of STOREFRONT_ROOTS) {
      for (const file of walk(root)) {
        const code = stripComments(readFileSync(file, "utf8"));
        // A rating-ish identifier followed by || or ?? and a non-zero number.
        // `|| 0` / `?? 0` are the CORRECT pattern (zero = no rating claim and
        // the UI branches on total_reviews), so the leading [1-9] excludes
        // them; anything else is a fabricated score.
        const pattern =
          /(rating[a-z_]*|average_rating)\s*(\|\||\?\?)\s*[1-9]\d*(\.\d+)?/i;
        if (pattern.test(code)) {
          offenders.push(path.relative(path.join(__dirname, ".."), file));
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("the product page shows no rating when there are zero reviews", () => {
    const page = readFileSync(
      path.join(__dirname, "..", "app", "(store)", "products", "[slug]", "page.tsx"),
      "utf8",
    );
    // The header summary must branch on total_reviews — a presence check on
    // the word alone would pass on a comment, so require the guard AND the
    // no-reviews copy.
    expect(page).toContain("total_reviews > 0");
    expect(page).toContain("هنوز نظری ثبت نشده است");
    // And the reviews tab must not invent a distribution for zero reviews.
    expect(stripComments(page)).not.toMatch(/star === 5\s*\?\s*80/);
  });

  it("the product JSON-LD only emits AggregateRating from real stats", () => {
    const layout = stripComments(
      readFileSync(
        path.join(__dirname, "..", "app", "(store)", "products", "[slug]", "layout.tsx"),
        "utf8",
      ),
    );
    // Stats come from the reviews endpoint, and the node is conditional.
    expect(layout).toContain("fetchReviewStats");
    expect(layout).toContain("aggregateRating");
    // No non-zero numeric rating fallback anywhere in the layout.
    expect(layout).not.toMatch(/rating[a-z_]*\s*(\|\||\?\?)\s*[1-9]/i);
  });
});
