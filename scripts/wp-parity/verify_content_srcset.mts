/**
 * Live check for P0 "مدیا: تصاویر واکنش‌گرا (srcset) در محتوا".
 *
 * A unit test on the transform would pass while the chain stayed broken, which
 * is the dominant failure mode in this project's gap list: a field present in a
 * schema, a model and a form, and nowhere else. So this drives the whole path
 * the reader hits:
 *
 *   stored body HTML → cleanHtml (sanitize + embed policy) → responsive rewrite
 *
 * and asserts the srcset survives all three steps, that an unsafe image is
 * still removed by the sanitizer, and — the part a frontend test cannot see —
 * that the candidate filenames this emits match the names the backend actually
 * writes to disk.
 *
 * Run it with tsx, from any directory:
 *   npx tsx scripts/wp-parity/verify_content_srcset.mts
 *
 * `node --experimental-strip-types` is NOT the runner here: this file imports
 * `sanitize-html.ts`, whose dependency `sanitize-html` is CommonJS, and node's
 * type-stripping ESM loader resolves that import differently than tsx does. The
 * docstring used to offer both; the first one failed, so only the one that
 * works is documented.
 */

import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Derived from this file's own location, not process.cwd(). These checks are
// run by hand, by CI, and from other directories, and a check that only works
// from the repo root is a check nobody runs. `verify_content_srcset` opened
// `backend/...` relative to the cwd, so running it from frontend/ looked for
// `frontend/backend/...` and failed on a file that does exist.
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");

import { withResponsiveImages } from "../../frontend/lib/content-responsive-images.ts";
import { cleanHtml } from "../../frontend/lib/sanitize-html.ts";

const failures: string[] = [];
let checks = 0;

function check(label: string, ok: boolean, detail = ""): void {
  checks += 1;
  if (ok) {
    console.log(`PASS: ${label}`);
  } else {
    failures.push(`${label}${detail ? ` — ${detail}` : ""}`);
    console.log(`FAIL: ${label}${detail ? ` — ${detail}` : ""}`);
  }
}

// ── 1. The rewrite, on its own ────────────────────────────────────────────────

const plain = withResponsiveImages(
  '<img src="/uploads/media/abc123.png" alt="a" />',
);
check(
  "a local body image gains a srcset",
  plain.includes("srcset="),
  plain,
);
check(
  "the srcset offers the three widths the backend renders",
  plain.includes("-medium.png 300w") &&
    plain.includes("-medium_large.png 768w") &&
    plain.includes("-large.png 1024w"),
  plain,
);
check("the original src is left in place", plain.includes('src="/uploads/media/abc123.png"'), plain);
check("sizes accompanies it", plain.includes('sizes="'), plain);

const untouched = withResponsiveImages(
  '<img srcset="/a.png 1x" src="/a.png" />',
);
check(
  "an img that already declares a srcset is left alone",
  untouched === '<img srcset="/a.png 1x" src="/a.png" />',
  untouched,
);

const dataUri = withResponsiveImages('<img src="data:image/png;base64,AAAA" />');
check("a data URI is not rewritten", !dataUri.includes("srcset"), dataUri);

const remote = withResponsiveImages('<img src="https://cdn.example.com/x.png" />');
check(
  "a remote image is not given local candidates",
  !remote.includes("srcset"),
  remote,
);

const noExt = withResponsiveImages('<img src="/uploads/media/plainfile" />');
check(
  "a src with no extension is left alone rather than given an invented path",
  !noExt.includes("srcset"),
  noExt,
);

const withQuery = withResponsiveImages('<img src="/uploads/media/abc.png?v=2" />');
check(
  "a query string survives into the candidates",
  withQuery.includes("-medium.png?v=2 300w"),
  withQuery,
);

// ── 2. The whole chain: sanitize, then rewrite ────────────────────────────────

const body = [
  '<p>متن</p>',
  '<img src="/uploads/media/def456.jpg" alt="cover" />',
  '<iframe src="https://evil.example.com/x"></iframe>',
].join("");

const rendered = cleanHtml(body);
check("the srcset survives sanitization", rendered.includes("srcset="), rendered.slice(0, 200));
check("the img itself survived", rendered.includes("/uploads/media/def456.jpg"), rendered.slice(0, 200));
check(
  "the embed-host policy still runs after the image rewrite",
  !rendered.includes("evil.example.com"),
  rendered.slice(0, 200),
);

// An author-supplied srcset must be respected, not overwritten.
const authorChose = cleanHtml('<img src="/uploads/media/x.png" srcset="/custom.png 640w" />');
check(
  "an author's own srcset is preserved through the chain",
  authorChose.includes("/custom.png 640w") && !authorChose.includes("-medium.png"),
  authorChose,
);

// ── 3. The other side: do those filenames exist on disk? ─────────────────────

// The frontend names candidates; the backend names what it writes. If the two
// disagree the browser 404s on every breakpoint, which is worse than the fixed
// src we replaced — so the agreement is asserted here, against the backend's
// own source rather than a copy of it.
const processor = readFileSync(
  join(ROOT, "backend", "app", "modules", "media", "application", "image_processor.py"),
  "utf-8",
);
const sizeMatch = /IMAGE_SIZES\s*=\s*\{([\s\S]*?)\n\}/.exec(processor);
const backendSizes = sizeMatch
  ? [...sizeMatch[1].matchAll(/"(\w+)":\s*\{\s*"width":\s*(\d+)/g)].map((m) => ({
      name: m[1],
      width: Number(m[2]),
    }))
  : [];
check("the backend's IMAGE_SIZES could be read", backendSizes.length >= 3, processor.slice(0, 80));

const derived = /return f"\{stem\}-\{size_name\}\{ext\}"/.exec(processor);
check("the backend names derived files as <stem>-<size><ext>", derived !== null);

const emitted = [...plain.matchAll(/-(\w+)\.png (\d+)w/g)].map((m) => ({
  name: m[1],
  width: Number(m[2]),
}));
check(
  "every candidate this emits is a size the backend registers",
  emitted.every((e) => backendSizes.some((b) => b.name === e.name && b.width === e.width)),
  `emitted ${JSON.stringify(emitted)} vs backend ${JSON.stringify(backendSizes)}`,
);
check(
  "the width written into the srcset matches the backend's registered width",
  emitted.length > 0 &&
    emitted.every((e) => {
      const b = backendSizes.find((x) => x.name === e.name);
      return b !== undefined && b.width === e.width;
    }),
  JSON.stringify(emitted),
);

// ── 4. Real files: are the derived sizes actually written? ───────────────────

// The rewrite is only correct if the candidates exist. A srcset entry that
// 404s is worse than no srcset at all — the browser retries the original at
// every breakpoint — so this asks the filesystem, not the source.
const uploadsRoot = join(ROOT, "backend", "media");
let verifiedOnDisk = 0;
let completeSets = 0;

try {
  const wanted = new Set(["medium", "medium_large", "large"]);
  const byStem = new Map<string, Set<string>>();

  for (const dir of ["media"]) {
    const full = join(uploadsRoot, dir);
    let entries: string[] = [];
    try {
      entries = readdirSync(full);
    } catch {
      continue;
    }
    for (const name of entries) {
      const m = /^(.*?)-(\w+)\.(png|jpe?g|gif|webp|avif)$/i.exec(name);
      if (!m || !wanted.has(m[2])) continue;
      const stem = m[1];
      if (!byStem.has(stem)) byStem.set(stem, new Set());
      byStem.get(stem)!.add(m[2]);
    }
  }

  for (const sizes of byStem.values()) {
    verifiedOnDisk += sizes.size;
    const missing = [...wanted].filter((w) => !sizes.has(w));
    if (missing.length === 0) completeSets += 1;
  }

  // Reported rather than asserted: an empty library has no derived files to
  // count, and a fresh checkout has none until something is uploaded. The
  // naming agreement above is the part that must hold unconditionally.
  console.log(
    `      (on disk: ${verifiedOnDisk} derived file(s) across ${completeSets} complete set(s))`,
  );
  if (completeSets > 0) {
    check(
      "at least one uploaded image has all three srcset candidates on disk",
      completeSets > 0,
    );
  } else {
    console.log("SKIP: no uploaded image with derived sizes to verify against.");
  }
} catch (e) {
  console.log(`      (could not read the uploads directory: ${String(e)})`);
}

console.log("");
if (failures.length) {
  console.log(`FAIL: ${failures.length} of ${checks} check(s) failed`);
  process.exit(1);
}
console.log(`PASS: all ${checks} checks — srcset survives the chain and matches the backend.`);
process.exit(0);
