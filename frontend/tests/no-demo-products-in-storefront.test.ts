/**
 * No fabricated demo products in the storefront.
 *
 * The compare page shipped a `FLAGSHIP_SUGGESTIONS` array of three fake
 * physical products (Samsung Galaxy S24 Ultra, iPhone 16 Pro Max, Asus
 * Zenbook) with invented prices, ratings and Unsplash images. A digital-goods
 * shop has none of these in its catalog; "add to cart" on them errored, the
 * 4.7+ ratings were fabricated claims, and the whole block was hardcoded demo
 * data masquerading as recommendations.
 *
 * This gate fails if hardcoded product-shaped demo data reappears anywhere in
 * storefront code. It matches the *shape* (a const array of product literals
 * with a hardcoded price), not just the old names — renaming the phones would
 * not sneak past it.
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

/** Strip comments — documenting the removed demo must not fail the gate. */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("no fabricated demo products in storefront", () => {
  it("no hardcoded product-literal arrays with fabricated prices", () => {
    const offenders: string[] = [];
    for (const root of STOREFRONT_ROOTS) {
      for (const file of walk(root)) {
        const code = stripComments(readFileSync(file, "utf8"));
        // A const array of Product objects with a hardcoded numeric price —
        // the exact shape of the removed FLAGSHIP_SUGGESTIONS block. A real
        // catalog page fetches products; it never declares them.
        const demoArray =
          /const\s+[A-Z_]*\s*(?::\s*Product\[\])?\s*=\s*\[[\s\S]{0,3000}?price:\s*\d{4,}/;
        if (demoArray.test(code)) {
          offenders.push(path.relative(path.join(__dirname, ".."), file));
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("the compare page carries no flagship demo remnants", () => {
    const source = stripComments(
      readFileSync(
        path.join(__dirname, "..", "app", "(store)", "compare", "page.tsx"),
        "utf8",
      ),
    );
    for (const token of [
      "FLAGSHIP",
      "Samsung",
      "Galaxy",
      "iPhone",
      "Zenbook",
      "unsplash",
    ]) {
      expect(source).not.toContain(token);
    }
    // And the real store links stay.
    expect(source).toContain("/products");
  });
});
