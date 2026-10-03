"""The watermark options have an operator surface.

The backend has been complete for a while: `watermark_service` rewrites every
uploaded raster in place, and the three `media_watermark_*` options drive it.
What was missing is the switch — the options were seeded with no UI, so the
feature could only be enabled by writing to the options table by hand.

This checks the chain, each link in the file that must own it:

  * the card exists and reads all three options;
  * it writes all three (a card that saves two of three silently drops the
    operator's choice on the third);
  * it is mounted on the media page — a component nobody renders is a
    component that does not exist;
  * the page import resolves to the same component.

Run:  python scripts/wp-parity/check_watermark_wired.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARD = os.path.join(ROOT, "frontend", "components", "admin", "watermark-settings-card.tsx")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "media", "page.tsx")

OPTIONS = (
    "media_watermark_enabled",
    "media_watermark_position",
    "media_watermark_opacity",
)

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    if not os.path.isfile(CARD):
        print(f"FAIL: the card does not exist at {CARD}")
        return 1
    if not os.path.isfile(PAGE):
        print(f"FAIL: the media page does not exist at {PAGE}")
        return 1

    card = open(CARD, encoding="utf-8").read()
    page = open(PAGE, encoding="utf-8").read()

    for option in OPTIONS:
        check(f"the card reads {option}", option in card,
              "the option is never read, so the form cannot show its value")
    # Writes: each option must appear inside a `set(` call.
    for option in OPTIONS:
        written = re.search(
            r"siteOptionsApi\.set\(\s*\"%s\"" % re.escape(option), card
        )
        check(f"the card writes {option}", written is not None,
              "the option is shown but never saved")

    check("the card is exported", "export function WatermarkSettingsCard" in card)
    check("the media page imports the card",
          "WatermarkSettingsCard" in page and "watermark-settings-card" in page,
          "no import — the component cannot be rendered")
    # Rendered, not merely imported: the JSX tag must appear.
    check("the media page renders it", "<WatermarkSettingsCard" in page,
          "imported but never used in JSX")

    # The behaviour half: the options must actually drive the upload pipeline.
    # Static checks cannot see that, so the fixture runs the real chain —
    # option on -> upload -> stored bytes marked; option off -> unmarked.
    import subprocess

    fixture = os.path.join(ROOT, ".p1-tests", "media_watermark_test.py")
    if not os.path.isfile(fixture):
        check("the behaviour fixture exists", False, fixture)
    else:
        try:
            proc = subprocess.run(
                [sys.executable, fixture],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=300,
            )
        except subprocess.TimeoutExpired:
            check("the behaviour fixture ran", False, "timed out")
        else:
            for ln in (proc.stdout or "").splitlines():
                if re.match(r"^\d+", ln.strip()):
                    print(f"     {ln.strip()}")
            check("the options drive the upload pipeline end to end",
                  proc.returncode == 0,
                  (proc.stdout or "")[-400:])

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the watermark options have a card that reads, writes, "
          "renders, and demonstrably marks uploads.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
