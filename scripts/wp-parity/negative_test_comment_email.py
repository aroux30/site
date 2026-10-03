"""Negative test for the comment emails: the envelope is what matters.

  A. Reply-To is dropped from the author mail — the exact regression the item
     was filed for: the author can read the address but cannot reply to it
  B. a mail goes out with no recipient address, i.e. the guard is bypassed and
     the address is guessed from something else
  C. a failing send escapes the service, which would take the whole comment
     down with it because the comment is already stored by then

    python scripts/wp-parity/negative_test_comment_email.py
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__file__))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FIXTURE = os.path.join(ROOT, ".p1-tests", "comment_email_test.py")
SERVICE = os.path.join(
    ROOT, "backend", "app", "modules", "blog", "application",
    "comment_email_service.py",
)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def run_fixture() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, FIXTURE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    for path in (FIXTURE, SERVICE):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1

    original = read(SERVICE)

    rc, out = run_fixture()
    if rc != 0:
        print("FAIL: the fixture does not pass on the real code, so a failure "
              "below would prove nothing.")
        print(out.strip()[-700:])
        return 1

    failures: list[str] = []

    def sabotage(label: str, old: str, new: str) -> None:
        if old not in original:
            failures.append(f"{label}: the sabotage matched nothing — the code "
                            f"moved and this test is pointing at nothing")
            return
        patched = original.replace(old, new, 1)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(patched)
        try:
            rc_s, _ = run_fixture()
        finally:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(original)
        if rc_s == 0:
            failures.append(f"{label}: the checks still passed")
        else:
            print(f"  {label}: caught (as it must be)")

    # A. Reply-To is dropped from the author mail
    sabotage(
        "A: the author mail loses its Reply-To",
        "                reply_to=(reply_to or \"\").strip() or None,",
        "                reply_to=None,  # sabotaged: the commenter is not reachable",
    )

    # B. the no-address guard is removed, so a mail goes out unaddressed
    sabotage(
        "B: a mail goes out with no recipient",
        "        if not author_email:\n"
        "            # No address to send to. Logged rather than raised: the in-app\n"
        "            # notification already reached this person.\n"
        "            logger.info(\n"
        "                \"comment_email_skipped_no_author_address\",\n"
        "                post_title=post_title[:80],\n"
        "            )\n"
        "            return False",
        "        if not author_email:\n"
        "            author_email = \"nobody@example.com\"  # sabotaged: guessed",
    )

    # C. a failing send escapes instead of being swallowed
    sabotage(
        "C: a failed send breaks the comment",
        "        except Exception:  # noqa: BLE001 — a notification must never break the comment",
        "        except ValueError:  # sabotaged: only some failures are swallowed",
    )

    rc_final, out_final = run_fixture()
    if rc_final != 0:
        print("FAIL: the fixture does not pass again after restoring the file — "
              "this test left the repository modified.")
        print(out_final.strip()[-700:])
        return 1

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("\nPASS: all three sabotages were caught.")
    return 0


if __name__ == "__main__":
    sys.exit(main())