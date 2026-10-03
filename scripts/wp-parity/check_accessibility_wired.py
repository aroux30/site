"""The accessibility suite is wired, not just installed.

`@axe-core/playwright` was in `package.json` and no file imported it, and there
was no Playwright config — so `npm run test:e2e` resolved to nothing and the
dependency was decoration. This checks the three links that make the suite
real, each in the file that must own it:

  * the dependency is declared;
  * a config exists and points at a test directory the spec lives in;
  * the spec imports `AxeBuilder` and actually calls `.analyze()` — an import
    with no analysis is the same decoration in a different file.

It does NOT run the browser: that needs a dev server and the backend, and this
project has a documented hazard about concurrent `next dev`. The harness itself
is proven by the smoke run recorded in the spec's own history; what can go
stale without anyone noticing is the wiring, and that is what is checked.

Run:  python scripts/wp-parity/check_accessibility_wired.py
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND = os.path.join(ROOT, "frontend")
CONFIG = os.path.join(FRONTEND, "playwright.config.ts")
SPEC = os.path.join(FRONTEND, "tests", "e2e", "accessibility.spec.ts")
PKG = os.path.join(FRONTEND, "package.json")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    if not os.path.isfile(PKG):
        print(f"FAIL: package.json missing at {PKG}")
        return 1
    pkg = json.load(open(PKG, encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    check("@axe-core/playwright is a declared dependency",
          "@axe-core/playwright" in deps, "not in package.json")
    check("@playwright/test is a declared dependency",
          "@playwright/test" in deps, "not in package.json")
    scripts = pkg.get("scripts", {})
    check("there is a test:e2e script", "test:e2e" in scripts,
          "npm run test:e2e has nothing to run")

    check("a playwright config exists", os.path.isfile(CONFIG),
          "without it, `playwright test` finds no testDir")
    if os.path.isfile(CONFIG):
        cfg = open(CONFIG, encoding="utf-8").read()
        check("the config points at a testDir", "testDir" in cfg)
        check("the config sets a baseURL", "baseURL" in cfg)

    check("the axe spec exists", os.path.isfile(SPEC),
          "the dependency is unused without a spec that imports it")
    if os.path.isfile(SPEC):
        spec = open(SPEC, encoding="utf-8").read()
        check("the spec imports AxeBuilder",
              "AxeBuilder" in spec and "axe-core/playwright" in spec,
              "no import — nothing uses axe")
        check("the spec calls .analyze()", ".analyze()" in spec,
              "imported but never analysed")
        check("the spec asserts on violations", "violations" in spec,
              "analysed but the result is not asserted on")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the accessibility suite is wired — dependency, config, and "
          "a spec that runs axe and asserts on the result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())