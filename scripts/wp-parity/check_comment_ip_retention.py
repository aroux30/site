"""Guard: comment IPs are masked on erasure and by age, both families.

P0 "حریم خصوصی: نگه‌داشت IP دیدگاه". An IP on a comment is personal data under
Article 4(1). It was stored in full, indefinitely, on a table the storefront can
read, and the only code that ever shortened one ran for the single subject who
asked for their own erasure. Nothing applied the rule by age, so every other
comment kept its exact address forever.

Two halves, and they are the same defect seen from two directions:

  - the erasure path, which masks the subject's own comments, and
  - the age sweep, which masks everyone else's.

WordPress does the first in ``wp_comments_personal_data_eraser`` and the
upstream analogue of the second in its moderation settings. The live assertion is
backend/scripts/verify_comment_ip_retention.py; this guard is the one that runs
without a database.

The masking is to the *network*, not NULL. That is not a detail: a flood check
groups comments by author_ip, so NULL throws away the anti-abuse signal the
network was kept for, while the exact address is what identifies a household.

    python scripts/wp-parity/check_comment_ip_retention.py
"""

from __future__ import annotations

import ast
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
ANON = ROOT / "backend" / "app" / "core" / "security" / "ip_anonymize.py"
SERVICE = (
    ROOT
    / "backend"
    / "app"
    / "modules"
    / "settings"
    / "application"
    / "privacy_service.py"
)
RETENTION = (
    ROOT
    / "backend"
    / "app"
    / "modules"
    / "settings"
    / "application"
    / "comment_ip_retention_service.py"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    failures: list[str] = []
    for path in (ANON, SERVICE, RETENTION):
        if not path.is_file():
            print("FAIL: %s does not exist" % path)
            return 1
    anon = read(ANON)
    service = read(SERVICE)
    retention = read(RETENTION)

    # 1. The masking has to exist as a shared helper, and it has to be reachable
    #    from both halves. A helper only one of them calls is half the fix, and
    #    the half that is missing is the one nothing notices.
    if "def anonymize_ip(" not in anon:
        failures.append(
            "there is no IP anonymizer, so nothing in the project can reduce an "
            "address to its network"
        )
    else:
        # The prefix *lengths*, not just the names. A guard that only greps for
        # `V6_PREFIX_LEN` passes on `V6_PREFIX_LEN = 128`, which masks a v6
        # address down to the exact host — no masking at all — and looks like the
        # fix is in place.
        for name, expected in (("V4_PREFIX_LEN", 24), ("V6_PREFIX_LEN", 64)):
            m = re.search(rf"^{name}\s*=\s*(\d+)", anon, re.M)
            if not m:
                failures.append(
                    "no %s, so the network length is whatever the stdlib default "
                    "happens to be rather than the one this policy states" % name
                )
            elif int(m.group(1)) != expected:
                failures.append(
                    "%s is %s, not %d; a %s keeps %s of the address, so the comment "
                    "is not actually anonymized"
                    % (
                        name,
                        m.group(1),
                        expected,
                        name,
                        "the whole address" if expected == 64 else "too much",
                    )
                )

        # v4-mapped collapse. Parsed rather than grepped: `ipv4_mapped` appears in
        # this module's own comment explaining why the isinstance guard is
        # needed, and in `ip_is_masked` as well, so a name search finds the word
        # with the behaviour deleted and calls the collapse present. The property
        # is "a mapped address is replaced by its v4 form inside the masking
        # path", and only the syntax tree knows that.
        tree = ast.parse(anon)
        masked_in_path = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name != "anonymize_ip":
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Attribute) and sub.attr == "ipv4_mapped":
                    masked_in_path = True
        if not masked_in_path:
            failures.append(
                "a v4-mapped v6 address is not collapsed to v4, so one visitor "
                "arriving over v4 and over v6 looks like two people"
            )

    # 2. Masking must be idempotent, or the sweep re-reads every past-window row
    #    on every run forever — and reports zero, which is indistinguishable from
    #    a correct run.
    if "def ip_is_masked(" not in anon:
        failures.append(
            "there is no idempotency check, so the age sweep re-selects the rows it "
            "already handled on every run"
        )

    # 3. The erasure path masks rather than blanks, in both branches. Counted
    #    rather than searched per-branch: both statements are textually
    #    identical, so a per-branch check would pass on a file where one of the
    #    two branches had been reverted to `= None` and the other had not — the
    #    exact shape of the bug, where the fix landed in one path and not the
    #    other.
    if "comment.author_ip = None" in service:
        failures.append(
            "a comment IP is blanked instead of masked, so a flood check loses the "
            "network it groups by while the address is the only thing that "
            "identifies a household"
        )
    masked_sites = service.count("comment.author_ip = anonymize_ip(comment.author_ip)")
    if masked_sites < 2:
        failures.append(
            "only %d of the 2 erasure branches mask the IP (anonymize and hard "
            "delete); the other leaves the address exact" % masked_sites
        )

    # 4. The age sweep has to exist and has to be age-filtered. Without the
    #    `created_at < cutoff` clause it masks comments from the future, which
    #    reads as "the retention policy is being enforced" while it removes the
    #    address a moderator still needs.
    if "def mask_ips_older_than(" not in retention:
        failures.append("there is no age-based IP sweep")
    else:
        sweep = re.search(r"def mask_ips_older_than\((.*)\Z", retention, re.S)
        text = sweep.group(1) if sweep else ""
        # The comparison is checked, not the name of the column. `created_at <
        # cutoff - timedelta(days=3650)` selects comments from the year 2000 and
        # passes a presence test, while masking every comment the store will
        # ever have — the address a moderator still needs, gone. The trailing
        # comma is part of the line, so the anchor sits after it.
        cmp = re.search(
            r"BlogComment\.created_at\s*<\s*cutoff\s*,",
            text,
        )
        if not cmp:
            loose = re.search(r"BlogComment\.created_at\s*<\s*([^,\n]+)", text)
            if loose:
                failures.append(
                    "the age filter compares created_at against %r rather than the "
                    "cutoff, so the window is not the one the retention policy "
                    "states" % loose.group(1).strip()
                )
            else:
                failures.append(
                    "the sweep has no age filter, so it masks every comment including "
                    "the fresh ones a moderator is still reading"
                )
        if "ip_is_masked(" not in text:
            failures.append(
                "the sweep does not skip already-masked addresses, so it re-reads "
                "the same rows forever and its daily count is a lie"
            )
        if "order_by(BlogComment.id)" not in text:
            failures.append(
                "the sweep pages without an ordering, so a batch of already-masked "
                "rows can be returned again and the loop never advances"
            )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d comment-IP retention link(s) are broken." % len(failures))
        return 1
    print("PASS: comment IPs are masked to their network, on erasure and by age.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
