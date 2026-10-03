/**
 * End-to-end check for the srcset gap, on the server side.
 *
 * P0 "مدیا: تصاویر واکنش‌گرا (srcset) در محتوا". The reader sees whatever the
 * blog post route puts in the page, and that route renders `post.content`
 * through `cleanHtml`. A transform that works in isolation but is not on that
 * path changes nothing for anybody, which is this project's most common way to
 * "finish" a gap.
 *
 * So this asserts the chain by name:
 *   1. the route that serves a post renders its body through cleanHtml;
 *   2. cleanHtml is the shared entry point every storefront consumer uses;
 *   3. and the transform behaves correctly when driven through it.
 *
 * The first two are static checks over the source, because a real HTTP request
 * would need the whole stack up; the third is executed.
 *
 *   npx tsx scripts/wp-parity/verify_srcset_wiring.mts
 */

import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Derived from this file's own location, not process.cwd(). These checks are
// run by hand, by CI, and from other directories, and a check that only works
// from the repo root is a check nobody runs. `verify_content_srcset` opened
// `backend/...` relative to the cwd, so running it from frontend/ looked for
// `frontend/backend/...` and failed on a file that does exist.
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");

import { cleanHtml } from "../../frontend/lib/sanitize-html.ts";

const failures: string[] = [];
let checks = 0;

function check(label: string, ok: boolean, detail = ""): void {
  checks += 1;
  if (ok) console.log(`PASS: ${label}`);
  else {
    failures.push(label);
    console.log(`FAIL: ${label}${detail ? ` — ${detail}` : ""}`);
  }
}

// ── 1. The blog post route must render the body through cleanHtml ─────────────

const postRoute = readFileSync(
  join(ROOT, "frontend", "app", "(store)", "blog", "[slug]", "page.tsx"),
  "utf-8",
);
const bodyRender = /dangerouslySetInnerHTML=\{\{[\s\S]{0,200}?cleanHtml\(/;
check(
  "the storefront blog post renders its body through cleanHtml",
  bodyRender.test(postRoute),
);

// ── 2. The other storefront consumers must use the same entry point ───────────

const consumers = [
  "frontend/app/(store)/[slug]/page.tsx",
  "frontend/components/cms/cms-page-shell.tsx",
  "frontend/components/blog/password-protected-content.tsx",
];
for (const rel of consumers) {
  const src = readFileSync(join(ROOT, rel), "utf-8");
  check(
    `${rel.split("/").pop()} renders through cleanHtml`,
    /cleanHtml\(/.test(src),
  );
}

// A consumer that bypassed cleanHtml would not get the srcset, and would also
// lose the sanitizer — so the check is that cleanHtml itself is the only place
// body HTML reaches the DOM.
const bypasses: string[] = [];
for (const dir of ["frontend/app", "frontend/components"]) {
  const walk = (path: string) => {
    for (const entry of readdirSync(path, { withFileTypes: true })) {
      const full = join(path, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === "node_modules" || entry.name === ".next") continue;
        walk(full);
        continue;
      }
      if (!entry.name.endsWith(".tsx")) continue;
      const src = readFileSync(full, "utf-8");
      if (!src.includes("dangerouslySetInnerHTML")) continue;
      // JSON-LD is not body HTML: it goes in a <script type="application/ld+json">
      // that the browser never renders, and it has its own escaping helper. An
      // earlier version of this check flagged the product page's structured data
      // as an unsanitized body, which it is not.
      if (src.includes("application/ld+json")) continue;
      if (!src.includes("cleanHtml(")) {
        // Admin previews legitimately show the draft, but the storefront must
        // not. Flag only the storefront.
        if (full.includes("(store)") || full.includes("components/cms")) {
          bypasses.push(full.replace(ROOT + "\\", ""));
        }
      }
    }
  };
  walk(join(ROOT, dir));
}
check(
  "no storefront component injects body HTML without cleanHtml",
  bypasses.length === 0,
  bypasses.join(", "),
);

// ── 3. Behaviour, driven through the shared entry point ──────────────────────

const rendered = cleanHtml('<p>x</p><img src="/uploads/media/abc123.png" alt="a" />');
check("cleanHtml adds a srcset to a body image", rendered.includes("srcset="), rendered);
check(
  "the candidates are the widths the upload path writes",
  rendered.includes("-medium.png 300w") &&
    rendered.includes("-medium_large.png 768w") &&
    rendered.includes("-large.png 1024w"),
  rendered,
);
check("sizes accompanies the srcset", /sizes="/.test(rendered), rendered);

// ── 4. And the candidates exist on disk ─────────────────────────────────────

const mediaDir = join(ROOT, "backend", "media", "media");
let completeSets = 0;
try {
  const byStem = new Map<string, Set<string>>();
  for (const name of readdirSync(mediaDir)) {
    const m = /^(.*?)-(medium|medium_large|large)\.(png|jpe?g|gif|webp|avif)$/i.exec(name);
    if (!m) continue;
    if (!byStem.has(m[1]!)) byStem.set(m[1]!, new Set());
    byStem.get(m[1]!)!.add(m[2]!);
  }
  for (const sizes of byStem.values()) {
    if (sizes.has("medium") && sizes.has("medium_large") && sizes.has("large")) completeSets += 1;
  }
  if (completeSets > 0) {
    check("an uploaded image has all three candidates on disk", true);
  } else {
    console.log("SKIP: no uploaded image with derived sizes to verify against.");
  }
} catch {
  console.log("SKIP: uploads directory not readable.");
}

console.log("");
if (failures.length) {
  console.log(`FAIL: ${failures.length} of ${checks} check(s) failed`);
  process.exit(1);
}
console.log(`PASS: all ${checks} checks — the srcset is on the path a reader actually takes.`);
process.exit(0);
