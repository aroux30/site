/**
 * Rewrite `<img>` tags in stored body HTML so each one carries a `srcset`.
 *
 * P0 "مدیا: تصاویر واکنش‌گرا (srcset) در محتوا". A body image was rendered with
 * one fixed URL, so a phone downloaded the desktop-sized file: a 4000px hero for
 * a 360px viewport, on every page load, for every reader.
 *
 * The four sizes already exist on disk — the uploader writes them and the
 * delete sweep reclaims them — so this is a wiring gap, not a rendering
 * project. The naming here mirrors the backend's
 * `derived_size_name` (`<stem>-<size><ext>`); when the two drift the browser
 * requests 404s, which is why `scripts/wp-parity/verify_content_srcset.mts`
 * asserts both sides agree by reading the backend's own source rather than a
 * copy of it.
 *
 * Deliberately not done here: measuring the image. Emitting a candidate that
 * does not exist would 404, so a size is only listed when the pattern is one
 * the upload path produces. A 404 on a srcset entry is worse than no srcset:
 * the browser retries the original at every breakpoint.
 */

/** Widths the backend renders, from IMAGE_SIZES. Order is ascending. */
const SRCSET_WIDTHS: ReadonlyArray<readonly [suffix: string, width: number]> = [
  ["medium", 300],
  ["medium_large", 768],
  ["large", 1024],
];

/** The width an `<img>` without a srcset is assumed to be, for the `sizes`
 *  attribute. Body content is a single ~768px column on the storefront. */
const DEFAULT_SIZES = "(max-width: 768px) 100vw, 768px";

function splitName(src: string): { dir: string; stem: string; ext: string } | null {
  if (!src) return null;
  // Split on the last slash and the last dot of the file part, so a query
  // string or a dotted directory name cannot shift the extension.
  const queryAt = src.search(/[?#]/);
  const clean = queryAt === -1 ? src : src.slice(0, queryAt);
  const suffix = queryAt === -1 ? "" : src.slice(queryAt);
  const slash = clean.lastIndexOf("/");
  const dir = slash === -1 ? "" : clean.slice(0, slash + 1);
  const name = clean.slice(slash + 1);
  const dot = name.lastIndexOf(".");
  if (dot <= 0) {
    // No extension: the derived sizes are named `<stem>-<size><ext>`, and
    // without an ext there is nothing to append the suffix to. Emitting
    // `plainfile-medium` would be a path the upload never produces — a 404 on
    // every breakpoint, which is worse than the fixed src it replaced.
    return null;
  }
  return { dir, stem: name.slice(0, dot), ext: name.slice(dot) + suffix };
}

/** True for srcs we must not rewrite: inline data URIs and remote hosts. */
function isRewritable(src: string): boolean {
  if (!src || src.startsWith("data:")) return false;
  // The derived sizes exist on *our* disk, under our uploads root. A src on
  // another host has no `-medium` sibling — writing one points the browser at
  // a URL the third party does not serve. This also caught a real bug: the
  // first version rewrote `https://cdn.example.com/x.png` into three 404s.
  if (/^https?:\/\//i.test(src)) return false;
  // Any other scheme (javascript:, mailto:, …) is not a media path either.
  if (/^[a-z][a-z0-9+.-]*:/i.test(src)) return false;
  return true;
}

function buildSrcset(src: string): string | null {
  const parts = splitName(src);
  if (!parts) return null;
  return SRCSET_WIDTHS.map(([suffix, width]) => `${parts.dir}${parts.stem}-${suffix}${parts.ext} ${width}w`)
    .join(", ");
}

const IMG_TAG = /<img\b[^>]*>/gi;
const SRC_ATTR = /\ssrc\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))/i;
const SRCSET_ATTR = /\ssrcset\s*=/i;
const SIZES_ATTR = /\ssizes\s*=/i;

/**
 * Add `srcset` and `sizes` to every local `<img>` in `html`.
 *
 * An `<img>` that already has a srcset is left alone: the author, or another
 * transform, already decided the candidates, and overwriting them would throw
 * away a deliberate choice.
 */
export function withResponsiveImages(html: string): string {
  if (!html || !html.includes("<img")) return html;

  return html.replace(IMG_TAG, (tag) => {
    if (SRCSET_ATTR.test(tag)) return tag;

    const m = SRC_ATTR.exec(tag);
    const src = m ? (m[2] ?? m[3] ?? m[4] ?? "") : "";
    if (!isRewritable(src)) return tag;

    const srcset = buildSrcset(src);
    if (!srcset) return tag;

    // `sizes` is a hint, not a promise: with it absent the browser assumes
    // 100vw and picks the largest candidate on a wide screen even when the
    // image sits in a narrow column.
    const withSrcset = tag.replace(SRC_ATTR, ` src="${src}" srcset="${srcset}"`);
    return SIZES_ATTR.test(withSrcset) ? withSrcset : `${withSrcset} sizes="${DEFAULT_SIZES}"`;
  });
}

export { SRCSET_WIDTHS, DEFAULT_SIZES };
