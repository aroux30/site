"""Negative test: the eager-load gate must FAIL on the bug it exists to catch.

A gate that cannot fail is not a gate. This reintroduces the exact defect that
turned the blog list into a 500 — ``BlogCategoryResponse.model_validate(post)``
handing a whole ORM object to pydantic — into a throwaway copy of the tree, and
asserts the gate reports it. Nothing here writes to the repository: the
sabotage is applied to a copy and the gate is pointed at that copy, so a shared
working tree is never the thing being broken.

Two shapes are exercised, because the gate claims to catch both:

1. ``Schema.model_validate(row)`` — the original bug.
2. A field typed as the ORM class, read through ``from_attributes``.

Run:  cd backend && PYTHONPATH=. python scripts/negative_test_eager_load_traps.py
Exit: 0 when the gate behaved correctly, 1 when it did not.
"""

from __future__ import annotations

import ast
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parent.parent
GATE = BACKEND / "scripts" / "check_eager_load_traps.py"


def _sabotage_model_validate(root: Path) -> str:
    """Reintroduce the original defect: model_validate on a whole ORM object.

    Replaces the whole field-by-field construction, so the sabotaged file still
    parses — a sabotage that breaks the syntax only proves the gate cannot read
    its input.
    """
    target = root / "app" / "modules" / "blog" / "application" / "blog_service.py"
    text = target.read_text(encoding="utf-8")
    start = text.find("                BlogCategoryResponse(\n")
    if start == -1:
        raise SystemExit(
            "negative test: the fixed call site is not where it was expected. "
            "The fix moved; update this test rather than leaving it green."
        )
    end = text.find("                if post.category", start)
    if end == -1:
        raise SystemExit("negative test: could not find the end of the call.")
    # Drop the comment block above it too, so the replacement is unambiguous.
    bad = "                BlogCategoryResponse.model_validate(post.category)\n            ),\n"
    target.write_text(text[:start] + bad + text[end + len("                if post.category\n                else None\n            ),\n"):], encoding="utf-8")
    return bad.strip()


def _sabotage_composite_read(root: Path) -> str:
    """Reintroduce the third shape: a lazy relationship read wrapped in an
    expression (``obj.rel or default``), handed to ``model_validate``.

    The gate's original argument walker only looked at arguments that were
    themselves an ``ast.Attribute``, so a wrapped read — ``post.category or
    None`` — was invisible even inside a Case-1 model_validate call. The
    walker now descends into composite expressions; this sabotage pins
    that: with the old walker the gate stays green (this check fails), with
    the fix it flags the read.
    """
    target = root / "app" / "modules" / "blog" / "application" / "blog_service.py"
    text = target.read_text(encoding="utf-8")
    injected = (
        "\n\nasync def _composite_read_probe(post: BlogPost):\n"
        "    return BlogCategoryResponse.model_validate(post.category or None)\n"
    )
    target.write_text(text + injected, encoding="utf-8")
    return "BlogCategoryResponse.model_validate(post.category or None)"


def _sabotage_typed_field(root: Path) -> str:
    """Reintroduce the second shape: a field typed as the ORM class."""
    target = root / "app" / "modules" / "blog" / "schemas" / "blog.py"
    text = target.read_text(encoding="utf-8")
    anchor = '    children: list["BlogCategoryResponse"] | None = None'
    if anchor not in text:
        raise SystemExit("negative test: the children field is not where expected.")
    head = "from pydantic import BaseModel, Field"
    out = text.replace(anchor, anchor + "\n    parent: BlogCategory | None = None", 1)
    out = out.replace(
        head,
        head + "\n\nfrom app.modules.blog.domain.models import BlogCategory",
        1,
    )
    target.write_text(out, encoding="utf-8")
    # Prove the injection landed before claiming the gate caught it.
    if "parent: BlogCategory | None = None" not in out:
        raise SystemExit("negative test: the typed-field sabotage did not land.")
    return "parent: BlogCategory | None = None"


def _run_gate(root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_eager_load_traps.py")],
        cwd=root,
        env={**__import__("os").environ, "PYTHONPATH": str(root)},
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _check(label: str, sabotage, expect_fragment: str, verify_file: str) -> bool:
    """Apply a sabotage to a private copy and assert the gate catches it."""
    tmp = Path(tempfile.mkdtemp(prefix="eager-neg-"))
    try:
        root = tmp / "backend"
        # Copy the code the gate reads; .env and bytecode are not needed.
        shutil.copytree(
            BACKEND / "app",
            root / "app",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(GATE, root / "scripts" / GATE.name)

        injected = sabotage(root)

        # Confirm the injection actually landed, and that the sabotaged file
        # still parses. A sabotage that broke the syntax would make the gate
        # report a registry-load failure, not the defect under test.
        target = root / verify_file
        landed = injected.split("\n")[0].strip() in target.read_text(encoding="utf-8")
        try:
            ast.parse(target.read_text(encoding="utf-8"))
            parses = True
        except SyntaxError as exc:
            parses = False
            print(f"        sabotaged file does not parse: {exc}")

        code, out = _run_gate(root)
        reported = expect_fragment in out
        ok = landed and parses and code == 1 and reported
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
        print(f"        injected: {injected}")
        print(
            f"        landed={landed} (want True), parses={parses} (want True), "
            f"gate exit={code} (want 1), reported={reported} (want True)"
        )
        if not ok:
            print("        ---- gate output ----")
            for line in out.splitlines()[:20]:
                print(f"        {line}")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _check_clean(root_copy_passes: bool) -> bool:
    """The unsabotaged tree must pass, or the gate is simply broken."""
    tmp = Path(tempfile.mkdtemp(prefix="eager-clean-"))
    try:
        root = tmp / "backend"
        shutil.copytree(
            BACKEND / "app",
            root / "app",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(GATE, root / "scripts" / GATE.name)
        code, out = _run_gate(root)
        ok = code == 0
        print(f"  {'ok  ' if ok else 'FAIL'}  clean tree passes (exit={code}, want 0)")
        if not ok:
            for line in out.splitlines()[:20]:
                print(f"        {line}")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _revert_fix(root: Path) -> None:
    """Put the original defect back, in a way that still parses.

    The field-by-field construction spans several lines; a one-line substring
    swap leaves the closing paren of the old call behind and the file stops
    importing, which would prove nothing about the request path.
    """
    target = root / "app" / "modules" / "blog" / "application" / "blog_service.py"
    text = target.read_text(encoding="utf-8")
    start = text.find("                BlogCategoryResponse(\n")
    if start == -1:
        raise SystemExit("negative test: the fixed call site moved; update this test.")
    end_marker = "                if post.category\n                else None\n            ),\n"
    end = text.find(end_marker, start)
    if end == -1:
        raise SystemExit("negative test: could not find the end of the call.")
    bad = "                BlogCategoryResponse.model_validate(post.category)\n            ),\n"
    target.write_text(text[:start] + bad + text[end + len(end_marker):], encoding="utf-8")
    ast.parse(target.read_text(encoding="utf-8"))  # must still parse


def _run_list_posts(root: Path) -> str:
    """Run list_posts against the live database from `root` and report the outcome."""
    script = (
        "import sys, asyncio\n"
        "sys.path.insert(0, '.')\n"
        "from app.core.database.session import async_session_factory\n"
        "from app.modules.blog.application.blog_service import BlogService\n"
        "import app.main\n"
        "async def go():\n"
        "    async with async_session_factory() as db:\n"
        "        r = await BlogService(db).list_posts(status=None, page=1, page_size=25)\n"
        "        print('RESULT: ok', r.total)\n"
        "try:\n"
        "    asyncio.run(go())\n"
        "except Exception as exc:\n"
        "    print('RESULT:', type(exc).__name__)\n"
        "    print('DETAIL:', str(exc)[:200])\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env={**__import__("os").environ, "PYTHONPATH": str(root)},
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return (proc.stdout or "") + (proc.stderr or "")


def _check_runtime(label: str, root: Path, want: str) -> bool:
    """Require the live list_posts call to end in `want` ('ok' or an error name)."""
    out = _run_list_posts(root)
    hit = f"RESULT: {want}" in out
    ok = hit
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    for line in out.splitlines():
        if line.startswith(("RESULT:", "DETAIL:")):
            print(f"        {line[:150]}")
    if not ok:
        print("        ---- output ----")
        for line in out.splitlines()[:15]:
            print(f"        {line}")
    return ok


def _check_fixed_code_works() -> bool:
    """The real, unsabotaged tree must serve the list without raising."""
    return _check_runtime("the fixed code lists posts with no error", BACKEND, "ok")


def main() -> int:
    print("negative test: eager-load trap gate")
    print("-" * 62)
    results = [
        _check_clean(True),
        _check(
            "model_validate on a whole ORM object (the original bug)",
            _sabotage_model_validate,
            "model_validate",
            "app/modules/blog/application/blog_service.py",
        ),
        _check(
            "a field typed as the ORM class",
            _sabotage_typed_field,
            "typed as the ORM class",
            "app/modules/blog/schemas/blog.py",
        ),
        _check(
            "a lazy relationship read wrapped in an expression (obj.rel or None)",
            _sabotage_composite_read,
            "post.category",
            "app/modules/blog/application/blog_service.py",
        ),
    ]
    # The runtime half, against the live database: the fix must work, and
    # reverting it must bring the 500 back.
    results.append(_check_fixed_code_works())
    tmp = Path(tempfile.mkdtemp(prefix="eager-rt-"))
    try:
        root = tmp / "backend"
        shutil.copytree(
            BACKEND / "app", root / "app",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        # The copy needs the env file the session factory reads.
        if (BACKEND / ".env").exists():
            shutil.copy2(BACKEND / ".env", root / ".env")
        _revert_fix(root)
        results.append(
            _check_runtime("reverting the fix brings MissingGreenlet back", root, "ValidationError")
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    passed = sum(results)
    print("-" * 62)
    print(f"{passed}/{len(results)} negative checks behaved correctly")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
