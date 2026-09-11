import DOMPurify from "dompurify";

export type SanitizeOptions = Parameters<typeof DOMPurify.sanitize>[1];

/**
 * Sanitize untrusted HTML to prevent XSS (Cross-Site Scripting) attacks.
 * Safe for both client-side and server-side contexts.
 */
export function sanitizeHtml(
  rawHtml: string | null | undefined,
  options?: SanitizeOptions,
): string {
  if (!rawHtml) return "";

  if (typeof window === "undefined") {
    // In server environment where DOM is unavailable, strip dangerous script/object tags
    return rawHtml
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
      .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, "")
      .replace(/<object\b[^<]*(?:(?!<\/object>)<[^<]*)*<\/object>/gi, "")
      .replace(/on\w+="[^"]*"/gi, "")
      .replace(/on\w+='[^']*'/gi, "");
  }

  const defaultOptions: SanitizeOptions = {
    ALLOWED_TAGS: [
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
    ALLOWED_ATTR: [
      "href",
      "target",
      "rel",
      "class",
      "title",
      "dir",
      "style",
      "aria-label",
    ],
  };

  return DOMPurify.sanitize(rawHtml, options || defaultOptions);
}

export default sanitizeHtml;
