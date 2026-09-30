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

/** Attributes allowed on any tag. */
export const ALLOWED_ATTR: string[] = [
  "href", "src", "alt", "title", "class", "id", "target", "rel", "dir", "lang",
  "width", "height", "frameborder", "allowfullscreen", "allow", "loading",
  "colspan", "rowspan", "scope", "open", "datetime", "cite", "controls",
  "poster", "preload", "kind", "srclang", "default",
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
