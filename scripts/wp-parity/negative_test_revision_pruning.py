"""Negative test for check_revision_pruning: prove the check can fail.

A gate that has never failed is indistinguishable from a gate that cannot. This
monkeypatches the prune statement to the one plausible mistake — sorting
ascending, so the offset keeps the *oldest* rows — and requires the checker to
report failure. Exit 0 only when the checker is actually able to fail.

    python scripts/wp-parity/negative_test_revision_pruning.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "check_revision_pruning.py")

spec = importlib.util.spec_from_file_location("rev_prune", TARGET)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from sqlalchemy import select  # noqa: E402


def broken_prune(db, post_id: str, cap: int) -> int:
    """The same prune with the sort reversed — keeps the oldest N instead."""
    from sqlalchemy import delete

    stmt = (
        select(mod.PostRev.id)
        .where(mod.PostRev.post_id == post_id)
        .order_by(mod.PostRev.revision_number.asc())  # the injected mistake
        .offset(cap)
    )
    stale = list(db.execute(stmt).scalars())
    if stale:
        db.execute(delete(mod.PostRev).where(mod.PostRev.id.in_(stale)))
        db.commit()
    return len(stale)


def main() -> int:
    original = mod.prune
    mod.prune = broken_prune
    try:
        rc = mod.main()
    finally:
        mod.prune = original

    if rc == 0:
        print(
            "\nFAIL: the checker passed with an ascending prune. It cannot detect "
            "keeping the oldest revisions, so it is not a gate."
        )
        return 1
    print("\nPASS: the checker failed on the injected mistake, so it is a real gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())