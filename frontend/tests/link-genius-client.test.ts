/**
 * Link Genius admin client + page wiring (Rank Math Pro parity, 2026-10-11).
 *
 * Pins the wiring points a human would otherwise have to click through:
 *   - the API client hits the real admin paths (a typo'd path is a 404 at
 *     runtime, invisible to a type-check),
 *   - the delete uses the two-segment link-maps route, NOT a metadata delete,
 *   - the page renders the suggestion list, the incoming-link list, and the
 *     keyword-map controls, and uses the in-app confirm (never window.confirm).
 *
 * Negative tests: change a path or remove a control and the matching
 * assertion fails.
 */
import { readFileSync } from "fs";
import { resolve } from "path";
import { describe, expect, it } from "vitest";

const clientSrc = readFileSync(resolve(__dirname, "../lib/api/seo.ts"), "utf-8");
const pageSrc = readFileSync(
  resolve(__dirname, "../app/admin/seo/link-genius/page.tsx"),
  "utf-8",
);
const navSrc = readFileSync(resolve(__dirname, "../lib/admin-nav.ts"), "utf-8");

describe("link genius API client", () => {
  it("targets the real admin paths", () => {
    expect(clientSrc).toContain("/admin/seo/posts/${encodeURIComponent(postId)}/link-suggestions");
    expect(clientSrc).toContain("/admin/seo/posts/${encodeURIComponent(postId)}/incoming-links");
    expect(clientSrc).toContain("/admin/seo/posts/${encodeURIComponent(postId)}/reindex-links");
    expect(clientSrc).toContain('"/admin/seo/link-maps"');
  });

  it("deletes a link map via the two-segment route (not a metadata delete)", () => {
    // DELETE /admin/seo/link-maps/{id} — the specific route registered BEFORE
    // the generic /admin/seo/{resource_type}/{resource_id}.
    expect(clientSrc).toMatch(
      /delete\(`\/admin\/seo\/link-maps\/\$\{encodeURIComponent\(mapId\)\}`\)/,
    );
  });

  it("previews and applies maps through the dedicated endpoints", () => {
    expect(clientSrc).toContain('"/admin/seo/link-maps/preview"');
    expect(clientSrc).toContain('"/admin/seo/link-maps/apply"');
  });
});

describe("link genius page", () => {
  it("renders the suggestions panel", () => {
    expect(pageSrc).toContain("fetchLinkSuggestions");
    expect(pageSrc).toContain("پیشنهاد برای پیوند دادن");
  });

  it("requests a page_size the API accepts (<= 100)", () => {
    // The first version asked for page_size: 200, which the API answers with
    // 422 — the post picker rendered empty. Only the browser E2E caught it;
    // this pins the ceiling so it cannot regress.
    const match = pageSrc.match(/page_size:\s*(\d+)/);
    expect(match, "no page_size in the page").not.toBeNull();
    expect(Number(match![1])).toBeLessThanOrEqual(100);
  });

  it("renders the incoming-links panel", () => {
    expect(pageSrc).toContain("fetchIncomingLinks");
    expect(pageSrc).toContain("لینک‌های ورودی به این نوشته");
  });

  it("renders the keyword-map manager with create/delete", () => {
    expect(pageSrc).toContain("fetchLinkMaps");
    expect(pageSrc).toContain("createLinkMap");
    expect(pageSrc).toContain("deleteLinkMap");
    expect(pageSrc).toContain("نقشهٔ جدید");
  });

  it("uses the in-app confirm, never window.confirm", () => {
    // window.confirm is a silent no-op in a sandboxed iframe (see
    // confirm-dialog.tsx) — a delete gated on it would look dead. The hook
    // (`useConfirm()`) is the only allowed source; a bare global
    // `confirm("...")` call is the bug this guards against.
    expect(pageSrc).toContain("useConfirm");
    expect(pageSrc).not.toMatch(/window\.confirm\s*\(|globalThis\.confirm\s*\(/);
    expect(pageSrc).not.toMatch(/\bconfirm\(\s*["'`]/);
  });

  it("offers apply-to-all behind a confirmation", () => {
    expect(pageSrc).toContain("applyLinkMap");
    expect(pageSrc).toContain("all_posts: true");
  });
});

describe("link genius nav entry", () => {
  it("is reachable from the SEO menu", () => {
    expect(navSrc).toContain('href: "/admin/seo/link-genius"');
    expect(navSrc).toContain("Sparkles");
  });
});

describe("link genius client — broken-link crawler", () => {
  const auditSrc = readFileSync(
    resolve(__dirname, "../app/admin/seo/link-audit/page.tsx"),
    "utf-8",
  );

  it("targets the real audit paths", () => {
    expect(clientSrc).toContain('"/admin/seo/link-audit"');
    expect(clientSrc).toContain('"/admin/seo/link-audit/run"');
    expect(clientSrc).toMatch(/link-audit\/\$\{encodeURIComponent\(auditId\)\}\/safe/);
  });

  it("the page runs the crawler and lists results", () => {
    expect(auditSrc).toContain("runLinkAudit");
    expect(auditSrc).toContain("fetchLinkAudit");
    expect(auditSrc).toContain("بررسی لینک‌های شکسته");
    expect(auditSrc).toContain("بررسی کن");
  });

  it("the page uses the in-app confirm for clearing, never window.confirm", () => {
    expect(auditSrc).toContain("useConfirm");
    expect(auditSrc).not.toMatch(/window\.confirm\s*\(|globalThis\.confirm\s*\(/);
  });

  it("is reachable from the SEO menu", () => {
    expect(navSrc).toContain('href: "/admin/seo/link-audit"');
  });
});

describe("storefront consumer of the related-posts route", () => {
  const blogSrc = readFileSync(
    resolve(__dirname, "../app/(store)/blog/[slug]/page.tsx"),
    "utf-8",
  );

  it("calls the public /seo/blog/{slug}/related route", () => {
    // "a route without a consumer is a gap" — the route must have a caller.
    expect(blogSrc).toContain("/seo/blog/${encodeURIComponent(slug)}/related");
  });

  it("only fetches when the same-category list is empty (no wasted request)", () => {
    expect(blogSrc).toMatch(/hasCategoryRelated\s*\?\s*\[\]\s*:\s*await\s+getGeniusRelated/);
  });
});
