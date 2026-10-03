"""A gate on disk that nobody runs is a gate that does not exist.

Found the hard way: three gates — the cross-session sabotage check, the comment
resource constraint, and the page lock wiring — sat in `scripts/wp-parity/`
passing perfectly and had never once been executed by the suite. A future edit
to the thing they guard would have been reported as covered and was not.

The reason is that registering a gate is a separate act from writing one, and
nothing links them. This gate closes that: every `check_*.py` in the directory
must appear in `run_all_gates.py`'s `GATES`, and every entry there must point at
a file that exists. Both directions, because the two failures look identical —
a suite that is green either way — and neither shows up until the thing the gate
was written for actually breaks.

The fix is one line in a list, which is exactly why it gets forgotten.

Run:  python scripts/wp-parity/check_every_gate_is_registered.py
"""

from __future__ import annotations

import os as _os
_sys_path_insert = _os.path.dirname(__file__)
import sys as _sys
_sys.path.insert(0, _sys_path_insert)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARITY = os.path.join(ROOT, "scripts", "wp-parity")
RUNNER = os.path.join(ROOT, "scripts", "run_all_gates.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    if not os.path.isdir(PARITY):
        print(f"FAIL: {PARITY} is missing")
        return 1

    with open(RUNNER, encoding="utf-8") as fh:
        runner = fh.read()

    registered = set(re.findall(r'\(\s*"(check_[a-z0-9_]+)"', runner))
    # The runner builds paths as `check_<name>.py`, so the registry stores the
    # stem. Normalise whatever it actually found so a gate named
    # `check_foo` and a file named `check_foo.py` line up.
    registered = {r[6:] if r.startswith("check_") else r for r in registered}

    on_disk = {
        f[6:-3] for f in os.listdir(PARITY)
        if f.startswith("check_") and f.endswith(".py")
    }

    print(f"  gates on disk: {len(on_disk)}")
    print(f"  gates registered in run_all_gates.py: {len(registered)}")

    missing = sorted(on_disk - registered)
    check("every gate on disk is registered", not missing,
          "; ".join(missing[:8]))

    absent = sorted(registered - on_disk)
    check("every registered gate exists on disk", not absent,
          "; ".join(absent[:8]))

    # The suite has to be running them too. `GATES` is the list; a registry
    # that is defined but never iterated is the same problem one level up.
    if "for name, needs_db in selected" not in runner:
        check("the runner iterates its registry", False,
              "GATES exists but nothing loops over it")

    # The runner runs gates, not negative tests — the two are separate on
    # purpose, because a negative test deliberately breaks a file and must not
    # run in the same pass as everything else. Stated here so the exemption
    # reads as a decision rather than as an oversight.
    negatives = {
        f[:-3] for f in os.listdir(PARITY)
        if f.startswith("negative_test_") and f.endswith(".py")
    }
    print(f"  negative tests (run separately, not registered here): {len(negatives)}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        print("\nAn unregistered gate passes every time it is run by hand and")
        print("never runs in the suite, which is the state this exists to end.")
        return 1
    print("\nPASS: every gate on disk is registered, and every registration "
          "points at a file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())