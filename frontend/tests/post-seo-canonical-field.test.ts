/**
 * Pins the canonical input in the post SEO panel (SEO audit F-18).
 *
 * The canonical plumbing was complete end-to-end (schema column, read/write
 * API, storefront consumption) except the one thing a human needs: an input
 * in the editor. This test locks the three wiring points — state, load, and
 * save payload — plus the visible field.
 *
 * Negative test: remove `canonicalUrl` from the upsert payload and the
 * first assertion fails; the field silently stops saving.
 */
import { readFileSync } from "fs";
import { resolve } from "path";
import { describe, expect, it } from "vitest";

const src = readFileSync(
  resolve(__dirname, "../components/admin/blog/post-seo-panel.tsx"),
  "utf-8",
);

describe("post SEO panel canonical field", () => {
  it("sends canonicalUrl in the save payload", () => {
    expect(src).toMatch(/canonicalUrl:\s*canonicalUrl\.trim\(\)\s*\|\|\s*null/);
  });

  it("loads the stored canonical into state", () => {
    expect(src).toMatch(/setCanonicalUrl\(meta\?\.canonicalUrl/);
  });

  it("renders the canonical input", () => {
    expect(src).toMatch(/id="seo-canonical"/);
  });
});
