"""Negative test for check_wxr_import_behaviour.

Each sabotage undoes one of the three things the parser gets wrong in a way no
source check sees, plus the disconnect. All four were found by running a real
WordPress-shaped file, not by reading the code.

  A. `.text` instead of `itertext()`. Content with markup is truncated at the
     first child element — a shorter string, no error, and a post missing
     everything after its first `<img>`.
  B. Accept `0000-00-00` as a date. The post lands on year zero, which every
     downstream date filter then treats as ancient.
  C. Map every status to published. An author's drafts become live pages, which
     is the worst outcome a migration tool can produce.
  D. Remove the route. The parser stays correct and unreachable, which is the
     same failure as it not existing.

Run:  python scripts/wp-parity/negative_test_wxr_import_behaviour.py
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

GATE = os.path.join(HERE, "check_wxr_import_behaviour.py")
PARSER = os.path.join(ROOT, "backend", "app", "modules", "blog",
                      "application", "wxr_parser.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "blog",
                      "api", "wp_parity_routes.py")
TAB = os.path.join(ROOT, "frontend", "components", "admin", "blog",
                   "transfer-tab.tsx")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "wp-parity.ts")


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def edit(label: str, path: str, fn) -> bool:
    with open(path, encoding="utf-8", newline="") as fh:
        on_disk = fh.read()
    crlf = "\r\n" in on_disk
    original = on_disk.replace("\r\n", "\n")

    def write(text: str) -> None:
        payload = text.replace("\n", "\r\n") if crlf else text
        with open(path, "w", encoding="utf-8", newline="") as fh:
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

    # A: read `.text`, which stops at the first child element.
    def use_dot_text(text: str) -> str:
        needle = '    return "".join(element.itertext()).strip()'
        if needle not in text:
            raise AssertionError("the text reader is not in the expected shape")
        return text.replace(needle, "    return (element.text or '').strip()", 1)

    ok = edit("A: read .text instead of itertext()", PARSER, use_dot_text) and ok

    # B: accept the zero date.
    def accept_zero(text: str) -> str:
        needle = '    if year == "0000" or month == "00" or day == "00":\n        return None'
        if needle not in text:
            raise AssertionError("the zero-date guard is not in the expected shape")
        return text.replace(needle, "    # sabotage: zero dates accepted", 1)

    ok = edit("B: accept 0000-00-00 as a date", PARSER, accept_zero) and ok

    # C: publish everything.
    def publish_everything(text: str) -> str:
        needle = '        status = _STATUS_MAP.get(status_raw, "draft")'
        if needle not in text:
            raise AssertionError("the status mapping is not in the expected shape")
        return text.replace(needle, '        status = "published"  # sabotage', 1)

    ok = edit("C: import every status as published", PARSER,
              publish_everything) and ok

    # D: the route goes; the parser stays.
    def drop_route(text: str) -> str:
        return text.replace('"/import/wxr"', '"/import/wxr-removed"', 1)

    ok = edit("D: remove the WXR route", ROUTES, drop_route) and ok

    # E: the operator cannot pick an XML file. Every backend check still passes.
    def drop_xml_input(text: str) -> str:
        return text.replace('accept="text/xml,application/xml,.xml"',
                            'accept="application/json,.json"', 1)

    ok = edit("E: the tab stops accepting XML", TAB, drop_xml_input) and ok

    # F: the handler parses the file as JSON instead of sending it — the
    #    shape that looks wired and throws on every WordPress file.
    def parse_instead_of_send(text: str) -> str:
        needle = "const stats = await blogTransferApi.importWxr(file);"
        if needle not in text:
            raise AssertionError("the send is not in the expected shape")
        return text.replace(
            needle,
            "const stats = await blogTransferApi.importJson("
            "JSON.parse(await file.text()) as Record<string, unknown>);",
            1,
        )

    ok = edit("F: the WXR handler parses the file as JSON", TAB,
              parse_instead_of_send) and ok

    if not ok:
        return 1
    print("\nPASS: the gate sees truncated content, a zero date, a draft "
          "published, and a parser nobody can reach.")
    return 0


if __name__ == "__main__":
    sys.exit(main())