"""The GDPR export arrives as a structured ZIP, and retention is configurable.

    python scripts/wp-parity/check_privacy_export_zip.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _repo_root() -> str:
    d = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(d, ".p1-tests")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.normpath(os.path.join(HERE, "..", ".."))


ROOT = _repo_root()
FIXTURE = os.path.join(ROOT, ".p1-tests", "privacy_export_zip_test.py")
SOURCES = os.path.join(ROOT, "backend", "app", "modules", "settings",
                       "application", "privacy_sources.py")
REQUESTS = os.path.join(ROOT, "backend", "app", "modules", "settings",
                        "application", "privacy_request_service.py")
CHECK_LINE = re.compile(r"^\d+\.")


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {label}: {ok}")
        if not ok:
            failures.append(f"{label}: {detail}" if detail else label)

    # The static half: the ZIP builder and the configurable retention exist in
    # the files that must own them.
    sources = open(SOURCES, encoding="utf-8").read() if os.path.isfile(SOURCES) else ""
    check("the ZIP builder exists", "def build_export_zip" in sources)
    check("it writes an index.html", "index.html" in sources)
    check("it writes a per-source data/ file", '"data/' in sources or "'data/" in sources)

    reqs = open(REQUESTS, encoding="utf-8").read() if os.path.isfile(REQUESTS) else ""
    check("the retention window is read from an option",
          "export_result_ttl" in reqs and "privacy.export_retention_hours" in reqs,
          "retention is still a hardcoded constant")
    check("the retention is clamped", "minimum=1" in reqs and "maximum=30 * 24" in reqs)

    # The behaviour half.
    if not os.path.isfile(FIXTURE):
        print(f"SKIP: fixture missing at {FIXTURE}")
        return 2
    try:
        proc = subprocess.run(
            [sys.executable, "-B", FIXTURE],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300,
        )
    except subprocess.TimeoutExpired:
        check("the zip fixture ran", False, "timed out")
    else:
        for ln in (proc.stdout or "").splitlines():
            if CHECK_LINE.match(ln.strip()):
                print(f"     {ln.strip()}")
        check("the export ZIP behaves", proc.returncode == 0,
              (proc.stdout or "")[-400:])

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the GDPR export is a structured ZIP and its retention is "
          "configurable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())