/**
 * Permalink helpers (mirror of backend/app/shared/permalinks.py).
 *
 * Pure string logic only — no fetch, no React — so the same rules can serve
 * link building in server/client components AND URL resolution in the
 * middleware without dragging anything into the edge bundle.
 * Matching is segment-based string parsing: no dynamically-composed RegExp,
 * so operator input can never change how a pattern is compiled.
 */

export interface PermalinkParts {
  postname: string;
  post_id: string;
  year: string;
  monthnum: string;
  day: string;
  category: string;
  author: string;
}

export interface RoutingConfig {
  permalink_structure: string;
  category_base: string;
  tag_base: string;
  enabled_locales: string;
  default_locale: string;
  /** Public origin, for anything that must be absolute (JSON-LD, feeds). */
  site_url?: string;
  /** Configured store name, used as the publisher in structured data. */
  blogname?: string;
}

export const DEFAULT_ROUTING: RoutingConfig = {
  permalink_structure: "/blog/%postname%/",
  category_base: "category",
  tag_base: "tag",
  enabled_locales: "fa",
  default_locale: "fa",
  site_url: "",
  blogname: "فروشگاه",
};

const STRUCTURE_TOKENS = [
  "postname",
  "post_id",
  "year",
  "monthnum",
  "day",
  "category",
  "author",
] as const;
type StructureToken = (typeof STRUCTURE_TOKENS)[number];

const STRUCTURE_RE = /^\/(?:[\w\-/%]+\/)*[\w\-/%]*$/;
const TAG_RE = /%(\w+)%/g;
const DATE_ORDER = ["year", "monthnum", "day"] as const;
const isDigits = (s: string): boolean => /^\d+$/.test(s);

export function isDefaultStructure(structure: string): boolean {
  const s = (structure || "").trim();
  return s === "" || s === "/blog/%postname%/";
}

/** Problems with a proposed structure; empty array = valid. Mirrors the
 *  backend so the admin screen and the URL resolver agree on what is legal. */
export function validateStructure(structure: string): string[] {
  // matchAll() clones the regex *including its current lastIndex*, so the
  // shared global TAG_RE must start from zero or a previous match in this
  // module leaves validation seeing only the tags after that point.
  TAG_RE.lastIndex = 0;
  const s = (structure || "").trim();
  if (!s.startsWith("/")) return ["ساختار باید با / شروع شود."];
  if (!STRUCTURE_RE.test(s)) {
    return ["فقط حروف، رقم، -, _, / و تگ‌های %...% مجاز است."];
  }
  const tags = [...s.matchAll(TAG_RE)].map((m) => m[1] ?? "");
  const unknown = tags.filter((t) => !STRUCTURE_TOKENS.includes(t as StructureToken));
  if (unknown.length) return [`تگ ناشناخته: ${unknown.join(", ")}`];
  if (tags.length === 0) return ["حداقل یک تگ %...% لازم است."];
  if (!tags.includes("postname") && !tags.includes("post_id")) {
    return ["ساختار باید %postname% یا %post_id% داشته باشد."];
  }
  const positions = new Map(tags.map((t, i) => [t, i]));
  const dp = DATE_ORDER.filter((d) => positions.has(d)).map(
    (d) => positions.get(d) as number,
  );
  if (dp.some((p, i) => i > 0 && p < (dp[i - 1] as number))) {
    return ["ترتیب تاریخ: سال → ماه → روز."];
  }
  return [];
}

/** Fill a structure with a post's parts; empty parts collapse separators. */
export function buildPostPath(structure: string, parts: PermalinkParts): string {
  let path = structure;
  for (const [token, value] of Object.entries(parts)) {
    path = path.split(`%${token}%`).join(value);
  }
  path = path.replace(/\/{2,}/g, "/");
  return path.endsWith("/") ? path : `${path}/`;
}

/** Public URL of one post under the configured structure. The default
 *  structure keeps the canonical file-tree path (no middleware involved). */
export function postHref(
  structure: string,
  post: {
    slug: string;
    id?: string;
    published_at?: string | null;
    category_slug?: string | null;
    author_slug?: string | null;
  },
): string {
  if (isDefaultStructure(structure)) return `/blog/${post.slug}`;
  if (validateStructure(structure).length > 0) return `/blog/${post.slug}`;
  const d = post.published_at ? new Date(post.published_at) : new Date();
  return buildPostPath(structure, {
    postname: post.slug,
    post_id: post.id ?? "",
    year: String(d.getFullYear()).padStart(4, "0"),
    monthnum: String(d.getMonth() + 1).padStart(2, "0"),
    day: String(d.getDate()).padStart(2, "0"),
    category: post.category_slug ?? "",
    // WordPress substitutes the author's nicename. Ours is users.author_slug;
    // when it is absent the token is dropped, because an empty segment would
    // render /blog//my-post/ and 404.
    author: post.author_slug ?? "",
  });
}

export function categoryHref(routing: RoutingConfig, slug: string): string {
  return archiveHref(routing, "category", slug);
}

export function tagHref(routing: RoutingConfig, slug: string): string {
  return archiveHref(routing, "tag", slug);
}

/**
 * Archive URL for a taxonomy term. The default bases ("category"/"tag") keep
 * the canonical file-tree path `/blog/category/<slug>`; a customised base
 * yields `/<base>/<slug>`, which the middleware rewrites back onto the
 * physical route. An unconfigured install therefore links byte-identically
 * to before, and a customised one actually changes URLs.
 */
export function archiveHref(
  routing: RoutingConfig,
  kind: "category" | "tag",
  slug: string,
): string {
  const base = (kind === "category" ? routing.category_base : routing.tag_base) || kind;
  if (base === kind) return `/blog/${kind}/${slug}`;
  return `/${base}/${slug}`;
}

/**
 * Date-archive URL, e.g. `/blog/archive/2026` or `/blog/archive/2026/09`.
 *
 * Kept here for the same reason as `archiveHref`: a hard-coded path in a
 * component is a path nobody can find or change in one place. Month is always
 * two digits so `/2026/9` and `/2026/09` cannot both exist.
 */
export function dateArchiveHref(year: number, month?: number | null): string {
  const y = String(year).padStart(4, "0");
  return month === undefined || month === null
    ? `/blog/archive/${y}`
    : `/blog/archive/${y}/${String(month).padStart(2, "0")}`;
}

function matchSegment(
  structSeg: string,
  pathSeg: string,
  out: Partial<PermalinkParts>,
): boolean {
  TAG_RE.lastIndex = 0;
  const tagMatch = TAG_RE.exec(structSeg);
  if (!tagMatch) return structSeg === pathSeg;
  const tag = tagMatch[1] as string;
  if (!STRUCTURE_TOKENS.includes(tag as StructureToken)) return false;
  const [before = "", after = ""] = structSeg.split(`%${tag}%`);
  if (!pathSeg.startsWith(before) || !pathSeg.endsWith(after)) return false;
  const value = pathSeg.slice(before.length, pathSeg.length - after.length);
  const shapeOk =
    tag === "year"
      ? value.length === 4 && isDigits(value)
      : tag === "monthnum" || tag === "day"
        ? value.length >= 1 && value.length <= 2 && isDigits(value)
        : tag === "post_id"
          ? isDigits(value)
          : value.length > 0;
  if (!shapeOk) return false;
  out[tag as keyof PermalinkParts] = value;
  return true;
}

/** Match an incoming pathname against the configured structure. Returns the
 *  captured parts, or null when the path is not a structured post URL. */
export function matchPermalink(
  pathname: string,
  structure: string,
): PermalinkParts | null {
  if (isDefaultStructure(structure)) return null;
  if (validateStructure(structure).length > 0) return null;
  const ss = structure.replace(/\/{2,}/g, "/").split("/").filter(Boolean);
  const ps = pathname.split("/").filter(Boolean);
  if (ss.length !== ps.length) return null;
  const parts: Partial<PermalinkParts> = {};
  for (let i = 0; i < ss.length; i += 1) {
    if (!matchSegment(ss[i] as string, ps[i] as string, parts)) return null;
  }
  if (!parts.postname && !parts.post_id) return null;
  return {
    postname: parts.postname ?? "",
    post_id: parts.post_id ?? "",
    year: parts.year ?? "",
    monthnum: parts.monthnum ?? "",
    day: parts.day ?? "",
    category: parts.category ?? "",
    author: parts.author ?? "",
  };
}

/**
 * First path segments owned by the physical storefront file tree. A custom
 * structure like ``/%category%/%postname%/`` would otherwise also match
 * ``/account/orders`` or ``/products/<slug>``; those paths must never be
 * rewritten, so resolution skips them outright.
 */
export const RESERVED_ROOTS: ReadonlySet<string> = new Set([
  "account",
  "admin",
  "api",
  "_next",
  "uploads",
  "media",
  "icons",
  "fonts",
  "products",
  "cart",
  "checkout",
  "blog",
  "login",
  "register",
  "compare",
  "favorites",
  "search",
  "payment",
  "mock-gateway",
  "rewards",
  "returns",
  "wholesale",
  "contact",
  "about",
  "faq",
  "terms",
  "privacy",
  "newsletter",
]);
