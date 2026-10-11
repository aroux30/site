/**
 * Pins the unique product meta fallback (SEO audit F-04).
 *
 * Live audit 2026-10-10: 5,146 products shared 15 distinct names and one
 * identical meta description. Only the slug is unique (5146/5146), so the
 * fallback title/description must include it — otherwise every product page
 * is a near-duplicate and search engines pick one arbitrary page to index.
 *
 * Negative test: remove `product.slug` from either fallback and the
 * source-level assertions fail.
 */
import { readFileSync } from "fs";
import { resolve } from "path";
import { describe, expect, it } from "vitest";

const src = readFileSync(
  resolve(__dirname, "../app/(store)/products/[slug]/layout.tsx"),
  "utf-8",
);

describe("product meta fallbacks are unique per product", () => {
  it("title fallback includes the slug", () => {
    expect(src).toMatch(/product\.seo_title \|\| `\$\{product\.name\} \(کد \$\{product\.slug\}\)`/);
  });

  it("description fallback includes the slug", () => {
    const fallback = src.match(/`خرید \$\{product\.name\} \(کد \$\{product\.slug\}\)[^`]*`/);
    expect(fallback, "description fallback must carry the slug").not.toBeNull();
  });
});
