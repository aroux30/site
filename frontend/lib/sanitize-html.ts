import sanitizeHtmlLib from "sanitize-html";

import {
  ALLOWED_ATTR,
  ALLOWED_ATTR_BY_TAG,
  ALLOWED_TAGS,
  ALLOWED_URI_REGEXP,
  isAllowedEmbedSrc,
} from "./editor/allowlist";

/**
 * Server and Node-safe HTML sanitization using sanitize-html.
 * Complements DOMPurify for robust multi-layer defense.
 */

const DEFAULT_OPTIONS: sanitizeHtmlLib.IOptions = {
  // One list, shared with the editor and (kept in step by script) the backend.
  // This file used to carry a third, shorter list, so a body could pass the
  // editor and then be unwrapped at render time.
  allowedTags: ALLOWED_TAGS,
  allowedAttributes: {
    ...ALLOWED_ATTR_BY_TAG,
    "*": ALLOWED_ATTR,
  },
  allowedSchemes: ["http", "https", "mailto", "tel"],
  allowedSchemesAppliedToAttributes: ["href", "src", "cite"],
  // Shortcode output ([button], [alert], [gallery]) carries presentation as
  // inline styles. Permitting `style` without this list would allow any CSS,
  // so the safe presentational subset is enumerated; anything else — notably
  // `url()` and `expression()` — is dropped.
  allowedStyles: {
    "*": {
      color: [/^#[0-9a-f]{3,8}$/i, /^rgba?\([\d\s.,%]+\)$/i, /^[a-z]+$/i],
      "background-color": [/^#[0-9a-f]{3,8}$/i, /^rgba?\([\d\s.,%]+\)$/i, /^[a-z]+$/i],
      background: [/^#[0-9a-f]{3,8}$/i, /^rgba?\([\d\s.,%]+\)$/i, /^[a-z]+$/i],
      "border-radius": [/^[\d.]+(px|rem|em|%)$/],
      "text-decoration": [/^[a-z-]+$/],
      display: [/^(inline-block|block|flex|inline|none)$/],
      "flex-wrap": [/^(wrap|nowrap)$/],
      gap: [/^[\d.]+(px|rem|em)$/],
      "flex-basis": [/^[\d.]+(px|rem|em|%)$/],
      "aspect-ratio": [/^[\d\s./]+$/],
      width: [/^[\d.]+(px|rem|em|%)$/],
      "max-width": [/^[\d.]+(px|rem|em|%)$/],
      padding: [/^[\d.\s]+(px|rem|em|%)*$/],
      margin: [/^[\d.\s-]+(px|rem|em|%)*$/],
    },
  },
  // Inline previews and pasted captures arrive as data: URIs; a stored CMS
  // body may legitimately carry one. Script-bearing schemes stay blocked.
  allowedSchemesByTag: { img: ["http", "https", "data"] },
};

/**
 * Sanitize a CMS body for rendering.
 *
 * Beyond the tag whitelist this enforces the embed-host policy: sanitize-html
 * cannot filter an iframe by host, so an iframe left after sanitization is
 * removed unless its `src` is an allowlisted provider. Without this pass any
 * editor could store an arbitrary third-party frame.
 */
export function cleanHtml(dirty: string, options?: sanitizeHtmlLib.IOptions): string {
  if (!dirty) return "";

  const clean = sanitizeHtmlLib(dirty, options || DEFAULT_OPTIONS);

  // Only enforce the host policy when running under the default (CMS) policy;
  // a caller supplying explicit options owns its own iframe decision.
  if (options) return clean;

  return clean.replace(
    /<iframe\b[^>]*\bsrc="([^"]*)"[^>]*>(?:<\/iframe>)?/gi,
    (match, src: string) => (isAllowedEmbedSrc(src) ? match : ""),
  );
}

export default cleanHtml;
