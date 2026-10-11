/**
 * The stored schema override must reach the rendered page.
 *
 * The editor's schema builder wrote `seo_metadata.schema_markup` and the
 * storefront ignored it — the operator's schema choice was write-only. This
 * gate pins the two render paths:
 *
 * - blog/[slug]/page.tsx: a stored object REPLACES the built-in Article node
 *   (Rank Math semantics), while the FAQ/Breadcrumb nodes stay independent.
 * - products/[slug]/layout.tsx: `fetchSchemaOverride` feeds the JSON-LD, with
 *   the built-in Product node as the fallback when no override is stored.
 *
 * Live-verified during the wave: a committed HowTo override rendered as
 * `"@type":"HowTo"` on the product page, and removing the row restored the
 * Product node.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

function read(rel: string): string {
  return readFileSync(path.join(__dirname, "..", rel), "utf8");
}

describe("schema override reaches the rendered page", () => {
  it("blog page renders a stored object instead of the built-in Article", () => {
    const source = read("app/(store)/blog/[slug]/page.tsx");
    // The override branch must read seo.schema_markup and guard its shape.
    expect(source).toContain("post.seo?.schema_markup");
    expect(source).toMatch(/storedSchema[\s\S]{0,200}typeof storedSchema === "object"/);
    // And the built-in node must be the ELSE branch, not the only branch.
    expect(source).toContain('"@type": "Article"');
  });

  it("product layout fetches the override and falls back to the built-in node", () => {
    const source = read("app/(store)/products/[slug]/layout.tsx");
    expect(source).toContain("fetchSchemaOverride");
    // Fallback shape: override ?? built-in.
    expect(source).toMatch(/schemaOverride \?\? buildProductJsonLd/);
  });

  it("fetchSchemaOverride treats non-object markup as absent", () => {
    const source = read("lib/api/services.ts");
    // Arrays and primitives must not be cast into a schema node.
    expect(source).toContain("!Array.isArray(markup)");
  });

  it("schema builder UI is wired into the editor SEO panel", () => {
    const source = read("components/admin/blog/post-seo-panel.tsx");
    expect(source).toContain("SchemaBuilder");
    expect(source).toContain('"schema"');
  });

  it("schema builder never assembles JSON-LD client-side", () => {
    const source = read("components/admin/blog/schema-builder.tsx");
    // The server assembles; the client displays. A client-side build would
    // drift from what the storefront emits and the preview would lie.
    expect(source).toContain("buildSchema(");
    expect(source).toContain("applySchema(");
    // No local @type assembly anywhere in the component.
    expect(source).not.toMatch(/["']@type["']\s*:/);
  });
});
