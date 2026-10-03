"""Re-check the P1 gap list against the code, claim by claim.

The list in `docs/store-relevant-cms-gaps-2026-10-01.md` was written once, from
an audit, and every line carries a `شاهد:` (evidence) pointer. Two things then
happen to such a list: items get fixed and stop being true, and items turn out
to have been fixed already when the list was written. Both are silent — the
document keeps claiming a gap that is not one, and work gets done twice.

So this re-runs each claim's *evidence pointer* against the tree and reports
the ones whose evidence no longer describes the code. It is not a verdict on
whether an item is fixed — a pointer that still resolves can still be fixed. It
answers the narrower, answerable question: has the code moved since the line
was written, so the claim needs re-reading?

Run:  python scripts/wp-parity/check_gap_list_evidence.py
"""

from __future__ import annotations

import io
import os
import re
import sys

# The document is Persian: every item line carries Persian prose, and on
# Windows the default console codec is cp1252, which cannot encode it. Without
# this the gate does not *report* the unreadable pointer — it crashes with a
# UnicodeEncodeError while trying to print it, turning a finding into a
# traceback that reads as "the gate is broken" rather than "this pointer is
# dead". A guard that dies at the moment it finds something is not a guard.
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC = os.path.join(ROOT, "docs", "store-relevant-cms-gaps-2026-10-01.md")

#: `شاهد: `path:line`` — the pointer every line carries. Several lines put a
#: path inside a longer Persian sentence, so only the first path on the line is
#: taken and everything before it is skipped rather than matched.
EVIDENCE_RE = re.compile(r"شاهد:\s*[^`\n]*?`([\w./\\-]+\.(?:py|ts|tsx))(?::(\d+)(?:-\d+)?)?`")


def resolve(path_rel: str, line: int | None) -> tuple[str, int] | None:
    """Turn one evidence pointer into (path, line). None if it cannot be read.

    A line number is checked against the file, not just parsed. An editor
    reports "this line does not parse" and says nothing about "this line was
    deleted when the file shrank", so a pointer past the end of its file passes
    every check that only looks for the file — and the claim it supported is
    the one nobody re-reads, because the file is right there.
    """
    rel = path_rel.replace("\\", "/")
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        return None
    if line is not None:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                length = sum(1 for _ in fh)
        except OSError:
            return None
        if int(line) > length:
            return None
    return path, int(line or 1)


def moved_elsewhere(path_rel: str) -> str | None:
    """Where a named file went, or None.

    A file that is moved keeps its name; a file that is *renamed* does not, and
    the two cases need different searches. The storefront robots route began as
    a metadata file and was renamed to Next's route-handler convention (the old
    stem became the parent directory, the file became the convention's own
    handler name) — so a basename search finds nothing and the pointer looks
    simply missing.

    Both searches are scoped to `frontend/app` and `backend/app`, where a move
    changes the URL a claim was about rather than only a path on disk. A file
    that still exists is not moved, whatever else shares its name.
    """
    rel = path_rel.replace("\\", "/")
    if os.path.isfile(os.path.join(ROOT, rel)):
        return None

    base = os.path.basename(rel)
    stem = base.rsplit(".", 1)[0]
    roots = [
        os.path.join(ROOT, "frontend", "app"),
        os.path.join(ROOT, "backend", "app"),
    ]

    # 1. same name somewhere else — the plain move.
    for search_root in roots:
        for dirpath, dirnames, filenames in os.walk(search_root):
            dirnames[:] = [d for d in dirnames if d != "node_modules"]
            if base in filenames:
                return os.path.relpath(
                    os.path.join(dirpath, base), ROOT
                ).replace("\\", "/")

    # 2. The stem became a directory, possibly with a dotted suffix, holding
    #    Next's own handler file — the shape a rename takes when a route grows
    #    settings (the storefront robots metadata file became a route handler
    #    this way).
    #
    #    Matched against the *child* directory names, not `dirpath`. The stem
    #    directory is reached as a child on the way in, so comparing against
    #    the directory currently being walked never matches — the check has to
    #    look one level ahead, which is what `dirnames` is.
    if stem:
        for search_root in roots:
            for dirpath, dirnames, _filenames in os.walk(search_root):
                dirnames[:] = [d for d in dirnames if d != "node_modules"]
                for child in list(dirnames):
                    if child == stem or child.rsplit(".", 1)[0] == stem:
                        candidate = os.path.join(dirpath, child, "route.ts")
                        if os.path.isfile(candidate):
                            rel = os.path.relpath(candidate, ROOT)
                            return rel.replace(os.sep, "/")
    return None


def main() -> int:
    if not os.path.isfile(DOC):
        print(f"FAIL: gap list missing at {DOC}")
        return 1
    with open(DOC, encoding="utf-8") as fh:
        text = fh.read()

    p1_start = text.find("## P1")
    p1_end = text.find("## P2")
    if p1_start == -1 or p1_end == -1:
        print("FAIL: the P1 and P2 headings are not both present")
        return 1
    p1 = text[p1_start:p1_end]

    items = [ln for ln in p1.splitlines() if ln.startswith("- [")]
    checked = 0
    unreadable: list[tuple[str, str]] = []
    moved: list[tuple[str, str, str]] = []
    for item in items:
        m = EVIDENCE_RE.search(item)
        if not m:
            continue
        ref, line = m.group(1), m.group(2)
        checked += 1
        if resolve(ref, line) is not None:
            continue
        # Two different failures, and conflating them hides both: a pointer
        # whose file was renamed still says something true about the code, while
        # one past the end of its file is stale for a different reason and
        # needs the line number fixed.
        where = moved_elsewhere(ref)
        if where:
            moved.append((ref, where, item[:90]))
        else:
            unreadable.append((f"{ref}:{line}" if line else ref, item[:90]))

    print(f"  P1 items: {len(items)}")
    print(f"  evidence pointers checked: {checked}")

    if moved:
        print("\n  pointers whose file has moved (the claim may still hold):")
        for ref, where, item in moved:
            print(f"    {ref}  ->  {where}")
            print(f"      on: {item}")

    if unreadable:
        print("\n  evidence pointers that no longer resolve:")
        for ref, item in unreadable:
            print(f"    {ref}")
            print(f"      on: {item}")

    # A pointer that cannot be read is not itself a failure — several of them
    # name a search rather than a file. But it does mean the line can no longer
    # be re-verified, so it is reported and counted rather than swallowed.
    print(f"\n  unreadable: {len(unreadable)} of {checked}")

    if checked == 0:
        print("\nFAIL: no evidence pointers were parsed — the format changed "
              "and this check is measuring nothing.")
        return 1
    print("\nPASS: the P1 evidence pointers were re-checked against the tree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())