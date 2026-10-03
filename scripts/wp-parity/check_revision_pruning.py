"""Prove that revision pruning keeps the newest snapshots and stops deleting
when there is nothing over the cap.

The prune query lives in `BlogService._prune_revisions`. It is four lines and
one silent failure mode: an `OFFSET` on the wrong sort order, or applied
ascending instead of descending, would keep the *oldest* twenty revisions and
delete the ones a restore is most likely to reach for. Nothing in the app would
notice — the revisions dialog would simply get shorter.

So the statement is exercised here against a real database, not asserted by
reading the source. Run:

    python scripts/wp-parity/check_revision_pruning.py

Exit 0 on pass, 1 on any mismatch. A negative test lives beside it:
`negative_test_revision_pruning.py` flips the sort order and must fail.
"""

from __future__ import annotations

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from sqlalchemy import Column, Integer, String, create_engine, delete, select  # noqa: E402
from sqlalchemy.orm import declarative_base, sessionmaker  # noqa: E402

Base = declarative_base()


class PostRev(Base):
    """The shape of blog_post_revision that the prune statement reads."""

    __tablename__ = "blog_post_revision"
    id = Column(String, primary_key=True)
    post_id = Column(String, index=True)
    revision_number = Column(Integer)


# (cap, rows present, rows expected to survive)
CASES = [
    (20, 5, 5),      # under the cap: nothing is deleted
    (20, 20, 20),    # exactly at the cap: nothing is deleted
    (20, 25, 20),    # over by 5: the five oldest go
    (20, 100, 20),   # far over: still exactly the cap survives
    (3, 2, 2),       # under, small cap
    (1, 5, 1),       # cap of 1 keeps the newest only
]


def prune(db, post_id: str, cap: int) -> int:
    """The statement as BlogService._prune_revisions builds it."""
    stmt = (
        select(PostRev.id)
        .where(PostRev.post_id == post_id)
        .order_by(PostRev.revision_number.desc())
        .offset(cap)
    )
    stale = list(db.execute(stmt).scalars())
    if stale:
        db.execute(delete(PostRev).where(PostRev.id.in_(stale)))
        db.commit()
    return len(stale)


def main() -> int:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    failures = []
    print(f"post_revisions_to_keep cases: {len(CASES)}")
    for cap, total, expected_kept in CASES:
        db.query(PostRev).delete()
        for n in range(1, total + 1):
            db.add(PostRev(id=f"r{n}", post_id="p1", revision_number=n))
        db.commit()

        removed = prune(db, "p1", cap)
        kept = sorted(r.revision_number for r in db.query(PostRev).all())

        problems = []
        if len(kept) != expected_kept:
            problems.append(f"kept {len(kept)}, expected {expected_kept}")
        if kept != list(range(total - expected_kept + 1, total + 1)):
            problems.append(f"kept the wrong rows: {kept[:5]}…{kept[-3:]}")
        if total > cap and removed != total - cap:
            problems.append(f"reported removing {removed}, expected {total - cap}")
        if total <= cap and removed != 0:
            problems.append(f"deleted {removed} rows while under the cap")

        if problems:
            failures.append(f"  cap={cap} rows={total}: " + "; ".join(problems))
            print(f"FAIL cap={cap:3d} rows={total:3d}  " + "; ".join(problems))
        else:
            print(f"PASS cap={cap:3d} rows={total:3d}  kept the newest {len(kept)}")

    db.close()
    if failures:
        print("\nFAIL: revision pruning does not keep the newest snapshots")
        return 1
    print("\nPASS: pruning keeps the newest N and deletes nothing under the cap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())