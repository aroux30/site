"""Negative test for check_pending_badge_wired.

The failure this guards is a *silent disconnect*: the endpoint keeps working,
the fixture keeps passing, and no badge appears — or one appears showing zero
because the count was never loaded. Neither is visible from the backend, which
is why this gate reads the consumer chain at all.

  A. Remove the badge from the admin bar — the endpoint survives, and the
     feature is gone.
  B. Drop the `!== null` guard. The badge then renders 0 before the first
     response arrives, telling a moderator the queue is empty when nobody has
     checked yet. This is the wrong-direction failure, and it looks fine.
  C. Remove the permission gate from the hook, so every admin polls an endpoint
     that 403s them.

Run:  python scripts/wp-parity/negative_test_pending_badge_wired.py
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
GATE = os.path.join(HERE, "check_pending_badge_wired.py")
HOOK = os.path.join(ROOT, "frontend", "hooks", "use-pending-comment-count.ts")
BAR = os.path.join(ROOT, "frontend", "components", "layout", "admin-bar.tsx")

BADGE_RE = re.compile(
    r"[ \t]*\{pendingCommentCount !== null && pendingCommentCount > 0 && \(.*?\n[ \t]*\)\}\n",
    re.S,
)


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

    def drop_badge(text: str) -> str:
        new, n = BADGE_RE.subn("", text, count=1)
        if n != 1:
            raise AssertionError(f"badge block matched {n} times")
        return new

    def drop_unknown_guard(text: str) -> str:
        new, n = BADGE_RE.subn(
            "{pendingCommentCount > 0 && (\n"
            "              <span>{pendingCommentCount}</span>\n"
            "            )}\n",
            text, count=1)
        if n != 1:
            raise AssertionError(f"badge block matched {n} times")
        return new

    def drop_permission(text: str) -> str:
        old = """    const canModerate =
      user?.is_superuser === true ||
      user?.permissions?.includes("blog:moderate_comments") ||
      user?.permissions?.includes("blog:write");"""
        if old not in text:
            raise AssertionError("the permission gate is not in the expected shape")
        return text.replace(old, "    const canModerate = true;", 1)

    ok = True
    for label, path, fn in (
        ("A: remove the badge from the admin bar", BAR, drop_badge),
        ("B: drop the unknown-count guard", BAR, drop_unknown_guard),
        ("C: remove the permission gate", HOOK, drop_permission),
    ):
        try:
            ok = edit(path, label, fn) and ok
        except AssertionError as exc:
            print(f"FAIL: {label} — {exc}")
            ok = False

    if not ok:
        return 1
    print("\nPASS: the gate goes red when the badge is gone, when it lies about "
          "an unknown count, and when it polls without permission.")
    return 0


if __name__ == "__main__":
    sys.exit(main())