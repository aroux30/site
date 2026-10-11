/**
 * Guard: no application code may gate an action on `window.confirm`.
 *
 * `window.confirm` returns `false` immediately, with no dialog, inside a
 * sandboxed iframe that lacks `allow-modals` — the way an embedded preview, a
 * webview, or any framed admin surface runs. A handler written as
 *
 *     if (!confirm("...")) return;
 *
 * then returns before issuing any request, showing no error and no toast: the
 * button looks dead.
 *
 * That is not hypothetical. On 2026-10-07 the blog list's delete button did
 * exactly this in the embedded preview while the same code worked in a
 * top-level tab, and 30+ other call sites across the admin had the same
 * exposure. The replacement is `useConfirm()` from
 * `components/ui/confirm-dialog.tsx`, which draws its own dialog and therefore
 * needs no browser modal permission.
 *
 * The check is deliberately source-based: the failure only reproduces in a
 * framed document, so a runtime test in jsdom would not catch a regression.
 */
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = join(process.cwd());

/** Directories that hold application source. */
const SCAN = ["app", "components", "hooks", "lib"];

/** Files allowed to mention `confirm(` for a reason other than the browser modal. */
const ALLOW = [
  // The replacement component itself: it defines `confirm` and passes it
  // around; it never calls `window.confirm`.
  "components/ui/confirm-dialog.tsx",
];

function walk(dir: string, out: string[] = []): string[] {
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    if (name === "node_modules" || name === ".next" || name.startsWith(".next-")) continue;
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(name)) out.push(full);
  }
  return out;
}

/**
 * Find `window.confirm(...)` or a bare `confirm(...)` call that is not one of
 * our own `useConfirm()` handles.
 *
 * A line is a violation when it calls confirm but is not:
 *  - a `useConfirm` binding (`const confirm = useConfirm()`),
 *  - an awaited call of our helper (`await confirm({`),
 *  - a reference inside a comment,
 *  - the local `confirm` defined by delete-user-dialog's own handler, which is
 *    a component-local function of the same name (identified by its `() =>`
 *    arrow with no arguments on a `const confirm = async () =>` line).
 */
function findViolations(source: string): { line: number; text: string }[] {
  const out: { line: number; text: string }[] = [];
  const lines = source.split("\n");
  lines.forEach((raw, i) => {
    const line = raw.trim();
    if (!line || line.startsWith("//") || line.startsWith("*") || line.startsWith("/*")) return;
    // Either the explicit global, or a bare `confirm(` call. `window.confirm(`
    // must match too — the leading `\b` after stripping is what a `[^.\w]`
    // guard would miss, because `.` is exactly the character before it.
    const isWindow = /\bwindow\s*\.\s*confirm\s*\(/.test(line);
    const isBare = /(^|[^.\w$])confirm\s*\(/.test(line);
    if (!isWindow && !isBare) return;
    // Our own helpers and bindings.
    if (line.includes("useConfirm")) return;
    if (/await confirm\s*\(/.test(line)) return;
    if (/^const confirm\s*=/.test(line)) return;
    // Our helper always takes an options object; the browser modal takes a
    // string. A call whose next non-space character is `{` is the helper —
    // this covers the `return confirm({...})` form used by an async helper.
    if (/confirm\s*\(\s*\{/.test(line)) return;
    // The local `confirm` in delete-user-dialog.tsx is a plain function, not
    // the browser modal; it takes no string argument.
    if (/^const confirm = async \(\) =>/.test(line)) return;
    if (/onClick=\{\(\) => void confirm\(\)\}/.test(line)) return;
    out.push({ line: i + 1, text: line.slice(0, 110) });
  });
  return out;
}

describe("no browser confirm in application code", () => {
  it("has no window.confirm call site", () => {
    const files = SCAN.flatMap((d) => walk(join(ROOT, d)));
    const offenders: string[] = [];
    for (const f of files) {
      const rel = relative(ROOT, f).replace(/\\/g, "/");
      if (ALLOW.includes(rel)) continue;
      for (const v of findViolations(readFileSync(f, "utf-8"))) {
        offenders.push(`${rel}:${v.line}: ${v.text}`);
      }
    }
    expect(
      offenders,
      `window.confirm is silently a no-op in a sandboxed iframe, so these\n` +
        `actions look dead in an embedded preview. Use useConfirm() from\n` +
        `@/components/ui/confirm-dialog instead:\n\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  it("the detector actually catches the pattern it forbids", () => {
    // A guard that cannot fail is not a guard. Feed it the exact shape that
    // shipped, and require a finding.
    const sample = [
      "  const handleTrash = async (post) => {",
      '    if (!confirm(`مقاله «${post.title}» حذف شود؟`)) return;',
      "  };",
    ].join("\n");
    expect(findViolations(sample).length).toBe(1);

    const windowForm = '    if (!window.confirm("حذف شود؟")) return;';
    expect(findViolations(windowForm).length).toBe(1);

    // And it must NOT flag the replacement.
    expect(findViolations("    const ok = await confirm({ title: 'x' });").length).toBe(0);
    expect(findViolations("  const confirm = useConfirm();").length).toBe(0);
  });
});
