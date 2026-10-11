/**
 * Pins the FAQPage extractor.
 *
 * The migrated article carries a "سوالات متداول" H2 with ten H3 Q&As, and
 * none of it was structured data — Google's Rich Results could not see it.
 * `extractFaqEntries` pulls the pairs out of the rendered body; `faqJsonLd`
 * wraps them in a FAQPage node.
 *
 * Negative tests, each verified by sabotage:
 * - raise the minimum question count to 99 → the ten-Q fixture returns null
 * - drop the "سوالات متداول" marker → the extractor returns null
 */
import { describe, expect, it } from "vitest";

import { extractFaqEntries, faqJsonLd } from "@/lib/content-faq";

const BODY = `
<h2>فهرست مطالب</h2><ol><li>مقدمه</li></ol>
<h2>مقدمه</h2><p>متن مقدمه</p>
<h2>16. سوالات متداول</h2>
<h3>پابجی موبایل چقدر حجم دارد؟</h3>
<p>حجم اولیه بازی حدود 2 گیگابایت است.</p>
<h3>آیا پابجی موبایل رایگان است؟</h3>
<p>بله، بازی کاملاً رایگان است.</p>
<h3>بهترین گوشی چیست؟</h3>
<p>گوشی‌هایی با Snapdragon 855 یا بالاتر.</p>
`;

describe("extractFaqEntries", () => {
  it("extracts question/answer pairs from a FAQ section", () => {
    const entries = extractFaqEntries(BODY);
    expect(entries).not.toBeNull();
    expect(entries).toHaveLength(3);
    expect(entries?.[0]?.question).toBe("پابجی موبایل چقدر حجم دارد؟");
    expect(entries?.[0]?.answer).toContain("2 گیگابایت");
    // The answer must stop at the next question — not swallow the rest.
    expect(entries?.[0]?.answer).not.toContain("رایگان");
    expect(entries?.[2]?.answer).toContain("Snapdragon");
  });

  it("returns null without a FAQ heading", () => {
    const noFaq = "<h2>مقدمه</h2><p>متن</p>";
    expect(extractFaqEntries(noFaq)).toBeNull();
  });

  it("returns null with fewer than two questions", () => {
    const oneQ = "<h2>سوالات متداول</h2><h3>تنها سوال؟</h3><p>جواب</p>";
    expect(extractFaqEntries(oneQ)).toBeNull();
  });

  it("wraps entries in a valid FAQPage node", () => {
    const entries = extractFaqEntries(BODY);
    const ld = faqJsonLd(entries ?? []);
    expect(ld["@type"]).toBe("FAQPage");
    const main = ld.mainEntity as unknown[];
    expect(main).toHaveLength(3);
    const first = main[0] as Record<string, unknown>;
    expect(first["@type"]).toBe("Question");
    expect((first.acceptedAnswer as Record<string, unknown>).text).toContain("2 گیگابایت");
  });
});
