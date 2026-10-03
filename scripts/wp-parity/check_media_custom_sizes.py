"""Custom image sizes: register, generate, validate, reclaim.

WordPress's add_image_size(). The behaviour lives in the fixture; this wrapper
puts it in the runner and checks the UI half too, because a registry an
operator cannot edit is a code constant with extra steps.

    python scripts/wp-parity/check_media_custom_sizes.py
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
FIXTURE = os.path.join(ROOT, ".p1-tests", "media_custom_size_test.py")
CARD = os.path.join(ROOT, "frontend", "components", "admin", "image-size-settings-card.tsx")
CHECK_LINE = re.compile(r"^\d+\.")


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {label}: {ok}")
        if not ok:
            failures.append(f"{label}: {detail}" if detail else label)

    # The UI half: the card must read, edit and write the option, or the
    # registry is backend-only and the operator cannot add a size at all.
    card = open(CARD, encoding="utf-8").read() if os.path.isfile(CARD) else ""
    check("the size card exists and edits custom sizes",
          "custom_image_sizes" in card,
          "the option is not in the card")
    check("the card reads the option", "parseCustomSizes" in card)
    check("the card writes the option",
          'siteOptionsApi.set("custom_image_sizes"' in card,
          "edited but never saved")
    check("the card validates the name before adding",
          "a-z0-9" in card and "addCustomSize" in card)

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
        check("the behaviour fixture ran", False, "timed out")
    else:
        for ln in (proc.stdout or "").splitlines():
            if CHECK_LINE.match(ln.strip()):
                print(f"     {ln.strip()}")
        check("registered sizes generate, validate and are reclaimed",
              proc.returncode == 0, (proc.stdout or "")[-400:])

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: custom image sizes are editable, generated, validated, and "
          "reclaimed on delete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
