import sanitizeHtmlLib from "sanitize-html";

/**
 * Server and Node-safe HTML sanitization using sanitize-html.
 * Complements DOMPurify for robust multi-layer defense.
 */
export function cleanHtml(dirty: string, options?: sanitizeHtmlLib.IOptions): string {
  if (!dirty) return "";

  const defaultOptions: sanitizeHtmlLib.IOptions = {
    allowedTags: [
      "b",
      "i",
      "em",
      "strong",
      "a",
      "p",
      "br",
      "ul",
      "ol",
      "li",
      "span",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "blockquote",
      "code",
      "pre",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
    ],
    allowedAttributes: {
      a: ["href", "name", "target", "rel"],
      "*": ["class", "title", "dir", "aria-label"],
    },
    allowedSchemes: ["http", "https", "mailto", "tel"],
  };

  return sanitizeHtmlLib(dirty, options || defaultOptions);
}

export default cleanHtml;
