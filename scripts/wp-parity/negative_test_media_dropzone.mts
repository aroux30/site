/**
 * Negative test for verify_media_dropzone.mts — prove the check can fail.
 *
 * Each mode below is a way a dropzone looks fine in review and is unusable in
 * a browser: the browser navigates to the dropped file, the highlight strobes
 * as the pointer crosses a thumbnail, text selection lights the whole library,
 * or files past the batch limit vanish with no message.
 *
 *   npx tsx scripts/wp-parity/negative_test_media_dropzone.mts
 */

import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const DROPZONE = join(ROOT, "frontend", "components", "admin", "media-dropzone.tsx");
const PAGE = join(ROOT, "frontend", "app", "admin", "media", "page.tsx");
const CHECK = join(HERE, "verify_media_dropzone.mts");

// (label, file, snippet that must be present, replacement)
// Rebuilt by scripts/wp-parity/rebuild_dropzone_modes.py from the live files, so a
// reformat cannot leave the test injecting a snippet that no longer exists.
// Rebuilt by scripts/wp-parity/rebuild_dropzone_modes.py from the live files, so a
// reformat cannot leave the test injecting a snippet that no longer exists.
// Rebuilt by scripts/wp-parity/rebuild_dropzone_modes.py from the live files, so a
// reformat cannot leave the test injecting a snippet that no longer exists.
// (label, target, snippet that must be present, replacement)
// The target is "DROPZONE" or "PAGE", resolved below — naming the symbol keeps
// this block readable and the file map the only place that has to change.
//
// Two of these snippets contain `${...}`, which is a template placeholder in a
// double-quoted string, so they are written as template literals with
// String.raw: the `$` carries no meaning there and `\` is not an escape
// sequence, so the text lands exactly as the file has it. Writing them as
// ordinary strings made the test inject a snippet the page never contained, and
// it failed with a misleading "cannot inject".
const MODES: Array<[string, string, string, string]> = [
  [
    "dragover without preventDefault, so the browser opens the dropped file",
    "DROPZONE",
    `      // Without preventDefault the browser navigates to the dropped file and
      // the whole session is lost.
      e.preventDefault();
`,
    "",
  ],
  [
    "the highlight reduced to a boolean, so crossing a thumbnail strobes it",
    "DROPZONE",
    "      depth.current += 1;\n      setOver(true);",
    "      setOver(true);",
  ],
  [
    "any drag lights the zone, including a text selection",
    "DROPZONE",
    '      if (!Array.from(e.dataTransfer.types).includes("Files")) return;\n',
    "",
  ],
  [
    "the drop reads its files after yielding, when the payload is already gone",
    "DROPZONE",
    `      // Read the files synchronously, before the reset above and any state
      // update: the payload is cleared once the drop handler yields.
      const files = Array.from(e.dataTransfer.files ?? []);
`,
    "      await Promise.resolve();\n      const files = Array.from(e.dataTransfer.files ?? []);",
  ],
  [
    "files past the batch limit disappear silently",
    "PAGE",
    `      toast({
        title: \`حداکثر \${MEDIA_MAX_BATCH_FILES} فایل در هر بار\`,
        description: \`\${MEDIA_MAX_BATCH_FILES} فایل اول آپلود می‌شود؛ \${dropped.length - MEDIA_MAX_BATCH_FILES} فایل نادیده گرفته شد.\`,
`,
    `      void 0;
    if (false) {
      toast({
        title: \`حداکثر \${MEDIA_MAX_BATCH_FILES} فایل در هر بار\`,
        description: \`\${MEDIA_MAX_BATCH_FILES} فایل اول آپلود می‌شود؛ \${dropped.length - MEDIA_MAX_BATCH_FILES} فایل نادیده گرفته شد.\`,
`,
  ],
  [
    "the zone is not disabled during an upload, so two batches can race",
    "PAGE",
    "      onFiles={acceptDropped}\n      disabled={uploading}\n",
    "      onFiles={acceptDropped}\n",
  ],
];




function run(): { code: number; out: string } {
  // shell: true because `npx` is npx.cmd on Windows and execFileSync cannot
  // launch a .cmd directly — it returns a null status and no output, which
  // reads here as a red check.
  const r = spawnSync("npx", ["tsx", CHECK], {
    cwd: ROOT,
    encoding: "utf-8",
    shell: true,
  });
  return { code: typeof r.status === "number" ? r.status : 1, out: `${r.stdout ?? ""}${r.stderr ?? ""}` };
}

function main(): void {
  const originals = new Map(
    [DROPZONE, PAGE].map((p) => [p, readFileSync(p, "utf-8")]),
  );
  const restore = () => {
    for (const [p, s] of originals) writeFileSync(p, s, "utf-8");
  };

  try {
    const baseline = run();
    if (baseline.code !== 0) {
      console.log(
        "FAIL: the check is red on the current tree, so a red result below would prove nothing.\n" +
          baseline.out.slice(-600),
      );
      process.exitCode = 2;
      return;
    }
    console.log(`[0/${MODES.length + 1}] check passes on the current tree`);

    MODES.forEach(([label, file, old, replacement], i) => {
      // The modes name their target symbolically ("DROPZONE" / "PAGE") rather
      // than by path, so the block stays readable and the file map below is the
      // only place that has to change if a file moves.
      const target = file === "DROPZONE" ? DROPZONE : PAGE;
      const src = originals.get(target)!;
      // Compare with line endings normalised. This file is checked out with
      // CRLF while the injected snippets are written with LF, so a raw
      // `includes` never matched and every injection reported "the snippet
      // moved" — which reads as a stale test rather than as a line-ending
      // difference, and cost several rounds of guessing.
      const norm = (s: string) => s.replace(/\r\n/g, "\n");
      const haystack = norm(src);
      if (!haystack.includes(norm(old))) {
        console.log(`FAIL: cannot inject "${label}" — the snippet moved. Update this test.`);
        process.exitCode = 2;
        return;
      }
      // Write back through the same normalised text, so the file under test keeps
      // the line endings it had and `restore` restores it byte for byte.
      writeFileSync(target, haystack.replace(norm(old), norm(replacement)), "utf-8");
      let result;
      try {
        result = run();
      } finally {
        writeFileSync(target, src, "utf-8");
      }
      if (result.code === 0) {
        console.log(`FAIL: the check passed while ${label}.`);
        process.exitCode = 1;
        return;
      }
      console.log(`[${i + 1}/${MODES.length + 1}] correctly fails on: ${label}`);
    });

    if (process.exitCode) return;

    const final = run();
    if (final.code !== 0) {
      console.log(`FAIL: the check is still red after restore.\n${final.out.slice(-400)}`);
      process.exitCode = 1;
      return;
    }
    console.log(`[${MODES.length + 1}/${MODES.length + 1}] green again after restore`);
    console.log("");
    console.log("PASS: the dropzone check fails on all six ways a dropzone is unusable.");
  } finally {
    restore();
  }
}

main();