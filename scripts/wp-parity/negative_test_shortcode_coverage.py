"""Negative test for check_shortcode_coverage.

Two sabotages, and the second is the one that matters.

  A. Remove `video`. The gap this gate was written for: the shortcode is
     absent, an author pastes `[video]`, and the literal text appears on the
     page.
  B. Widen the URL check to accept anything. The refusal becomes an
     allow-list-with-a-hole, and a `javascript:` source reaches an `<audio
     src>` — script execution in the page's origin, from a shortcode an
     author typed. Nothing about the refusal looks different in the source: it
     is still an `if`, still returning early.

Run:  python scripts/wp-parity/negative_test_shortcode_coverage.py
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_shortcode_coverage.py")
SHORTCODES = os.path.join(ROOT, "backend", "app", "shared", "content",
                         "shortcodes.py")


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=400,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def edit(label: str, fn) -> bool:
    with open(SHORTCODES, encoding="utf-8", newline="") as fh:
        on_disk = fh.read()
    crlf = "\r\n" in on_disk
    original = on_disk.replace("\r\n", "\n")

    def write(text: str) -> None:
        payload = text.replace("\n", "\r\n") if crlf else text
        with open(SHORTCODES, "w", encoding="utf-8", newline="") as fh:
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

    ok = True

    def drop_video(text: str) -> str:
        needle = '@shortcode("video")\n'
        if needle not in text:
            raise AssertionError("the video shortcode is not in the expected shape")
        # Unregister rather than delete: the gate must notice a shortcode that
        # exists in the file and is not reachable, which is the state a
        # commented-out block leaves behind.
        return text.replace(needle, '# @shortcode("video")  # sabotage\n', 1)

    ok = edit("A: unregister the video shortcode", drop_video) and ok

    def widen_url_check(text: str) -> str:
        needle = '    if lowered.startswith(("/media/", "/uploads/")) or lowered.startswith("./"):\n        return url\n'
        if needle not in text:
            raise AssertionError("the scheme check is not in the expected shape")
        # Still an allow-list, still an `if` — but with a hole in it.
        return text.replace(
            needle,
            needle + "    if lowered.startswith(\"data:\"):\n        return url  # sabotage\n",
            1,
        )

    ok = edit("B: let a data: source through the check", widen_url_check) and ok

    if not ok:
        return 1
    print("\nPASS: the gate sees a missing shortcode and a scheme check with a "
          "hole in it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())