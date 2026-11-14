import { describe, expect, it } from "vitest";
import {
  validateStructure,
  baseSegmentProblems,
  DEFAULT_ROUTING,
} from "@/lib/permalinks";

/**
 * Permalink structure validation — the WP-parity «پیوندهای یکتا» screen
 * blocks structures that would generate dead URLs. Mirrored rules live in
 * backend/app/shared/permalinks.py (checked there by an inline python
 * snippet in the delivery notes); this file pins the frontend side.
 */
describe("validateStructure", () => {
  it("accepts the presets the permalink screen offers", () => {
    for (const structure of [
      DEFAULT_ROUTING.permalink_structure, // /blog/%postname%/
      "/%year%/%monthnum%/%postname%/",
      "/%year%/%monthnum%/%day%/%postname%/",
      "/archives/%post_id%",
      "/%postname%/",
    ]) {
      expect(validateStructure(structure), structure).toEqual([]);
    }
  });

  it("rejects a literal reserved first segment (the file tree owns it)", () => {
    // /blog/<x>/<y> is three segments: no physical route serves it and the
    // middleware skips reserved roots, so every generated URL would 404.
    expect(validateStructure("/blog/%category%/%postname%/")).not.toEqual([]);
    expect(validateStructure("/products/%postname%/")).not.toEqual([]);
    expect(validateStructure("/account/%postname%/")).not.toEqual([]);
  });

  it("keeps accepting the default /blog/%postname%/ (it IS the physical route)", () => {
    expect(validateStructure("/blog/%postname%/")).toEqual([]);
  });

  it("allows a tag in the first segment (value is dynamic, not a fixed route)", () => {
    expect(validateStructure("/%category%/%postname%/")).toEqual([]);
    expect(validateStructure("/%year%/%postname%/")).toEqual([]);
  });

  it("keeps the classic shape rules", () => {
    expect(validateStructure("blog/%postname%/").length).toBeGreaterThan(0); // no leading /
    expect(validateStructure("/%whatever%/").length).toBeGreaterThan(0); // unknown tag
    expect(validateStructure("/fixed/").length).toBeGreaterThan(0); // no tag at all
    expect(validateStructure("/%day%/%year%/%postname%/").length).toBeGreaterThan(0); // date order
  });
});

describe("baseSegmentProblems (taxonomy/product bases)", () => {
  it("accepts a single fresh segment, Persian included", () => {
    expect(baseSegmentProblems("topic")).toEqual([]);
    expect(baseSegmentProblems("موضوع")).toEqual([]);
    expect(baseSegmentProblems("")).toEqual([]); // empty = default
  });

  it("rejects multi-segment bases (the middleware only rewrites two-segment paths)", () => {
    expect(baseSegmentProblems("a/b").length).toBeGreaterThan(0);
  });

  it("rejects fixed storefront roots", () => {
    expect(baseSegmentProblems("blog").length).toBeGreaterThan(0);
    expect(baseSegmentProblems("account").length).toBeGreaterThan(0);
    expect(baseSegmentProblems("checkout").length).toBeGreaterThan(0);
  });

  it("lets the product base keep its own default value", () => {
    expect(baseSegmentProblems("products", DEFAULT_ROUTING.product_base)).toEqual([]);
    expect(baseSegmentProblems("blog", DEFAULT_ROUTING.product_base).length).toBeGreaterThan(0);
  });

  it("lets each taxonomy base keep its canonical default", () => {
    // "category" is root-reserved (the shop archive /category/<slug>), yet it
    // is ALSO the blog category base's own default — the allow-list resolves
    // that, so the settings screen never ships disabled out of the box.
    expect(baseSegmentProblems("category", DEFAULT_ROUTING.category_base)).toEqual([]);
    expect(baseSegmentProblems("tag", DEFAULT_ROUTING.tag_base)).toEqual([]);
    // …but "category" stays rejected for a field whose default it is not.
    expect(baseSegmentProblems("category", "tag").length).toBeGreaterThan(0);
  });
});
