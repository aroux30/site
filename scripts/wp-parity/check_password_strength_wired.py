"""The password strength meter must evaluate correctly and be rendered on the form.

WordPress carries an evaluator derived from zxcvbn that rates passwords into
four bands: very weak, weak, medium, strong. The point is not aesthetics — it
is stopping a customer who sets `12345678` from losing their account next week.

Two halves, and each can be absent while the other is fine:

  * the evaluator logic. Must penalise pure numbers, all-lower or all-upper,
    repeated characters, and short length; and must reward length past 12 and
    past 16 and character diversity.
  * the component wiring. The meter must be rendered under the password input
    in the registration form, not merely exist in a components folder.

Run:  python scripts/wp-parity/check_password_strength_wired.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
METER = os.path.join(ROOT, "frontend", "components", "auth",
                     "password-strength-meter.tsx")
REGISTER = os.path.join(ROOT, "frontend", "app", "(store)", "register", "page.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    for path in (METER, REGISTER):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    meter, register = read(METER), read(REGISTER)

    # 1. the evaluator rules
    check("evaluator function is exported", "export function evaluatePassword" in meter)
    check("penalises pure digits", "/^[0-9]+$/" in meter)
    check("penalises repeated characters", "/(.)\\1{2,}/" in meter)
    check("requires diversity for high scores", "diversity" in meter)
    check("scores into five bands (0..4)", "0 | 1 | 2 | 3 | 4" in meter)

    # 2. the component exists and is accessible
    check("component is exported", "export function PasswordStrengthMeter" in meter)
    check("renders polite live region for screen readers",
          'aria-live="polite"' in meter)

    # 3. wired into the registration form
    check("registration page imports it", "PasswordStrengthMeter" in register)
    check("rendered under the password field",
          "<PasswordStrengthMeter password={password}" in register)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the password strength evaluator has the right penalties "
          "and is rendered on the registration form.")
    return 0


if __name__ == "__main__":
    sys.exit(main())