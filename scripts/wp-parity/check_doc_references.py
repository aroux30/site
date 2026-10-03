"""Guard: no docstring may point at a file that does not exist.

Found by a peer session while reviewing the srcset work: `content-responsive-images.ts`
credited `check_content_srcset.py` for the naming agreement, and no such file
had ever existed — the check is `verify_content_srcset.mts`. A dead reference in
a comment is worse than no comment, because it reads as a pointer to the check
that protects the code, and the next person follows it and finds nothing.

So this walks the backticked filenames in the modules this project has been
adding under frontend/lib and scripts/wp-parity, and resolves each one.

    python scripts/wp-parity/check_doc_references.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Where a backticked `name.ext` might live, searched in order. A bare filename
# is looked up in each; a path-like token is also tried under these roots,
# because the codebase writes `lib/sanitize-html.ts` meaning `frontend/lib/...`.
SEARCH_ROOTS = (
    ROOT / "scripts" / "wp-parity",
    # `run_all_gates.py` sits directly in scripts/, not under wp-parity/. A gate
    # that references it by name was reported dead while the file was right
    # there — a guard that cries wolf on a real file is one that gets ignored.
    ROOT / "scripts",
    ROOT / "backend" / "scripts",
    ROOT / "frontend" / "lib",
    ROOT / "backend" / "app",
)

# Directories a path-like token is relative to, besides the repo root. Without
# these the check reported 14 false failures on references that resolve fine —
# `lib/sanitize-html.ts` is a real file at frontend/lib/sanitize-html.ts, and a
# guard that cries wolf is one that gets ignored.
PATH_PREFIX_ROOTS = (
    ROOT,
    ROOT / "frontend",
    ROOT / "frontend" / "app",
    ROOT / "frontend" / "components",
    ROOT / "backend",
    ROOT / "backend" / "app",
    ROOT / "backend" / "app" / "modules",
)

# A bare filename inside a module's own folder: `privacy-admin.ts` next to
# `privacy.ts` means the sibling. Searching only fixed roots reported two false
# failures for files that sit in the same directory as the reference.
EXTRA_BARE_ROOTS = (
    ROOT / "frontend" / "lib" / "api",
    ROOT / "frontend" / "lib" / "editor",
    ROOT / "frontend" / "app" / "admin",
    ROOT / "backend" / "app" / "modules" / "rbac" / "application",
    ROOT / "backend" / "app" / "modules" / "media" / "application",
    ROOT / "backend" / "app" / "modules" / "blog" / "application",
    ROOT / "backend" / "app" / "modules" / "content" / "application",
)

# Every layer of every module, so a bare filename resolves wherever it lives.
# Discovered rather than listed: the entries in EXTRA_BARE_ROOTS are what was
# there when this check was written, and every module added since then reported
# its own bare filenames as dead references — which is the worst way for a
# dead-reference guard to fail, because the tempting fix is to silence it and the
# honest response is to delete the file it points at. `store_name.py` was
# reported dead for exactly this reason: a real file, in a module nobody had
# added to the list.
LAYER_ROOTS = tuple(
    sorted(
        d
        for m in (ROOT / "backend" / "app" / "modules").glob("*")
        if m.is_dir()
        for d in (m, *(m / layer for layer in ("application", "domain", "api", "schemas")))
        if d.is_dir()
    )
)

SCANNED_GLOBS = (
    "frontend/lib/*.ts",
    "frontend/lib/**/*.ts",
    "scripts/wp-parity/*.py",
    "scripts/wp-parity/*.mts",
    "backend/scripts/*.py",
)

# This file is excluded: its own docstring names the dead references it exists to
# explain (a real one, plus `admin/layout.tsx` as an example of a relative
# mention), so it would always report itself. The same applies to the negative
# test, whose injected examples are dead names on purpose — without this a
# self-describing test suite reports its own fixtures as findings.
SELF = Path(__file__).name
NEGATIVE_TEST = "negative_test_doc_references.py"

# A backticked token that looks like a filename: has an extension, no spaces, no
# slashes (a path reference is allowed to have slashes and is checked separately),
# and is not a type or a config key.
BACKTICKED = re.compile(r"`([A-Za-z0-9_.-]+\.(?:py|mts|ts|tsx))`")

# `check_admin_nav.py` and friends are written without their folder; a token
# with a slash is a path and is resolved relative to the repo root instead.
PATHY = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|mts|ts|tsx))`")


#: Placeholder stems used in prose to mean "a file of this kind", not a real
#: file. `check_foo.py` in a gate's docstring explains the naming convention; it
#: is the same class as an elided path — a description, not a pointer. Matching
#: is on the whole stem so a real file that merely contains "foo" is unaffected.
PLACEHOLDER_STEMS = {"check_foo", "check_x", "foo", "bar", "baz", "example"}


def resolvable(name: str, source: Path) -> bool:
    # An elided path (`.../domain/models.py`) is shorthand, not a claim about a
    # file that should exist at a knowable place. Skipping it is the difference
    # between a check people run and one they disable.
    if name.startswith("..."):
        return True
    if name.rsplit(".", 1)[0].lower() in PLACEHOLDER_STEMS:
        return True
    if "/" in name:
        # Repo-relative, then under the usual roots, then relative to the
        # file doing the referring. `admin/layout.tsx` inside
        # scripts/wp-parity/check_admin_nav.py means frontend/app/admin/layout.tsx
        # to the author, not a path from the repo root — without the last rule
        # every relative mention reads as dead.
        candidates = [base / name for base in PATH_PREFIX_ROOTS]
        candidates.append(source.parent / name)
        return any(c.is_file() for c in candidates)
    return any(
        (root / name).is_file()
        for root in (*SEARCH_ROOTS, *EXTRA_BARE_ROOTS, *LAYER_ROOTS)
    )


def main() -> int:
    failures: list[str] = []
    scanned = 0

    for pattern in SCANNED_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file():
                continue
            if path.name in (SELF, NEGATIVE_TEST):
                continue
            scanned += 1
            src = path.read_text(encoding="utf-8", errors="replace")
            for token in set(PATHY.findall(src)):
                if not resolvable(token, path):
                    rel = path.relative_to(ROOT).as_posix()
                    failures.append(
                        f"{rel} mentions `{token}`, which does not exist — a dead "
                        f"reference reads as a pointer to the check that protects "
                        f"this code, and the next person follows it to nothing"
                    )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d dead file reference(s)." % len(failures))
        return 1

    print("PASS: %d file(s) scanned, every backticked filename resolves." % scanned)
    return 0


if __name__ == "__main__":
    sys.exit(main())