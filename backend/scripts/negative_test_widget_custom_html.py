"""Negative test: the custom_html widget check can actually fail.

A verification script that only ever prints PASS is a gate that cannot fail, and
a gate that cannot fail is not a gate. This breaks each property the check
depends on, one at a time, and requires the check to go red for the stated
reason.

The two directions matter equally and they are opposites:

  - a sanitizer that is *removed* lets a script reach the database, and the
    storefront — which now renders that value as markup — executes it on a page
    every visitor loads
  - a sanitizer that is *too aggressive* eats the markup the widget exists for,
    and the store is back to rendering text by another name

A check that only tests the first passes on the second, because a feature nobody
can use and a feature nobody can attack look the same to a test that only looks
for scripts.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parents[1]
CHECK = BACKEND / "scripts" / "verify_widget_custom_html.py"
WIDGETS = BACKEND / "app" / "shared" / "content" / "widgets.py"
SANITIZER = BACKEND / "app" / "shared" / "content" / "html_sanitizer.py"
FRONTEND = BACKEND.parent / "frontend" / "components" / "layout" / "widget-area.tsx"

# (name, file, original, broken, expected substring in the check's output)
CASES: list[tuple[str, Path, str, str, str]] = [
    (
        "the write path stops sanitizing — the stored-XSS the gap invites",
        WIDGETS,
        "        areas[area_id][\"widgets\"] = _sanitise_widgets(widgets)",
        "        areas[area_id][\"widgets\"] = widgets",
        "survived into the database",
    ),
    (
        # An allowlist swapped for "everything except <script>". It reads like a
        # sanitizer and passes any check that only looks for script tags — while
        # every onclick, every javascript: URL and every iframe walks straight
        # into a value the storefront now renders.
        # The allowlist replaced by a one-tag denylist. It reads like a sanitizer
        # and passes any check that only looks for script tags — while every
        # onclick, every javascript: URL and every iframe walks straight into a
        # value the storefront now renders. Unioning `script` into the allowlist
        # would not do it: bleach still drops everything else, so the payloads
        # stay inert and the injection measures nothing.
        "the allowlist becomes a denylist of script tags only",
        SANITIZER,
        "        tags=_EMBED_ALLOWED_TAGS,",
        '        tags={"script"},',
        # A one-tag denylist has two symptoms, and the check reports the second
        # one first: the payload survives *and* every legitimate tag is gone. Both
        # are the defect, and asserting the one that is easy to miss is the point —
        # a check that only looked for `<script>` would call this sanitized.
        "legitimate markup lost",
    ),
    (
        "the sanitizer is replaced by a plain return",
        WIDGETS,
        "            config[\"content\"] = sanitize_html(config[\"content\"])",
        "            config[\"content\"] = config[\"content\"]",
        "survived into the database",
    ),
    (
        "a text widget gets sanitized too, mangling prose that was never markup",
        WIDGETS,
        '        if widget.get("type") != "custom_html":\n            cleaned.append(dict(widget))\n            continue',
        "        if False:\n            cleaned.append(dict(widget))\n            continue",
        "came back as",
    ),
    (
        # The other half of the same change: a sanitizer with no renderer does not
        # fix the gap, it reverts it. This injection puts the widget back to
        # rendering its own source, which is what the check must notice — the
        # opposite failure from a missing sanitizer, and the one a script-only
        # check cannot see.
        "the storefront renders the widget as text again",
        FRONTEND,
        "        <div\n"
        '          className="custom-html-widget text-sm leading-relaxed"\n'
        "          dangerouslySetInnerHTML={{ __html: text }}\n"
        "        />",
        "        <p className=\"whitespace-pre-line text-sm leading-relaxed text-muted-foreground\">\n"
        "          {text}\n"
        "        </p>",
        "still renders custom_html as text",
    ),
]


def run_check() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECK)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=BACKEND,
        env={**os.environ, "PYTHONPATH": "."},
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    saved: dict[Path, str] = {}
    for _, path, _, _, _ in CASES:
        if path not in saved:
            saved[path] = path.read_text(encoding="utf-8")

    try:
        return _run(saved)
    finally:
        # The outermost restore, so a run that exits before the loop cannot leave
        # an injected defect on disk and make the next run fail for an unrelated
        # reason.
        for path, original in saved.items():
            if path.read_text(encoding="utf-8") != original:
                path.write_text(original, encoding="utf-8")
                print("restored %s" % path.name)


def _run(saved: dict[Path, str]) -> int:
    print("baseline (unbroken tree):")
    code, out = run_check()
    if code != 0:
        print(out)
        print(
            "FAIL: the check does not pass on the unbroken tree, so a red run below "
            "would mean nothing"
        )
        return 1
    print("  PASS as expected")
    print("")

    failures: list[str] = []
    for name, path, original, broken, expected in CASES:
        source = saved[path]
        if original not in source:
            failures.append(
                "%s: the marker to break is not in %s, so this case would prove "
                "nothing -- update it for the current source" % (name, path.name)
            )
            continue
        path.write_text(source.replace(original, broken, 1), encoding="utf-8")
        try:
            code, out = run_check()
        finally:
            path.write_text(source, encoding="utf-8")

        if code == 0:
            failures.append("%s: the check still passed" % name)
            print("  FAIL %s -- the check still passed" % name)
        elif expected not in out:
            failures.append(
                "%s: the check went red, but not for this reason -- expected %r in "
                "the output" % (name, expected)
            )
            print("  FAIL %s -- red for the wrong reason" % name)
            print("    " + out.strip().replace("\n", "\n    "))
        else:
            print("  PASS %s -> check went red for the right reason" % name)

    code, out = run_check()
    if code != 0:
        print(out)
        failures.append("the check is red again after restoring every file")
    else:
        print("")
        print("PASS: the tree is green again after every injection was reverted.")

    if failures:
        print("")
        for f in failures:
            print("FAIL: %s" % f)
        return 1
    print("")
    print("PASS: every defect this check targets makes it go red, for its own reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())