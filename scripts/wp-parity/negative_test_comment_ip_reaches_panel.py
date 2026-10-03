"""Negative test for check_comment_ip_reaches_panel.

Two directions, because the two failures are opposites and the gate has to
catch both:

  A. Remove the IP from the moderation table. This is the regression the gate
     was written for — a moderator moderating spam loses the one signal that
     tells two comments came from the same place, and nothing raises.
  B. Add it to the *public* schema. That is the security half: the public list
     is unauthenticated, so this hands every anonymous visitor the address of
     every commenter. A gate that only checked presence would pass.

Run:  python scripts/wp-parity/negative_test_comment_ip_reaches_panel.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, "check_comment_ip_reaches_panel.py")
PANEL = os.path.join(ROOT, "frontend", "components", "admin", "blog",
                     "comments-moderation-tab.tsx")
SCHEMA = os.path.join(ROOT, "backend", "app", "modules", "blog", "schemas", "blog.py")

# The panel renders the IP in a block that also carries the URL; matched as a
# whole so the sabotage removes the row and not half of it.
PANEL_BLOCK_RE = re.compile(r"[ \t]*\{c\.author_ip && \(.*?\n[ \t]*\)\}\n", re.S)

# `author_url` sits on the public schema; inserting before it puts the IP in
# the same class, which is exactly the shape of the leak.
PUBLIC_ANCHOR = "    # Publicly rendered as a mailto link, so it is not PII the way an email is."


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def edit(path: str, label: str, fn) -> bool:
    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    try:
        changed = fn(original)
        if changed == original:
            print(f"FAIL: {label} — nothing changed, so the gate was tested "
                  f"against a no-op.")
            return False
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(changed)
        try:
            rc, out = run_gate()
        finally:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(original)
        rc_after, _ = run_gate()
        if rc_after != 0:
            print(f"FAIL: {label} — the gate did not pass again after restoring.")
            return False
        if rc == 0:
            print(f"FAIL: {label} still passed. The gate cannot see it.")
            return False
        caught = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("- ")]
        print(f"  {label} -> caught")
        for line in caught[:2]:
            print(f"      {line[:150]}")
        return True
    finally:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(original)


def main() -> int:
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code.")
        print(out.strip()[-700:])
        return 1
    print("gate passes on the real code")

    def drop_from_panel(text: str) -> str:
        new, n = PANEL_BLOCK_RE.subn("", text, count=1)
        if n != 1:
            raise AssertionError(f"panel block matched {n} times")
        return new

    def leak_to_public(text: str) -> str:
        if PUBLIC_ANCHOR not in text:
            raise AssertionError("public-schema anchor not found")
        return text.replace(
            PUBLIC_ANCHOR,
            "    author_ip: str | None = None\n" + PUBLIC_ANCHOR, 1)

    ok = True
    for label, path, fn in (
        ("A: remove the IP from the moderation table", PANEL, drop_from_panel),
        ("B: add the IP to the public schema", SCHEMA, leak_to_public),
    ):
        try:
            ok = edit(path, label, fn) and ok
        except AssertionError as exc:
            print(f"FAIL: {label} — {exc}")
            ok = False

    if not ok:
        return 1
    print("\nPASS: the gate goes red both when the IP disappears from the panel "
          "and when it leaks to the public schema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())