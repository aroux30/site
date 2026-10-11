/**
 * Pins the month-archive metadata (found live 2026-10-10 by the monitoring
 * session; the winning audit plan had missed it).
 *
 * `[month]/page.tsx` forwarded the year page's component but NOT its
 * generateMetadata, so Next fell back to the blog layout: every month URL
 * answered title "مجله و بلاگ" and canonical `/blog` — while the sitemap
 * advertises those month URLs. Google asked for the month page and was
 * told "I am the blog index".
 *
 * Negative test: remove the generateMetadata export from this file and the
 * assertions fail.
 */
import { readFileSync } from "fs";
import { resolve } from "path";
import { describe, expect, it } from "vitest";

const src = readFileSync(
  resolve(__dirname, "../app/(store)/blog/archive/[year]/[month]/page.tsx"),
  "utf-8",
);

describe("month archive metadata", () => {
  it("exports generateMetadata", () => {
    expect(src).toMatch(/export async function generateMetadata/);
  });

  it("canonical is month-scoped, not the blog root", () => {
    expect(src).toMatch(/canonical: `\$\{base\}\/blog\/archive\/\$\{year\}\/\$\{month\}`/);
    expect(src).not.toMatch(/canonical:.*\/blog`/);
  });

  it("title carries the month label", () => {
    expect(src).toMatch(/title: `آرشیو \$\{label\}`/);
  });

  it("still renders the shared year component", () => {
    expect(src).toMatch(/return <ArchivePage params=\{params\} \/>/);
  });
});
