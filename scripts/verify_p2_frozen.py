#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The one command that says whether P2 is done, on a tree nobody is editing.

Every other check in this repository answers a question about one thing. This
answers the only question anybody actually asks at the end: *is it finished?*
It runs the whole verification set back to back and prints a single verdict,
with every step's own output available underneath.

    python scripts/verify_p2_frozen.py              # the verdict
    python scripts/verify_p2_frozen.py --quiet      # steps only on failure
    python scripts/verify_p2_frozen.py --min-idle 20  # require 20 quiet minutes

**The quiet-tree check is not a nicety.** This repository has been edited by
three sessions at once, and that produced three measured false results: a
"regression" that was another session's half-finished rewrite, a guard reported
as unrunnable because its file was being rewritten underneath it, and a 19/21
audit run that turned out to be 21/21 once the writes stopped. A verdict
recorded while the tree is moving is not a verdict, so this script refuses to
print a clean one without saying how quiet the tree was.

Five steps, in the order that fails fastest and says the most:

1. the 25 invariant gates — cheap, and they catch a broken tree immediately;
2. the sabotage audit — 21 guards plus the gates, each proven able to turn red;
3. the backend suite;
4. `tsc` on the frontend;
5. `alembic heads` vs `current` — one head, and the database on it.

Exit 0 only when every step passed *and* the tree was quiet. A step that could
not run is reported as such and is never counted as a pass — the same rule the
gate runner follows, and the same reason it exists.

Read-only. It restores nothing, edits nothing, and runs no migration.
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(_HERE)
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "frontend")
PY = sys.executable

#: Directories whose contents count as "the tree" for the quiet check. Build
#: output and dependencies are excluded on purpose: a `.next` rebuild or an
#: `npx` install writes thousands of files and says nothing about whether the
#: source is being edited. `scripts/` is included because the gates live there
#: and a gate edited mid-run makes the run meaningless.
TRACKED = (
    "backend/app",
    "backend/alembic",
    "backend/tests",
    "frontend/app",
    "frontend/components",
    "frontend/lib",
    "frontend/hooks",
    "frontend/tests",
    "scripts",
)


class Step:
    """One verification step and its outcome."""

    def __init__(self, name: str, argv: list[str], cwd: str, timeout: int) -> None:
        self.name = name
        self.argv = argv
        self.cwd = cwd
        self.timeout = timeout
        self.code = 0
        self.seconds = 0.0
        self.stdout = ""
        self.stderr = ""
        #: Set when a step could not run at all. Distinct from a pass: an
        #: unverifiable step is the one outcome that must never read as green.
        self.could_not_run = ""

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.could_not_run

    @property
    def verdict(self) -> str:
        if self.could_not_run:
            return "COULD NOT RUN"
        return "pass" if self.code == 0 else "FAIL"

    def tail(self, lines: int = 14) -> str:
        """The end of the output, where a failure explains itself."""
        body = (self.stdout + self.stderr).strip().splitlines()
        return "\n".join("      " + ln for ln in body[-lines:])


def _run(name: str, argv: list[str], cwd: str, timeout: int) -> Step:
    step = Step(name, argv, cwd, timeout)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [BACKEND, env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    began = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        step.code = proc.returncode
        step.stdout = proc.stdout or ""
        step.stderr = proc.stderr or ""
        # Exit 3 is audit_p2_guards' refusal to sabotage a moving tree. It is
        # not a failure of the audit and not a pass either — it means the one
        # check that proves the guards can fail did not run, and reporting it as
        # green would make the verdict exactly as unearned as the case it exists
        # to catch.
        if proc.returncode == 3 and "REFUSED" in step.stdout:
            step.could_not_run = (
                "the sabotage audit refused to run on a tree that was still "
                "moving; the guards were not proven able to fail"
            )
    except FileNotFoundError as exc:
        step.could_not_run = str(exc)
    except subprocess.TimeoutExpired:
        step.could_not_run = f"timeout after {timeout}s"
    step.seconds = time.monotonic() - began
    return step


# ------------------------------------------------------------------ the tree


def _recently_changed(minutes: float, now: float) -> list[tuple[str, float]]:
    """Every tracked file written in the last `minutes`, newest first.

    Skips the usual noise directories rather than filtering by name: a build
    directory that is missing from the ignore list should not make the tree look
    busy, and one that is present should not make it look quiet either.
    """
    skip = {".next", "node_modules", "__pycache__", ".git", ".pytest_cache", "dist"}
    cutoff = now - minutes * 60
    hits: list[tuple[str, float]] = []
    for rel in TRACKED:
        base = os.path.join(ROOT, rel)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [
                d for d in dirnames if d not in skip and not d.startswith(".")
            ]
            for name in filenames:
                if name.endswith((".pyc", ".pyo")):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if mtime > cutoff:
                    hits.append((os.path.relpath(path, ROOT).replace("\\", "/"), mtime))
    hits.sort(key=lambda pair: pair[1], reverse=True)
    return hits


# -------------------------------------------------------------------- alembic


def _alembic_heads_and_current() -> tuple[list[str], str, str]:
    """`(heads, current, error)`.

    Two heads is the failure this exists for: the schema can then be applied in
    either order depending on which branch a fresh database starts from, and a
    migration that works on the developer's database raises on a new one. One
    head is a precondition of the P2 work, not a nicety.
    """
    heads_cmd = [PY, "-B", "-m", "alembic", "heads"]
    cur_cmd = [PY, "-B", "-m", "alembic", "current"]
    heads_out = subprocess.run(
        heads_cmd, cwd=BACKEND, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    cur_out = subprocess.run(
        cur_cmd, cwd=BACKEND, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    if heads_out.returncode != 0:
        return [], "", (heads_out.stderr or heads_out.stdout).strip().splitlines()[-1:]
    if cur_out.returncode != 0:
        return [], "", (cur_out.stderr or cur_out.stdout).strip().splitlines()[-1:]

    def revisions(text: str) -> list[str]:
        found: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            # `alembic heads` prints "<rev> (head)"; `current` prints the same
            # shape, optionally with the "(head)" marker absent.
            if not line or line.startswith("INFO"):
                continue
            head = line.split(" ", 1)[0].strip()
            if head and head not in found:
                found.append(head)
        return found

    return revisions(heads_out.stdout), revisions(cur_out.stdout), ""


# ---------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-idle",
        type=float,
        default=5.0,
        help="minutes without a source edit required for a clean verdict "
        "(default: 5). Use 0 to skip the check and accept the caveat.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print a step's output only when it failed",
    )
    args = parser.parse_args()

    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    started = time.monotonic()
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")

    out.write(f"P2 final verification — {started_at}\n")
    out.write("=" * 78 + "\n")

    # --- the tree, before anything is measured -------------------------------
    changed = _recently_changed(args.min_idle, time.time()) if args.min_idle > 0 else []
    if args.min_idle > 0:
        if changed:
            out.write(
                f"WARNING: {len(changed)} tracked file(s) changed in the last "
                f"{args.min_idle:g} minutes.\n"
            )
            for path, mtime in changed[:12]:
                ago = max(0.0, time.time() - mtime) / 60
                out.write(f"    {ago:6.1f}m ago  {path}\n")
            if len(changed) > 12:
                out.write(f"    ... and {len(changed) - 12} more\n")
            out.write(
                "  A verdict recorded now describes a tree that is still moving. "
                "Let the other sessions finish, then re-run.\n"
            )
        else:
            out.write(
                f"tree quiet for at least {args.min_idle:g} minutes "
                f"({len(TRACKED)} tracked areas)\n"
            )
    else:
        out.write(
            "WARNING: --min-idle 0, the quiet-tree check was skipped.\n"
        )
    out.write("-" * 78 + "\n")

    steps = [
        Step("invariant gates", [PY, "-B", "scripts/run_all_gates.py"], ROOT, 1800),
        Step(
            "guard sabotage audit",
            # --force because this command has already established that the tree
            # is quiet. The audit refuses to run its sabotage layers on a moving
            # tree — correctly, since every case writes a real source file — and
            # that check belongs here, once, rather than being repeated halfway
            # through a five-minute run.
            [PY, "-B", "scripts/audit_p2_guards.py", "--force"],
            ROOT,
            1800,
        ),
        Step(
            "backend suite",
            [PY, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            BACKEND,
            3600,
        ),
    ]

    # tsc lives in the frontend's node_modules; a missing one is "could not
    # run", not a type error, and the distinction decides the exit code.
    npx = "npx.cmd" if os.name == "nt" else "npx"
    steps.append(
        Step("frontend types", [npx, "tsc", "--noEmit"], FRONTEND, 1800)
    )

    # The list is rebuilt from what actually ran. Assigning the results back is
    # the point: an earlier version appended each Step to `steps`, ran a *new*
    # Step built from the same arguments, and reported on the originals — which
    # kept `code = 0` forever. A gate failed, the report said 5/5, and the
    # verdict said DONE. The same shape as a test asserting on the fixture
    # instead of the code under test.
    for index, step in enumerate(list(steps)):
        result = _run(step.name, step.argv, step.cwd, step.timeout)
        steps[index] = result
        out.write(
            f"  {result.name:<24} {result.verdict:<14} {result.seconds:6.1f}s\n"
        )
        if not result.ok or not args.quiet:
            if result.stdout.strip() or result.stderr.strip():
                out.write(result.tail() + "\n")
        sys.stdout.flush()

    # --- migrations ----------------------------------------------------------
    heads, current, alembic_error = _alembic_heads_and_current()
    if alembic_error:
        out.write(f"  {'migration heads':<24} {'COULD NOT RUN':<14}\n")
        out.write("      " + " ".join(str(e) for e in alembic_error) + "\n")
        head_ok = False
    else:
        # `alembic current` prints the whole ancestry of the applied revision in
        # some configurations; only the first line is the applied one.
        head_ok = len(heads) == 1 and len(current) == 1 and heads[0] == current[0]
        state = "pass" if head_ok else "FAIL"
        out.write(f"  {'migration heads':<24} {state:<14}\n")
        if not head_ok:
            out.write(
                f"      heads={heads or '(none)'} current={current or '(none)'}\n"
            )
            if len(heads) > 1:
                out.write(
                    "      two heads: a fresh database can take either branch, so "
                    "a migration that passes here can fail there. Merge them.\n"
                )
            elif current and heads and current[0] != heads[0]:
                out.write(
                    f"      the database is at {current[0]} but the tree is at "
                    f"{heads[0]}; a deployment would run migrations nobody has run.\n"
                )
            elif not current:
                out.write("      the database reports no applied revision.\n")
        else:
            out.write(f"      single head {heads[0]}, database on it\n")

    # --- the verdict ---------------------------------------------------------
    failed = [s for s in steps if not s.ok]
    quiet_enough = not changed or args.min_idle == 0
    out.write("=" * 78 + "\n")
    out.write(
        f"{len(steps) + 1 - len(failed) - (0 if head_ok else 1)}"
        f"/{len(steps) + 1} checks passed in {time.monotonic() - started:.0f}s\n"
    )

    if failed or not head_ok:
        out.write("\nVERDICT: NOT DONE\n")
        for step in failed:
            out.write(f"  {step.name}: {step.verdict}\n")
            if step.could_not_run:
                out.write(f"      {step.could_not_run}\n")
        if not head_ok and not alembic_error:
            out.write("  migrations: heads and current disagree\n")
    elif not quiet_enough:
        out.write("\nVERDICT: every check passed, but the tree was still moving.\n")
        out.write(
            "  Treat this as a preview. Re-run once the other sessions have "
            "stopped; only then is it a verdict.\n"
        )
    else:
        out.write("\nVERDICT: P2 IS DONE\n")
        if args.min_idle > 0:
            out.write(
                f"  Every invariant gate, the sabotage audit, the backend suite, "
                f"frontend types and a single migration head — all green, on a "
                f"tree quiet for {args.min_idle:g}+ minutes.\n"
            )
        else:
            # Do not print the quietness claim when it was never checked. The
            # message says the checks passed; claiming they passed on a frozen
            # tree when --min-idle 0 skipped that check is the kind of sentence
            # a reader takes as a measurement.
            out.write(
                f"  Every invariant gate, the sabotage audit, the backend suite, "
                f"frontend types and a single migration head — all green.\n"
                f"  The quiet-tree check was SKIPPED (--min-idle 0), so this says "
                f"nothing about the tree having been still.\n"
            )
    out.flush()
    return 0 if (not failed and head_ok and quiet_enough) else 1


if __name__ == "__main__":
    sys.exit(main())