"""Negative test for the media-page feature gate's branch checks.

The review found that two of this gate's checks were satisfied by strings that
survive deleting the feature: `"application/pdf" in page and "<iframe" in page`
passed with the whole render branch gone, because both words occur elsewhere in
the file. So the sabotage is that — remove the branch, keep the strings.

Two deletions, each of which was green before this test existed:

  A. Delete the PDF preview branch, keeping `isPdf` and the `<iframe>` tag
     somewhere else in the file — so a check that greps still passes.
  B. Delete the list-view render branch, keeping the toggle and the state.

Run:  python scripts/wp-parity/negative_test_media_page_features.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_media_page_features.py")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "media", "page.tsx")


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def edit(label: str, fn) -> bool:
    with open(PAGE, encoding="utf-8", newline="") as fh:
        on_disk = fh.read()
    crlf = "\r\n" in on_disk
    original = on_disk.replace("\r\n", "\n")

    def write(text: str) -> None:
        payload = text.replace("\n", "\r\n") if crlf else text
        with open(PAGE, "w", encoding="utf-8", newline="") as fh:
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
    for line in caught[:2]:
        print(f"      {line[:140]}")
    return True


def main() -> int:
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code.")
        print(out.strip()[-700:])
        return 1
    print("gate passes on the real code")

    # A: delete the PDF preview branch. `isPdf` and `<iframe>` stay elsewhere,
    #    which is what made the old string check useless.
    def delete_pdf_branch(text: str) -> str:
        at = text.find("{isPdf ? (")
        if at == -1:
            raise AssertionError("the PDF branch is not in the expected shape")
        depth = 0
        end = None
        for i in range(at, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            raise AssertionError("the PDF branch does not close")
        # Keep both strings alive somewhere else, so the check has to be about
        # the branch and not the words.
        return (
            text[:at] + "{false /* sabotage */}" + text[end:]
            + "\n// application/pdf <iframe> still present as text\n"
        )

    ok = edit("A: delete the PDF preview branch", delete_pdf_branch)

    # B: delete the list-view render branch, keeping the toggle.
    def delete_list_branch(text: str) -> str:
        m = re.search(r'viewMode === "list" \? \(', text)
        if not m:
            raise AssertionError("the list branch is not in the expected shape")
        at = m.start()
        depth = 0
        end = None
        for i in range(at, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            raise AssertionError("the list branch does not close")
        return text[:at] + "(<div>list</div>)" + text[end:]

    ok = edit("B: delete the list-view render branch", delete_list_branch) and ok

    if not ok:
        return 1
    print("\nPASS: the gate sees both branches deleted while the strings that "
          "used to satisfy it remain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())