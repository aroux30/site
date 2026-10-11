/**
 * Extract an FAQPage JSON-LD payload from a rendered article body.
 *
 * A "سوالات متداول" section is a normal part of a guide article — the
 * migrated pubg-mobile post has ten question/answer pairs under an H2 with
 * that title. Google reads FAQPage structured data for those and can show
 * the Q&As directly in search results; without the markup the section is
 * invisible to Rich Results.
 *
 * The shape the extractor accepts is the one the editor and the import
 * produce: an `<h2>` whose text contains "سوالات متداول" (or "FAQ"), then
 * one `<h3>` per question followed by one or more paragraphs/`<ul>`/`<ol>`
 * that form the answer — until the next `<h2>`.
 *
 * Deliberately conservative:
 * - No H2/FAQ heading, or fewer than two questions, returns null. A single
 *   "Q&A" heading is usually a section title, not a FAQ block, and Google
 *   requires at least two entries for the rich result.
 * - Answer text is the heading's following block content, tags stripped.
 *   The first sentence only would cut an answer mid-list.
 *
 * Runs on the ALREADY-RENDERED body (post content after `render_body`), so
 * the heading levels are the ones the page shows (the body's own H1 was
 * demoted to H2 by `demote_body_h1`, which is why this looks for H2).
 */

export interface FaqEntry {
  question: string;
  answer: string;
}

/** Decode the entities `cleanHtml` can leave in text nodes. */
function decodeEntities(text: string): string {
  return text
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;|&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, code: string) => String.fromCodePoint(Number(code)));
}

function textOf(html: string): string {
  return decodeEntities(html.replace(/<[^>]+>/g, " "))
    .replace(/\s+/g, " ")
    .trim();
}

/** FAQ heading markers, checked case-insensitively against heading text. */
const FAQ_HEADING_MARKERS = ["سوالات متداول", "سوالات پرتکرار", "faq", "questions"];

/**
 * Find the FAQ entries in a rendered body, or null when the body has none.
 *
 * `bodyHtml` must be the same HTML the page renders (post-sanitize,
 * post-render-body) so heading levels and text match what a reader sees.
 */
export function extractFaqEntries(bodyHtml: string | null | undefined): FaqEntry[] | null {
  if (!bodyHtml) return null;

  // Split the body into heading-delimited regions. A small parser instead of
  // DOMParser because this runs on the server, where there is no DOM.
  const headingRe = /<h([1-6])\b[^>]*>([\s\S]*?)<\/h\1\s*>/gi;
  const headings: { level: number; text: string; start: number; end: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = headingRe.exec(bodyHtml)) !== null) {
    headings.push({
      level: Number(m[1]),
      text: textOf(m[2] ?? ""),
      start: m.index,
      end: m.index + m[0].length,
    });
  }

  const faqHeading = headings.find(
    (h) =>
      h.level <= 3 &&
      FAQ_HEADING_MARKERS.some((marker) =>
        h.text.toLowerCase().includes(marker.toLowerCase()),
      ),
  );
  if (!faqHeading) return null;

  // The FAQ region runs until the next heading of the same or higher level.
  const regionEnd =
    headings.find((h) => h.start > faqHeading.end && h.level <= faqHeading.level)
      ?.start ?? bodyHtml.length;
  const region = bodyHtml.slice(faqHeading.end, regionEnd);

  // Within the region: h3 (or h4) = question, following content = answer.
  // One forward scan records each question's heading start; an answer runs
  // from its own heading to the next one (the last runs to the region end).
  const qRe = /<h([3-4])\b[^>]*>([\s\S]*?)<\/h\1\s*>/gi;
  const questions: { question: string; answerStart: number; answerEnd: number }[] = [];
  let qm: RegExpExecArray | null;
  while ((qm = qRe.exec(region)) !== null) {
    questions.push({
      question: textOf(qm[2] ?? ""),
      answerStart: qm.index + qm[0].length,
      answerEnd: region.length,
    });
  }
  if (questions.length < 2) return null;

  for (let i = 0; i < questions.length; i++) {
    const current = questions[i];
    if (!current) continue;
    if (questions[i + 1]) {
      // The next question's heading is the first `<h` after this answer's
      // start; the heading length is not stored, so re-find it by index.
      const nextHeadingAt = region.indexOf("<h", current.answerStart);
      current.answerEnd = nextHeadingAt === -1 ? region.length : nextHeadingAt;
    }
  }

  const entries: FaqEntry[] = [];
  for (const q of questions) {
    const answer = textOf(region.slice(q.answerStart, q.answerEnd));
    if (q.question && answer) {
      entries.push({ question: q.question, answer });
    }
  }
  return entries.length >= 2 ? entries : null;
}

/** The FAQPage JSON-LD node for a set of entries. */
export function faqJsonLd(entries: FaqEntry[]): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: entries.map((e) => ({
      "@type": "Question",
      name: e.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: e.answer,
      },
    })),
  };
}
