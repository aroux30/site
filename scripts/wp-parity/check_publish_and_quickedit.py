"""Editing behaviour that has no visible surface when it breaks.

Publication dates, quick-edit's post format, the page tree, term editing and
term attachment: each one of these was reachable in the database and absent
(or half-wired) in the panel, so an editor had no way to correct one.

Both were reachable in the database and absent from the panel: `published_at`
was accepted by the update schema but no form sent it, and `post_format` was in
neither the quick-edit allowlist nor its dialog. So an editor who needed to
correct a date or relabel a post as a gallery had to open the full editor and,
for the date, publish and then edit again.

This runs the two behavioural fixtures against the project's own database and
fails if either stops holding. It is deliberately a database test and not a
source grep: the failures these guard against are behavioural — a date that is
accepted and then silently overwritten by the publish branch, or a bad format
that takes the whole save down with it — and reading the source shows neither.

Requires the local Postgres. It skips (exit 0) when the fixtures are absent, so
a checkout without them is not made red.

    python scripts/wp-parity/check_publish_and_quickedit.py
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The fixtures live in `.p1-tests` at the repository root. Resolved by walking
# up from this file rather than by counting `..`: a wrong count silently
# pointed somewhere else, the directory check found nothing, and the gate
# answered SKIP with exit 0 — a green run that tested nothing. Walking up
# until the marker directory appears cannot drift that way.
def _repo_root() -> str:
    d = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(d, ".p1-tests")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    # Fall back to the documented layout so the error names a real path.
    return os.path.normpath(os.path.join(HERE, "..", ".."))


FIXTURES = os.path.join(_repo_root(), ".p1-tests")
SCRIPTS = ("pubdate_test.py", "quickedit_test.py", "page_tree_test.py", "taxonomy_terms_test.py", "post_terms_test.py", "taxonomy_crud_test.py", "term_search_test.py", "object_types_test.py", "page_visibility_test.py", "page_slug_test.py", "comment_moderation_test.py", "tools_test.py", "comment_guards_test.py", "comment_email_test.py", "comment_options_test.py", "comment_action_test.py", "previously_approved_test.py", "comment_order_test.py", "comment_trash_test.py", "slug_redirect_test.py", "pending_count_test.py", "media_attach_test.py", "media_folder_test.py", "big_image_test.py", "registration_switch_test.py", "cpt_supports_comments_test.py", "author_display_name_test.py", "admin_search_deeplink_test.py", "shortcode_media_test.py", "taxonomy_archive_test.py")
CHECK_LINE = re.compile(r"^\d+\.")


def main() -> int:
    if not os.path.isdir(FIXTURES):
        # Exit 2, not 0. "The fixtures are absent" and "the behaviour holds"
        # are different facts, and returning 0 for the first is how a gate
        # ends up green without ever having run. 2 is the conventional
        # could-not-check code, so a CI step can tell them apart.
        print(f"SKIP: fixtures missing at {FIXTURES}")
        print("     this gate did NOT run; do not read this as a pass.")
        return 2

    # The fixtures write to one database, so two runs of this gate at once see
    # each other's rows — a comment made "held" by one run is approved by the
    # other, and the failure lands on whichever check happened to be running.
    # That reads as a flaky fixture and is neither. The lock is advisory and
    # keyed on this file's own lock, so it serialises gate runs against each
    # other and nothing else.
    lock_path = os.path.join(_repo_root(), ".p1-tests", ".gate.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock = open(lock_path, "w", encoding="utf-8")
    try:
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        except (OSError, ImportError) as exc:  # noqa: PERF203
            # Refusing to run is the wrong failure here: a missing lock must not
            # turn a working gate into a skip. Say so, and carry on alone.
            print(f"WARN: could not take the gate lock ({exc}); running alone.")

        return _run_all()
    finally:
        lock.close()


def _run_all() -> int:

    failed: list[str] = []
    ran = 0
    for script in SCRIPTS:
        path = os.path.join(FIXTURES, script)
        if not os.path.isfile(path):
            print(f"SKIP: {script} not present — the check did not run.")
            return 2
        ran += 1
        try:
            proc = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            # 30 fixtures run back to back against one database. When anything else
            # touches that database at the same time — another session, a manual
            # fixture run — every one of them slows down together, and the total
            # lands on the 300s budget even though every fixture is fine on its
            # own. Retrying once after a pause separates that from a fixture
            # that genuinely hangs, which is the failure worth reporting. The
            # 300s is per attempt, so this cannot double the runtime in the
            # normal path: the retry only runs when the first attempt already
            # spent 300s.
            print(
                "     %s hit the 300s budget; pausing and retrying once — "
                "another run against the same database can push all 30 "
                "over it together." % script
            )
            time.sleep(10)
            try:
                proc = subprocess.run(
                    [sys.executable, path],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                failed.append(script)
                print(f"FAIL {script} timed out again after a retry — the "
                      f"fixture itself hangs, or something else is holding "
                      f"the database")
                continue
            # A successful retry falls through to the normal inspection below.

        checks = [
            ln.strip()
            for ln in (proc.stdout or "").splitlines()
            if CHECK_LINE.match(ln.strip())
        ]
        if proc.returncode != 0:
            failed.append(script)
            print(f"FAIL {script} exited {proc.returncode}")
            for line in checks:
                print(f"     {line}")
            for line in (proc.stderr or "").strip().splitlines()[-3:]:
                print(f"     {line}")
        else:
            print(f"PASS {script}: {len(checks)} check(s)")
            for line in checks:
                print(f"     {line}")

    if failed:
        print("\nFAIL: " + ", ".join(failed))
        return 1
    if not ran:
        print("\nSKIP: nothing to run.")
        return 0
    print("\nPASS: publication date and quick-edit format both hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())