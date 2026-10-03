/**
 * Negative test for verify_content_srcset.mts — prove the check can fail.
 *
 * The check earned this the hard way: its first run found two real bugs in the
 * rewrite it was testing (a remote image given local candidates, and a
 * srcset invented for an extension-less path). A check that has never gone red
 * is not evidence, so the two breaks it exists to catch are kept here.
 *
 *   npx tsx scripts/wp-parity/negative_test_content_srcset.mts
 */

import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Anchored to this file, not process.cwd(): this test is invoked by hand from
// wherever the operator happens to be, and spawnSync inherits that cwd for the
// child, so a cwd-relative path made the whole thing work only from the root.
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const TARGET = join(ROOT, "frontend", "lib", "content-responsive-images.ts");
const CHECK = join(HERE, "verify_content_srcset.mts");

const MODES: Array<[string, string, string]> = [
  [
    "the rewrite is a no-op, so body images stay fixed-width",
    "  return html.replace(IMG_TAG, (tag) => {",
    "  if (html) return html;\n  return html.replace(IMG_TAG, (tag) => {",
  ],
  [
    "a candidate the backend never renders, which 404s in the browser",
    '  ["large", 1024],\n',
    '  ["huge", 3000],\n',
  ],
  [
    "a width that disagrees with the backend's registered width",
    '  ["medium", 300],\n',
    '  ["medium", 500],\n',
  ],
];

function run(): { code: number; out: string } {
  // spawnSync with shell, not execFileSync: on Windows `npx` resolves to
  // npx.cmd, and execFileSync cannot execute a .cmd directly — it fails with a
  // null status and no output, which reads here as "the check is red" and
  // would abort the test before it proved anything.
  const r = spawnSync("npx", ["tsx", CHECK], {
    cwd: ROOT,
    encoding: "utf-8",
    shell: true,
  });
  const out = `${r.stdout ?? ""}${r.stderr ?? ""}`;
  return { code: typeof r.status === "number" ? r.status : 1, out };
}

function main(): void {
  const original = readFileSync(TARGET, "utf-8");
  const restore = () => writeFileSync(TARGET, original, "utf-8");

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

    MODES.forEach(([label, old, replacement], i) => {
      // Line endings normalised: the file under test is checked out with CRLF
      // while the injected snippets are written with LF, so a raw `includes`
      // never matched and two of the three injections reported "the snippet
      // moved" — which reads as a stale test rather than as a line-ending
      // difference.
      const norm = (s: string) => s.split("\r\n").join("\n");
      const haystack = norm(original);
      if (!haystack.includes(norm(old))) {
        console.log(`FAIL: cannot inject "${label}" — the snippet moved. Update this test.`);
        process.exitCode = 2;
        return;
      }
      writeFileSync(TARGET, haystack.replace(norm(old), norm(replacement)), "utf-8");
      let result;
      try {
        result = run();
      } finally {
        restore();
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
    console.log("PASS: the srcset check fails on all three ways the rewrite can be wrong.");
  } finally {
    restore();
  }
}

main();
