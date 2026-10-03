/**
 * The one allowlist for stored editor content.
 *
 * Three lists used to exist — this file's neighbours `lib/editor/markdown.ts`,
 * `lib/sanitize-html.ts`, and `backend/app/shared/content/html_sanitizer.py` —
 * and they disagreed. The narrowest one, the list the editor applies on every
 * keystroke, was missing 45 tags the backend accepts, so inserting any of the
 * app's own block patterns and typing a single character silently unwrapped
 * them. The layouts in `backend/app/modules/content/domain/block_patterns.py`
 * are built from `section` and `div`; those are the two tags a layout is made
 * of, and the editor was eating them.
 *
 * So the client lists are generated from this one. The backend keeps its own
 * copy in Python — a cross-language single source is not worth a build step —
 * and `backend/tests`-grade parity is asserted by
 * `scripts/wp-parity/check_editor_allowlists.py`, which fails when the two
 * drift. Run it after changing either side.
 *
 * The two things this list must never grow: anything that executes
 * (`script`, `style`, `form`, `button`, `input`) and any embed that is not
 * host-filtered. Iframes are allowed here and then narrowed by
 * `EMBED_HOST_RE` below, which is the same check the backend applies.
 */

/** Tags an editor may produce. Keep in step with `ALLOWED_TAGS` in
 *  backend/app/shared/content/html_sanitizer.py. */
export const ALLOWED_TAGS: string[] = [
  // structure
  "p", "br", "hr", "div", "span", "section", "article", "header", "footer",
  "main", "aside", "nav", "figure", "figcaption", "details", "summary",
  "address",
  // headings
  "h1", "h2", "h3", "h4", "h5", "h6",
  // text
  "strong", "b", "em", "i", "u", "s", "strike", "del", "ins", "sub", "sup",
  "small", "mark", "abbr", "cite", "q", "code", "kbd", "samp", "pre", "var",
  "time", "bdi", "bdo", "wbr", "ruby", "rt", "rp",
  // lists
  "ul", "ol", "li", "dl", "dt", "dd",
  // quotes
  "blockquote",
  "q",
  // tables
  "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup",
  "col",
  // media
  "a", "img", "picture", "source", "video", "audio", "track",
  // oEmbed: permitted by tag, then narrowed to these hosts by EMBED_HOST_RE.
  // DOMPurify's tag list cannot see a src, which is why the two are separate.
  "iframe",
];

/** Attributes allowed on any tag.
 *
 *  This is the union of the server's per-tag map (ALLOWED_ATTRIBUTES) plus the
 *  iframe-only names. It used to be narrower, so an attribute the store
 *  accepts — `srcset` on an inserted image, `role` on a layout section — was
 *  visible in the editor and gone from the stored row.
 *  `check_editor_allowlists.py` compares the union in both directions. */
export const ALLOWED_ATTR: string[] = [
  // the server's "*" entry
  "class", "id", "title", "dir", "lang", "role",
  // `style` is allowed server-side and narrowed by ALLOWED_CSS_PROPERTIES
  // below. Without it the alignment buttons wrote a style that the very next
  // sanitise pass deleted, so they did nothing at all.
  "style",
  // a
  "href", "target", "rel", "name",
  // img / source
  "src", "alt", "width", "height", "loading", "decoding", "srcset", "sizes",
  // `media` pairs with `srcset` on <source>; without it a responsive picture
  // is reduced to one candidate by the editor but kept whole by the server.
  "media", "type",
  // video / audio / track
  "controls", "poster", "preload", "kind", "srclang", "label", "default",
  // tables
  "colspan", "rowspan", "headers", "scope", "abbr", "span",
  // lists
  "start", "reversed", "type", "value",
  // details, time
  "open", "datetime",
  // oEmbed iframes, narrowed to known hosts by EMBED_HOST_RE
  "frameborder", "allow", "allowfullscreen",
];

/** CSS properties the editor may keep in a `style` attribute.
 *  Mirrors ALLOWED_CSS_PROPERTIES in the backend sanitizer — the same list, so
 *  a style the editor renders survives the server instead of being dropped on
 *  save. Presentation only: nothing here can load or execute anything. */
export const ALLOWED_CSS_PROPERTIES: string[] = [
  "color", "background-color", "background", "font-size", "font-weight",
  "font-style", "font-family", "text-align", "text-decoration",
  "line-height", "letter-spacing", "margin", "margin-top",
  "margin-bottom", "margin-left", "margin-right", "padding",
  "padding-top", "padding-bottom", "padding-left", "padding-right",
  "border", "border-top", "border-bottom", "border-left", "border-right",
  "border-radius", "border-color", "border-width", "border-style",
  "width", "height", "max-width", "max-height", "min-width",
  "min-height", "display", "gap", "grid-template-columns",
  "flex-direction", "justify-content", "align-items", "opacity",
  "box-shadow", "overflow", "vertical-align", "white-space",
];

/**
 * Per-tag attributes, merged over the global list by the callers that need it
 * (DOMPurify takes a flat list, so this is for the ones that build a map).
 */
export const ALLOWED_ATTR_BY_TAG: Record<string, string[]> = {
  a: ["href", "name", "target", "rel", "title"],
  img: ["src", "alt", "width", "height", "loading", "class", "srcset", "sizes"],
  iframe: [
    "src", "width", "height", "title", "frameborder", "loading", "allow",
    "allowfullscreen",
  ],
};

/** Schemes a URL may use. */
export const ALLOWED_URI_REGEXP = /^(?:https?|mailto|tel|\/)/i;

/**
 * Providers whose embed markup may stay in stored content. Mirrors
 * `_EMBED_HOSTS` in the backend sanitizer; both must be https.
 */
export const EMBED_HOST_RE =
  /^https:\/\/(?:www\.)?(?:youtube\.com\/embed|youtube-nocookie\.com\/embed|aparat\.com\/video|twitch\.tv\/embed|instagram\.com\/embed)/i;

/** True when an iframe src is from a known provider. */
export function isAllowedEmbedSrc(src: string | null | undefined): boolean {
  return typeof src === "string" && EMBED_HOST_RE.test(src.trim());
}
