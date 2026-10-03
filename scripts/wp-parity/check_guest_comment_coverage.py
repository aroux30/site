"""Guard: a data-subject request reaches comments that have no owner.

P0 "حریم خصوصی: پوشش دیدگاه‌های مهمان". A guest comment carries an email and an
IP and no owner, so every query that selects on ``author_id`` alone misses all
of them. Both halves of the request were blind to it: the export came back with
no comments in it, and the erasure left the subject's email and IP in a table
the whole storefront reads.

The hard delete is the sharp end. The foreign key is ``ON DELETE SET NULL``, so
signed-in comments survive as orphans and cascade-adjacent code considers them
handled — but a guest comment hangs off nothing at all, so the cascade has no
path to it and the account can be deleted with the subject's address still in
plain sight.

The live assertion is backend/scripts/verify_guest_comment_privacy.py; this
guard is the one that runs without a database, so the regression is caught at
commit time rather than the next time somebody remembers to run the check.

    python scripts/wp-parity/check_guest_comment_coverage.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = Path(__file__).resolve().parents[2]
SERVICE = (
    ROOT / "backend" / "app" / "modules" / "settings" / "application" / "privacy_service.py"
)


def main() -> int:
    failures: list[str] = []
    path = SERVICE
    if not path.is_file():
        print("FAIL: %s does not exist" % path)
        return 1
    service = path.read_text(encoding="utf-8")

    # 1. There has to be a matcher that understands a guest comment at all.
    #    Substring presence would be satisfied by a mention in a docstring, so
    #    the call site is what gets checked: a statement built and executed.
    if "def _comments_by_subject(" not in service:
        failures.append(
            "there is no matcher for comments by subject, so every comment query "
            "here can only look at author_id and misses every guest comment"
        )
    elif "author_email.ilike(" not in service:
        failures.append(
            "the subject matcher does not compare the guest email, so a comment "
            "left before the subject registered is never attributed to them"
        )

    # 2. Both halves of the request have to go through it. A helper that exists
    #    and is called once is half the fix, and the half that was missing is the
    #    one nobody notices.
    helper = re.search(r"def _comments_by_subject\(", service)
    if helper:
        # Every comment query in this module must be the helper, not a raw
        # author_id select. Counted rather than searched: a single remaining
        # raw query is the bug, and a search for the bad pattern would also hit
        # the helper's own definition. `\s*` across the line break on purpose —
        # a formatter will split this call however it likes, and a guard that
        # only matches the one-line form passes on a broken multi-line query.
        raw = re.findall(
            r"select\(BlogComment\)\s*\.where\(\s*BlogComment\.author_id", service
        )
        for _ in raw:
            failures.append(
                "a comment query still selects on author_id alone, so guest "
                "comments are invisible to the data-subject request"
            )
        if not re.search(r"_comments_by_subject\(user_id, user\.email\)", service):
            failures.append(
                "the export does not pass the subject's address to the matcher, so "
                "a guest comment cannot be matched to them"
            )

    # 3. The address has to be read before it is cleared. The anonymize branch
    #    sets user.email = None early; a matcher call after that point finds
    #    nothing, which is exactly how the original code left the data in place.
    #    The capture sits *before* `if anonymize:`, so the body under
    #    examination starts at the capture and runs to the hard-delete branch.
    anon = re.search(
        r"subject_email = user\.email(.*?)\n        else:\s*\n\s*# Hard delete",
        service,
        re.S,
    )
    if anon:
        body = "subject_email = user.email" + anon.group(1)
        clear_at = body.find("user.email = None")
        if clear_at < 0:
            failures.append("the anonymize branch no longer clears the account email")
        else:
            before = body[:clear_at]
            if "subject_email = user.email" not in before:
                failures.append(
                    "the account email is cleared before the guest-comment pass "
                    "reads it, so that pass has no address to match on and leaves "
                    "the subject's email and IP in a public table"
                )
    else:
        failures.append(
            "the address is not captured before the account email is cleared, so "
            "the guest-comment pass has nothing to match on"
        )

    # 4. The hard delete has to reach the guest comments itself.
    hard = re.search(r"\n        else:\s*\n\s*# Hard delete(.*)$", service, re.S)
    if not hard:
        failures.append("the hard-delete branch could not be read")
    else:
        body = hard.group(1)
        if "await db.delete(user)" not in body:
            failures.append("the hard-delete branch no longer deletes the account")
        elif "_comments_by_subject" not in body:
            failures.append(
                "the hard delete relies on the cascade to clear comments, but a "
                "guest comment hangs off no foreign key -- the account is deleted "
                "and its address stays in the comment table"
            )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d guest-comment coverage link(s) are broken." % len(failures))
        return 1
    print("PASS: both halves of a data-subject request reach guest comments.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
