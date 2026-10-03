"""No gate may rebind sys.stdout in a way another import can close.

Found while running the suite: `negative_test_email_store_name` died with
`ValueError: I/O operation on closed file` on its very first print. The cause
was not the test it was running —

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", ...)

Assigning a fresh wrapper and dropping the old one closes the shared buffer. Any
module that then does the same closes the stream the first one is still
printing to. Twenty-one files in this tree did it, so every test that *imports*
a gate — which is most of the negative tests here, since importing is faster
than a subprocess — was one import away from a crash that looked like a
broken test.

The fix is `console_safe`, which is idempotent: it checks whether stdout is
already UTF-8 and leaves it alone if so. So this gate checks that no file wraps
stdout itself, and that the ones which need the guard import it rather than
reimplementing it.

Run:  python scripts/wp-parity/check_stdout_guards_are_idempotent.py
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PARITY = os.path.join(ROOT, "scripts", "wp-parity")

#: The non-idempotent form. `console_safe` is the supported replacement.
BAD = re.compile(
    r"^\s*sys\.stdout\s*=\s*io\.TextIOWrapper\(", re.M
)

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    files = [f for f in os.listdir(PARITY) if f.endswith(".py")]
    print(f"  files scanned: {len(files)}")

    offenders: list[str] = []
    users_without_guard: list[str] = []

    # Three files legitimately contain the pattern as *text*: the helper that
    # replaces it, this gate (which quotes it in a regex), and this gate's own
    # negative test (which writes it into a throwaway probe). None of them
    # executes it in a process that goes on to import anything.
    exempt = {
        "console_safe.py",
        os.path.basename(__file__),
        "negative_test_" + os.path.basename(__file__).removeprefix("check_"),
    }

    for name in sorted(files):
        if name in exempt:
            continue
        with open(os.path.join(PARITY, name), encoding="utf-8") as fh:
            text = fh.read()
        if BAD.search(text):
            offenders.append(name)
        # Touches stdout at all, but not through the shared helper.
        elif re.search(r"sys\.stdout\.reconfigure|TextIOWrapper\(", text) \
                and "console_safe" not in text:
            users_without_guard.append(name)

    check("no file rebinds sys.stdout with a fresh wrapper",
          not offenders, "; ".join(offenders[:6]))
    check("any file that wraps stdout imports console_safe instead",
          not users_without_guard, "; ".join(users_without_guard[:6]))

    # The helper itself has to exist, or the advice above is unfollowable.
    check("console_safe exists",
          os.path.isfile(os.path.join(PARITY, "console_safe.py")))

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        print("\nA second wrapper closes the first one's buffer. Any module")
        print("imported afterwards then prints to a closed stream.")
        return 1
    print("\nPASS: stdout is guarded in one idempotent place, so importing a "
          "gate cannot close another gate's output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
