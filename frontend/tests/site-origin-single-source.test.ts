/**
 * Pins the single-source rule for the site origin (SEO audit F-15).
 *
 * The storefront had two origin sources: NEXT_PUBLIC_SITE_URL (siteOrigin())
 * for most pages, and the DB value (routing.site_url) for four blog files.
 * If an operator updates only one of them, the blog canonicalizes to a
 * different domain than the rest of the site — worse than before, because
 * the divergence is silent.
 *
 * Rule: storefront files use siteOrigin() only. `routing.site_url` remains
 * allowed in admin pages (they display/edit the DB value).
 *
 * Negative test: re-add `routing.site_url ||` to any storefront file and
 * this fails.
 */
import { readFileSync, readdirSync, statSync } from "fs";
import { join, resolve } from "path";
import { describe, expect, it } from "vitest";

const STORE_DIR = resolve(__dirname, "../app/(store)");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    const st = statSync(p);
    if (st.isDirectory()) out.push(...walk(p));
    else if (/\.(tsx?|ts)$/.test(entry)) out.push(p);
  }
  return out;
}

describe("single origin source in the storefront", () => {
  it("no storefront file reads routing.site_url", () => {
    const offenders: string[] = [];
    for (const file of walk(STORE_DIR)) {
      const src = readFileSync(file, "utf-8");
      // Comment mentions are fine; a code read is not.
      const code = src
        .split("\n")
        .filter((line) => !line.trim().startsWith("//"))
        .join("\n");
      if (code.includes("routing.site_url")) offenders.push(file.replace(STORE_DIR, ""));
    }
    expect(offenders, `files still reading routing.site_url: ${offenders.join(", ")}`).toEqual([]);
  });
});
