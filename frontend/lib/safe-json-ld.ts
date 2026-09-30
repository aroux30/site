/**
 * Safe JSON serialization for `<script type="application/ld+json">` blocks.
 *
 * `JSON.stringify` does not escape `<`, so any string field that reaches a
 * JSON-LD payload can contain `</script>` and terminate the script element,
 * turning structured-data output into an XSS sink.
 *
 * The replacement strings below are assembled with `String.fromCharCode(92)`
 * for the leading backslash, so the emitted text is a literal JSON unicode
 * escape rather than the character it is meant to escape. Writing the
 * replacement as a source literal is a trap: a single-backslash `<` in
 * JavaScript source *is* the character `<`, which silently turns the whole
 * call into a no-op — exactly the bug this module exists to prevent.
 *
 * U+2028/U+2029 are escaped too: they are valid inside JSON strings but were
 * illegal in JavaScript source, so they corrupt script blocks and break
 * JSON.parse consumers in older engines.
 *
 * Use this for every JSON-LD block. Never hand JSON.stringify output straight
 * to dangerouslySetInnerHTML.
 */
const BACKSLASH = String.fromCharCode(92);
const LINE_SEPARATOR = String.fromCharCode(0x2028);
const PARAGRAPH_SEPARATOR = String.fromCharCode(0x2029);

const JSON_LD_REPLACEMENTS: ReadonlyArray<readonly [RegExp, string]> = [
  [/</g, `${BACKSLASH}u003c`],
  [/>/g, `${BACKSLASH}u003e`],
  [/&/g, `${BACKSLASH}u0026`],
  [new RegExp(LINE_SEPARATOR, "g"), `${BACKSLASH}u2028`],
  [new RegExp(PARAGRAPH_SEPARATOR, "g"), `${BACKSLASH}u2029`],
];

export function safeJsonLd(data: unknown): string {
  return JSON_LD_REPLACEMENTS.reduce(
    (json, [pattern, replacement]) => json.replace(pattern, replacement),
    JSON.stringify(data),
  );
}
