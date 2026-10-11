/**
 * Pins the product soft-404 fix (2026-10-09).
 *
 * `/products/<nonexistent>` returned **HTTP 200** with a "not found" screen:
 * the page body is a client component, so it could only swap the visible
 * content — the status line stayed 200 and `robots` said `index, follow`.
 * That is a soft 404: Google indexes unlimited made-up product URLs and
 * spends crawl budget on them.
 *
 * The fix: the server-side layout calls `notFound()` when the product does
 * not resolve, which sets a real 404. Verified live: fake slugs → 404,
 * real slug → 200.
 *
 * Negative test: remove the `notFound()` call from the layout and the
 * source assertion fails (and the live check goes back to 200).
 */
import { readFileSync } from "fs";
import { resolve } from "path";
import { describe, expect, it } from "vitest";

const layoutSrc = readFileSync(
  resolve(__dirname, "../app/(store)/products/[slug]/layout.tsx"),
  "utf-8",
);

describe("product detail is a real 404 when the product does not exist", () => {
  it("the server layout calls notFound() on a missing product", () => {
    expect(layoutSrc).toMatch(/if \(!product\)\s*\{\s*notFound\(\);/);
  });

  it("generateMetadata describes the error page instead of calling notFound", () => {
    // `notFound()` inside generateMetadata aborts the render before the
    // metadata is used, and Next then emits a 404 document with NO title
    // (verified live). The metadata call must RETURN a titled, noindex
    // document; the status comes from the default layout.
    const metaFn = layoutSrc.split("export async function generateMetadata")[1] ?? "";
    const metaBody = metaFn.split("export default")[0] ?? "";
    expect(metaBody).toContain("محصول مورد نظر یافت نشد");
    expect(metaBody).toMatch(/robots:\s*\{\s*index:\s*false/);
    // Only executable lines count — the explanatory comment above mentions
    // `notFound()` by name, which a naive source grep would flag.
    const codeOnly = metaBody
      .split("\n")
      .filter((line) => !line.trim().startsWith("//"))
      .join("\n");
    expect(codeOnly).not.toMatch(/notFound\(\)/);
  });
});
