"""Run the password strength evaluator and check its verdicts.

`check_password_strength_wired.py` reads the source. This one *runs* it, by
extracting the `evaluatePassword` function and executing it in Node, because
the logic is the whole point of the meter — a component that always says
"قوی" is worse than no meter, because the customer believes it.

The cases are the ones where a naive implementation goes wrong:

  * `12345678` passes the server's rule (8 chars, a letter) — no it does not,
    it has no letter, but `abcdefgh` does, and it must still be weak. A meter
    that scores length only calls `abcdefgh` strong.
  * a repeated-character password and a sequential one must be penalised;
  * a genuinely good password must reach the top band, or the meter is useless
    for telling anyone anything.

Run:  node scripts/wp-parity/run_password_strength_cases.mjs
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
METER = os.path.join(ROOT, "frontend", "components", "auth",
                     "password-strength-meter.tsx")
RUNNER = os.path.join(ROOT, "scripts", "wp-parity",
                      "run_password_strength_cases.mjs")

def main() -> int:
    for path in (METER, RUNNER):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1

    proc = subprocess.run(
        ["node", RUNNER, METER],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out.strip())

    if proc.returncode != 0:
        print("\nFAIL: the evaluator run did not complete.")
        return 1
    if "ALL PASS" not in out:
        print("\nFAIL: at least one case did not hold.")
        return 1
    # The cases live in the Node runner, which is what actually executes the
    # evaluator. Duplicating them here would be a second list that drifts, which
    # is the failure this gate exists to prevent.
    count = out.count("  ok   ")
    print(f"\nPASS: all {count} password strength cases hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())