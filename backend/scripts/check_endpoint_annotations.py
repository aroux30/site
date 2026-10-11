"""Read-only gate: every route's type annotations must resolve at runtime.

Why this gate exists (2026-10-06): ``from __future__ import annotations``
turns every annotation into a string, and FastAPI evaluates those strings when
it builds each route. When a name is missing at runtime — imported only under
``TYPE_CHECKING``, or not imported at all — FastAPI cannot classify the
parameter and falls back to reading it as a *query* parameter. The
email-template preview and save routes were dead for exactly this reason:
their ``body: dict[str, Any]`` could not resolve (``Any`` was never imported),
so every request from the editor failed with
``422 "query.body Field required"`` before the handler ran.

Nothing failed at import time. The app booted, the routes answered 422, and
the status reads like the *client* sent a bad request. The same defect also
leaves every ``db: AsyncSession`` dependency standing on a fallback path that
happens to work today and depends on FastAPI's internals for that — the
``TYPE_CHECKING`` comment in pyproject.toml records that it broke startup
twice before.

This gate imports ``app.main`` (the real boot path) and evaluates every
endpoint's annotations with ``typing.get_type_hints``. A ``NameError`` here
is the same ``NameError`` FastAPI swallows and turns into the wrong parameter
location, so a red run is a route that will misbehave or 422.

Read-only: no database, no writes. Exits non-zero when any endpoint's
annotations do not resolve.

    cd backend && PYTHONPATH=. python scripts/check_endpoint_annotations.py
"""

from __future__ import annotations

import io
import sys
import typing

# The output carries an em-dash and route paths; Windows consoles default to
# cp1252 and would replace the dash with a replacement char mid-sentence.
# Same guard the other gates in this directory use.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    try:
        from app.main import app
    except Exception as exc:  # noqa: BLE001 — a boot failure is the finding
        print(
            f"importing app.main failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    failures: list[str] = []
    checked = 0
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        checked += 1
        try:
            typing.get_type_hints(endpoint)
        except Exception as exc:  # noqa: BLE001 — the annotation failure IS the finding
            path = getattr(route, "path", "?")
            methods = ",".join(sorted(getattr(route, "methods", None) or []))
            failures.append(f"{methods} {path}: {type(exc).__name__}: {exc}")

    if failures:
        print(
            f"{len(failures)} of {checked} endpoint(s) have annotations that do "
            f"not resolve at runtime:"
        )
        for line in failures:
            print(f"  {line}")
        print()
        print(
            "Each of these is a parameter FastAPI cannot classify: it silently "
            "falls back to a query parameter, so a JSON body never arrives and "
            "the request fails with 422 before the handler runs. Fix by "
            "importing the missing name at runtime (the codebase convention: "
            "see the TYPE_CHECKING note in pyproject.toml)."
        )
        return 1

    print(f"all {checked} endpoint annotations resolve at runtime")
    return 0


if __name__ == "__main__":
    sys.exit(main())
