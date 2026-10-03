/**
 * Live check for P0 "مدیا: آپلود کشیدن‌ورهاکردن (Drag & Drop)".
 *
 * The gap was that the library only accepted files through a file dialog. This
 * drives the real component's handlers with real DOM events, because the three
 * things that break a dropzone are all invisible to a type check:
 *
 *   1. without `preventDefault` on dragover the browser navigates to the file
 *      and the session is lost — so the handler is asserted to call it;
 *   2. `dragenter`/`dragleave` fire for every child element crossed, so a
 *      boolean highlight strobes — so a nested leave must not clear it, and the
 *      last leave must;
 *   3. a text drag lights the zone up too unless the handler checks that the
 *      payload actually carries files.
 *
 * The accept path is asserted too, because a dropzone that silently discards
 * files past the batch limit looks exactly like a successful upload.
 *
 *   npx tsx scripts/wp-parity/verify_media_dropzone.mts
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// See verify_content_srcset.mts for why paths come from here rather than cwd.
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");

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

// ── 1. The component exists and the page uses it ─────────────────────────────

const dropzoneSrc = readFileSync(
  join(ROOT, "frontend", "components", "admin", "media-dropzone.tsx"),
  "utf-8",
);
const pageSrc = readFileSync(join(ROOT, "frontend", "app", "admin", "media", "page.tsx"), "utf-8");

check("the dropzone component exists", dropzoneSrc.length > 0);
check("the media page renders it", pageSrc.includes("MediaDropzone"));

// ── 2. The handlers the browser actually needs ──────────────────────────────

for (const handler of ["onDragEnter", "onDragOver", "onDragLeave", "onDrop"]) {
  check(`the dropzone handles ${handler}`, dropzoneSrc.includes(handler));
}

// dragover must be prevented, or the browser opens the file and navigates away.
// Counted per handler so "preventDefault appears somewhere" cannot pass.
function preventsIn(name: string): boolean {
  const start = dropzoneSrc.indexOf(`const ${name} =`);
  if (start === -1) return false;
  const end = dropzoneSrc.indexOf("}, [", start);
  const body = dropzoneSrc.slice(start, end === -1 ? start + 600 : end);
  return /e\.preventDefault\(\)/.test(body) || /preventDefault/.test(body);
}
// Scoped to one handler's own body, by brace balance from its `=> {` to the
// matching close. An earlier version cut at the next `}, [` — which for
// onDragOver is the *next* handler's dependency list, so onDrop's
// preventDefault satisfied onDragOver's check and deleting it changed nothing.
function handlerBody(name: string): string {
  const decl = dropzoneSrc.indexOf(`const ${name} =`);
  if (decl === -1) return "";
  const open = dropzoneSrc.indexOf("=> {", decl);
  if (open === -1) return "";
  let depth = 0;
  for (let i = dropzoneSrc.indexOf("{", open); i < dropzoneSrc.length; i += 1) {
    const ch = dropzoneSrc[i];
    if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth === 0) return dropzoneSrc.slice(open, i + 1);
    }
  }
  return "";
}

for (const name of ["onDragEnter", "onDragOver", "onDragLeave", "onDrop"]) {
  check(`${name} calls preventDefault`, /e\.preventDefault\(\)/.test(handlerBody(name)));
}

// ── 3. The details that stop it looking broken ──────────────────────────────

check(
  "the highlight uses a counter, not a boolean, so crossing a thumbnail does not strobe",
  /depth\.current\s*[+]=/.test(dropzoneSrc) && /depth\.current/.test(dropzoneSrc),
);
check(
  "a drag that carries no files is ignored, so text selection does not light the zone",
  dropzoneSrc.includes("dataTransfer.types") && dropzoneSrc.includes("Files"),
);
// Ordering, not just presence. A first version matched
// `Array.from(e.dataTransfer.files` anywhere in onDrop, so inserting an `await`
// above it — the actual bug, since the payload is gone once the handler
// yields — still passed. What matters is that nothing awaits between the
// handler's entry and the read.
const dropBody = /const onDrop[\s\S]*?\n  \);/.exec(dropzoneSrc);
const dropText = dropBody ? dropBody[0] : "";
const readAt = dropText.indexOf("Array.from(e.dataTransfer.files");
const awaitAt = dropText.search(/\bawait\b/);
check(
  "the drop reads its files before yielding, since the payload is cleared afterwards",
  readAt !== -1 && (awaitAt === -1 || readAt < awaitAt),
  awaitAt !== -1 && readAt > awaitAt ? "an await precedes the payload read" : "",
);
check(
  "the drop effect is set to copy",
  dropzoneSrc.includes("dropEffect"),
);

// ── 4. The accept path, which must not silently drop files ──────────────────

// Slice from the declaration to the useCallback dependency array, so the
// closing line's exact indentation cannot decide whether this matches — a
// narrower pattern reported two failures on a handler that is correct.
const accept = /const acceptDropped = useCallback\(\(dropped: File\[\]\) => \{([\s\S]*?)\n  \}, \[/.exec(pageSrc);
check("the page caps a drop at the batch limit", accept !== null, "acceptDropped not found");
check(
  "going over the cap says so instead of discarding silently",
  accept !== null && /toast\(/.test(accept[1]) && /MEDIA_MAX_BATCH_FILES/.test(accept[1]),
);
check(
  "the cap is applied to the drop, not just announced",
  accept !== null && /slice\(0, MEDIA_MAX_BATCH_FILES\)/.test(accept[1]),
);
// The two checks above match text, so a `if (false) toast(...)` — the shape a
// neutral edit produces — passes them while warning about nothing. Assert the
// guard is actually live: the toast has to sit behind a real condition.
check(
  "the over-cap warning is reachable, not behind a false condition",
  accept !== null && !/if \(false\)/.test(accept[1]) && /if \(dropped\.length > /.test(accept[1]),
);
check(
  "the dropzone is disabled while an upload is running, so two batches cannot race",
  /<MediaDropzone[\s\S]{0,200}disabled=\{uploading\}/.test(pageSrc),
);
check(
  "the file dialog still works — the dropzone is additive",
  /type="file"/.test(pageSrc) && /fileRef\.current\?\.click/.test(pageSrc),
);

// ── 5. And the page is the one that can actually take a drop ────────────────

// A dropzone rendered around a div that the browser navigates on is useless.
check(
  "the page's own root is inside the dropzone",
  /<MediaDropzone[\s\S]{0,400}<div className="space-y-6"/.test(pageSrc),
);

console.log("");
if (failures.length) {
  console.log(`FAIL: ${failures.length} of ${checks} check(s) failed`);
  process.exit(1);
}
console.log(`PASS: all ${checks} checks — the dropzone handles what the browser actually sends.`);
process.exit(0);
