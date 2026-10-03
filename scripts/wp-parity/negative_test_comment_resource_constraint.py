"""Negative test for check_comment_resource_constraint.

The gate guards a failure that looks like a working feature: `supports_comments`
consulted, the entry validated, the comment built — and the INSERT refused by a
constraint that never heard of a custom post type. The error a moderator sees
names a constraint, which answers none of "can I comment here".

So the sabotage restores the old two-shape constraint — which is the exact
state the code shipped in — and the gate must notice.

  A. Replace the constraint with the original, which rejects `content_entry`.
  B. Replace it with something permissive (`CHECK (true)`). This is the other
     direction: the gate must not pass a constraint that was merely widened,
     because a blog post with a `resource_id` that disagrees with its
     `post_id` would then be storable and every read that joins the two would
     silently disagree.

Run:  python scripts/wp-parity/negative_test_comment_resource_constraint.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(HERE, "check_comment_resource_constraint.py")

NAME = "ck_blog_comments_resource_consistency"

TWO_SHAPES = (
    "CHECK (((((resource_type)::text = 'blog_post'::text) "
    "AND (post_id IS NOT NULL) AND (resource_id = post_id)) "
    "OR (((resource_type)::text = 'cms_page'::text) "
    "AND (post_id IS NULL) AND (resource_id IS NOT NULL))))"
)

PERMISSIVE = "CHECK (true)"

APPLY = r"""
import asyncio, sys
sys.path.insert(0, %r)
import app.main
from sqlalchemy import text
from app.core.database.session import _build_engine, async_sessionmaker

async def go():
    e = _build_engine()
    async with async_sessionmaker(e)() as db:
        await db.execute(text('ALTER TABLE blog_comments DROP CONSTRAINT IF EXISTS ' + %r))
        await db.execute(text('ALTER TABLE blog_comments ADD CONSTRAINT ' + %r + ' ' + %r))
        await db.commit()
    await e.dispose()

asyncio.run(go())
"""

RESTORE = r"""
import asyncio, sys
sys.path.insert(0, %r)
import app.main
from sqlalchemy import text
from app.core.database.session import _build_engine, async_sessionmaker

GOOD = (
    "CHECK ("
    "  ((resource_type = 'blog_post'"
    "    AND post_id IS NOT NULL AND resource_id = post_id)"
    "   OR ((resource_type IN ('cms_page', 'content_entry'))"
    "       AND post_id IS NULL AND resource_id IS NOT NULL))"
    ")"
)

async def go():
    e = _build_engine()
    async with async_sessionmaker(e)() as db:
        await db.execute(text('ALTER TABLE blog_comments DROP CONSTRAINT IF EXISTS ' + %r))
        await db.execute(text('ALTER TABLE blog_comments ADD CONSTRAINT ' + %r + ' ' + GOOD))
        await db.commit()
    await e.dispose()

asyncio.run(go())
"""


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def set_constraint(definition: str) -> tuple[int, str]:
    script = APPLY % (
        os.path.join(ROOT, "backend"), NAME, NAME, definition
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def restore() -> tuple[int, str]:
    script = RESTORE % (os.path.join(ROOT, "backend"), NAME, NAME)
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code.")
        print(out.strip()[-800:])
        return 1
    print("gate passes on the real code")

    ok = True
    for label, definition in (
        ("A: restore the two-shape constraint (no content_entry)", TWO_SHAPES),
        ("B: widen the constraint to CHECK (true)", PERMISSIVE),
    ):
        rc_apply, apply_out = set_constraint(definition)
        if rc_apply != 0:
            print(f"FAIL: {label} — could not apply the constraint.")
            print(apply_out.strip()[-500:])
            ok = False
            continue

        rc_broken, out_broken = run_gate()
        # Restore unconditionally, before any `continue` — a `continue` inside
        # a `finally` swallows the in-flight exception and is a SyntaxWarning
        # in recent Python, so the restore lives here instead.
        rc_restore, restore_out = restore()
        if rc_restore != 0:
            print(f"FAIL: {label} — the constraint was not restored.")
            print(restore_out.strip()[-500:])
            ok = False
            continue

        rc_after, out_after = run_gate()
        if rc_after != 0:
            print(f"FAIL: {label} — the gate did not pass again after restoring.")
            print(out_after.strip()[-600:])
            ok = False
            continue
        if rc_broken == 0:
            print(f"FAIL: {label} still passed. The gate cannot see it.")
            ok = False
            continue

        caught = [ln.strip() for ln in out_broken.splitlines()
                  if ln.strip().startswith("- ")]
        print(f"  {label} -> caught")
        for line in caught[:2]:
            print(f"      {line[:140]}")

    if not ok:
        return 1
    print("\nPASS: the gate sees both a constraint that is too narrow and one "
          "that is too permissive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())