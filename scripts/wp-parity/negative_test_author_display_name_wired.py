"""Negative test for check_author_display_name_wired.

This gate exists because the feature was handed over twice before being done.
Each time every *piece* was present and only the chain was broken, so the
sabotages are the three broken hops rather than the obvious "delete the column".

  A. Remove `display_name` from the constructor call. The field is on the row,
     the query selects it, and the formatter prefers it — everything a
     "does the column exist" check asks about is true, and the byline still
     shows first+last. This is the state the code was actually in.
  B. Drop the column from the query. The row and formatter are untouched; the
     value simply never arrives.
  C. Consult the fallback before the chosen name. Every field is read, the
     result is a string either way, and a chosen name loses.
  D. Remove the fallback entirely — the one that does not look like a
     regression, because it only affects authors who never set a name.

Run:  python scripts/wp-parity/negative_test_author_display_name_wired.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_author_display_name_wired.py")
SERVICE = os.path.join(ROOT, "backend", "app", "modules", "blog",
                       "application", "author_service.py")

CTOR_ARG = re.compile(r"[ \t]*display_name=getattr\(profile, \"display_name\", None\),\n")


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def edit(label: str, fn) -> bool:
    with open(SERVICE, encoding="utf-8", newline="") as fh:
        on_disk = fh.read()
    crlf = "\r\n" in on_disk
    original = on_disk.replace("\r\n", "\n")

    def write(text: str) -> None:
        payload = text.replace("\n", "\r\n") if crlf else text
        with open(SERVICE, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)

    try:
        changed = fn(original)
    except AssertionError as exc:
        print(f"FAIL: {label} — {exc}")
        return False
    if changed == original:
        print(f"FAIL: {label} — nothing changed.")
        return False

    write(changed)
    try:
        rc, out = run_gate()
    finally:
        write(original)

    rc_after, _ = run_gate()
    if rc_after != 0:
        print(f"FAIL: {label} — the gate did not pass again after restoring.")
        return False
    if rc == 0:
        print(f"FAIL: {label} still passed. The gate cannot see it.")
        return False

    caught = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("- ")]
    print(f"  {label} -> caught")
    for line in caught[:1]:
        print(f"      {line[:150]}")
    return True


def main() -> int:
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code.")
        print(out.strip()[-700:])
        return 1
    print("gate passes on the real code")

    def drop_ctor_arg(text: str) -> str:
        new, n = CTOR_ARG.subn("", text, count=1)
        if n != 1:
            raise AssertionError(f"the constructor argument matched {n} times")
        return new

    def drop_query_column(text: str) -> str:
        needle = "                UserProfile.display_name,\n"
        if needle not in text:
            raise AssertionError("the query column is not in the expected shape")
        return text.replace(needle, "", 1)

    def swap_preference(text: str) -> str:
        chosen = '    chosen = (getattr(author, "display_name", None) or "").strip()\n'
        if chosen not in text:
            raise AssertionError("the chosen-name line is not in the expected shape")
        # Read the fallback first, then the chosen name: every field is still
        # read and the result is still a string — only the winner changes.
        return text.replace(
            chosen,
            '    _fb = f"{author.first_name or \'\'} {author.last_name or \'\'}".strip()\n'
            '    chosen = (getattr(author, "display_name", None) or "").strip()\n',
            1,
        ).replace(
            "    name = chosen or f\"{author.first_name or ''} "
            "{author.last_name or ''}\".strip()",
            "    name = _fb or chosen",
            1,
        )

    def drop_fallback(text: str) -> str:
        needle = " or f\"کاربر {author.phone[-4:]}\""
        if needle not in text:
            raise AssertionError("the phone fallback is not in the expected shape")
        return text.replace(needle, "", 1)

    ok = True
    for label, fn in (
        ("A: stop passing it at the constructor", drop_ctor_arg),
        ("B: stop selecting it in the query", drop_query_column),
        ("C: consult the fallback before the chosen name", swap_preference),
        ("D: remove the phone fallback", drop_fallback),
    ):
        ok = edit(label, fn) and ok

    if not ok:
        return 1
    print("\nPASS: every hop is load-bearing, including the one that was "
          "actually missing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())