import sanitizeHtmlLib from "sanitize-html";
// A relative path, not the "@/" alias: the sibling import below already
// does it, and an alias breaks this module outside Next's bundler —
// which is how the srcset check had to be written to import it directly.
import { withResponsiveImages } from "./content-responsive-images";

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

  const withoutStrangers = clean.replace(
    /<iframe\b[^>]*\bsrc="([^"]*)"[^>]*>(?:<\/iframe>)?/gi,
    (match, src: string) => (isAllowedEmbedSrc(src) ? match : ""),
  );

  // After sanitizing, not before: sanitize-html rebuilds each tag from its
  // whitelist, and an attribute it does not know about is dropped. Emitting
  // srcset first would mean the attribute never survives. Doing it here also
  // means every consumer of cleanHtml — the blog post, the CMS page, the
  // password-protected body — gets responsive images without each page
  // remembering to ask.
  return withResponsiveImages(withoutStrangers);
}

import { sanitizeScopedCss } from "./builder/scoped-css";

const BUILDER_ALLOWED_TAGS: string[] = Array.from(
  new Set([
    ...ALLOWED_TAGS,
    "svg", "path", "polygon", "circle", "rect", "line", "polyline", "g",
    "button", "label", "input", "textarea", "select", "option", "form",
  ])
);

const BUILDER_SAFE_CSS_VALUE_RE =
  /^(?!.*(?:expression\s*\(|javascript\s*:|vbscript\s*:|@import|behavior\s*:|-moz-binding|url\s*\(\s*["']?\s*(?:https?:|data:|\/\/))).+$/i;

const BUILDER_ALLOWED_CSS_PROPS = new Set([
  "color", "background-color", "background-image", "background-position",
  "background-size", "background-repeat", "background-attachment",
  "background-blend-mode", "mix-blend-mode", "background",
  "font-size", "font-weight", "font-style", "font-family", "line-height",
  "letter-spacing", "word-spacing", "text-align", "text-decoration", "text-transform",
  "-webkit-text-stroke-width", "-webkit-text-stroke-color",
  "text-shadow", "margin", "margin-top", "margin-right", "margin-bottom",
  "margin-left", "margin-inline-start", "margin-inline-end",
  "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
  "padding-inline-start", "padding-inline-end",
  "border", "border-top", "border-right", "border-bottom", "border-left",
  "border-radius", "border-color", "border-width", "border-style",
  "border-top-style", "border-top-width", "border-top-color",
  "width", "height", "max-width", "max-height", "min-width", "min-height",
  "display", "gap", "row-gap", "column-gap", "grid-template-columns", "grid-template-rows",
  "grid-auto-flow", "justify-items", "align-content",
  "flex", "flex-direction", "flex-wrap", "flex-grow",
  "order", "justify-content", "align-items", "align-self", "opacity",
  "box-shadow", "outline", "outline-offset", "overflow", "vertical-align", "white-space",
  "position", "top", "bottom", "left", "right", "inset", "z-index",
  "pointer-events", "direction", "animation-duration", "animation-delay",
  "animation-name", "transform", "filter", "backdrop-filter",
  "-webkit-backdrop-filter", "mask-image", "-webkit-mask-image", "mask-size",
  "-webkit-mask-size", "mask-position", "-webkit-mask-position", "mask-repeat",
  "-webkit-mask-repeat", "clip-path", "transition",
]);

function filterBuilderInlineStyle(rawStyle: string | undefined): string | undefined {
  if (!rawStyle) return undefined;
  const kept: string[] = [];
  for (const decl of rawStyle.split(";")) {
    const colon = decl.indexOf(":");
    if (colon <= 0) continue;
    const prop = decl.slice(0, colon).trim().toLowerCase();
    const val = decl.slice(colon + 1).trim();
    if (!prop || !val || !BUILDER_ALLOWED_CSS_PROPS.has(prop)) continue;
    if (!BUILDER_SAFE_CSS_VALUE_RE.test(val)) continue;
    kept.push(`${prop}: ${val}`);
  }
  return kept.length > 0 ? `${kept.join("; ")};` : undefined;
}

const BUILDER_RESPONSIVE_STYLE_RE =
  /<style\b[^>]*data-builder-responsive="1"[^>]*>([\s\S]*?)<\/style>/gi;

/**
 * Sanitize ASTCompiler-rendered Visual Page Builder SSR HTML without stripping
 * responsive styles, CSS tokens (hsl(var(--...))), transforms, dividers, spacers,
 * interactive form elements, or SVG shapes.
 */
export function cleanBuilderHtml(dirty: string): string {
  if (!dirty) return "";

  const preservedStyles: string[] = [];
  const withoutResponsiveStyles = dirty.replace(
    BUILDER_RESPONSIVE_STYLE_RE,
    (_m, cssText: string) => {
      const safeCss = sanitizeScopedCss(cssText || "");
      if (safeCss) preservedStyles.push(safeCss);
      return "";
    }
  );

  const options: sanitizeHtmlLib.IOptions = {
    allowedTags: BUILDER_ALLOWED_TAGS,
    allowedAttributes: {
      ...ALLOWED_ATTR_BY_TAG,
      "*": [
        ...ALLOWED_ATTR,
        "data-*", "aria-*", "tabindex",
      ],
      form: ["action", "method", "enctype", "novalidate", "name", "target"],
      input: [
        "type", "name", "value", "placeholder", "required", "disabled",
        "readonly", "checked", "autocomplete",
      ],
      textarea: ["name", "placeholder", "rows", "cols", "required", "disabled", "readonly"],
      select: ["name", "required", "disabled"],
      option: ["value", "selected"],
      button: ["type", "disabled"],
      label: ["for"],
      video: ["src", "controls", "poster", "width", "height", "preload", "autoplay", "muted", "loop", "playsinline"],
      svg: [
        "xmlns", "viewbox", "viewBox", "width", "height", "fill", "stroke",
        "stroke-width", "stroke-linecap", "stroke-linejoin",
        "preserveaspectratio", "preserveAspectRatio",
      ],
      path: ["d", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "opacity"],
      polygon: ["points", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin"],
      circle: ["cx", "cy", "r", "fill", "stroke", "stroke-width"],
      rect: ["x", "y", "width", "height", "rx", "ry", "fill", "stroke", "stroke-width"],
      line: ["x1", "y1", "x2", "y2", "stroke", "stroke-width", "stroke-linecap"],
      polyline: ["points", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin"],
      g: ["fill", "stroke", "stroke-width", "transform"],
    },
    allowedSchemes: ["http", "https", "mailto", "tel"],
    allowedSchemesAppliedToAttributes: ["href", "src", "cite"],
    allowedSchemesByTag: { img: ["http", "https", "data"] },
    transformTags: {
      "*": (tagName, attribs) => {
        if (attribs.style) {
          const filtered = filterBuilderInlineStyle(attribs.style);
          if (filtered) attribs.style = filtered;
          else delete attribs.style;
        }
        return { tagName, attribs };
      },
    },
  };

  const clean = sanitizeHtmlLib(withoutResponsiveStyles, options);
  const withoutStrangers = clean.replace(
    /<iframe\b[^>]*\bsrc="([^"]*)"[^>]*>(?:<\/iframe>)?/gi,
    (match, src: string) => (isAllowedEmbedSrc(src) ? match : ""),
  );
  let rendered = withResponsiveImages(withoutStrangers);
  if (preservedStyles.length > 0) {
    const styleBlock = `<style data-builder-responsive="1">${preservedStyles.join("\n")}</style>`;
    rendered = rendered.replace(
      /(<div\b[^>]*class="builder-document[^"]*"[^>]*>)/i,
      `$1${styleBlock}`
    );
  }
  return rendered;
}

export default cleanHtml;
