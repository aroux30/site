"""Every media path the frontend calls must exist on the server.

This exists because a bad edit truncated `media/api/routes.py` to seven lines,
which took the whole module out of the app: `main.py` raises on a router that
fails to import, so the server did not boot at all. The routes were rebuilt
from the service methods, and the part that made the loss detectable was not
any test — it was reading what the frontend calls and finding nine paths with
nothing behind them.

So the comparison is permanent and runs against the live app. Two directions:

  * a path the frontend calls that the server does not serve — a 404 the
    operator finds by clicking;
  * a permission codename on a media route that does not exist in the RBAC
    seed, which means the guard 403s everyone rather than the intended few.

Run:  python scripts/wp-parity/check_media_routes_reachable.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND = os.path.join(ROOT, "frontend")
BACKEND = os.path.join(ROOT, "backend")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def frontend_calls() -> set[tuple[str, str]]:
    """Every (METHOD, path) the frontend asks for, with `${var}` normalised.

    Method-aware on purpose. The first version compared paths only, and that
    was blind to two live bugs at once: `DELETE /media/trash/{id}` was called
    by the client with no route behind it (405), and `POST /media/trash/empty`
    existed but was *shadowed* by `POST /trash/{asset_id}` declared earlier
    (422). Both were "the path is served" under a path-only comparison.

    The path is the *first* string or template literal after the method name,
    found by scanning forward rather than by one regex over the whole call:
    `apiClient.post<{ ok: number; results: Array<Record<string, unknown>> }>`
    spans lines and nests `>`, which a single-pattern match drops silently —
    and a call this function cannot see is a call whose missing route it
    cannot report. Scanning forward has no such shape to get wrong.
    """
    found: set[tuple[str, str]] = set()
    method_re = re.compile(r"\.(get|post|put|patch|delete)\b")
    # The first quoted run after the method: "..." | '...' | `...`
    first_string_re = re.compile(r"[`\"']([^`\"'\n]+)[`\"']")
    for root, dirs, files in os.walk(FRONTEND):
        dirs[:] = [d for d in dirs if d not in {"node_modules", ".next", "out"}]
        for name in files:
            if not name.endswith((".ts", ".tsx")):
                continue
            try:
                with open(os.path.join(root, name), encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            for m in method_re.finditer(text):
                window = text[m.end() : m.end() + 400]
                s = first_string_re.search(window)
                if not s:
                    continue
                raw_path = s.group(1).split("?")[0]
                # The call must be about media at all. `/media` exactly is the
                # library list, and `/media/...` the rest.
                if not (raw_path == "/media" or raw_path.startswith("/media/")):
                    continue
                if "/application/" in raw_path:
                    continue
                tail = raw_path.rstrip("/").rsplit("/", 1)[-1]
                # A dotted literal with no template is a sample URL in prose
                # (`/media/x.png`), not a call. Everything else is one.
                if "." in tail and "{" not in tail:
                    continue
                found.add(
                    (m.group(1).upper(), re.sub(r"\$\{[^}]+\}", "{x}", raw_path))
                )
    return found


def server_routes() -> list[tuple[str, str]]:
    """The media routes as (METHOD, path), in declaration order.

    Order matters: FastAPI matches in it, so a parameterized route declared
    before a literal one swallows the literal. Returning the list rather than a
    set keeps that order visible to the checks below.
    """
    sys.path.insert(0, BACKEND)
    import app.main  # noqa: F401 — boots the app, which is the point

    prefix = "/api/v1"
    out: list[tuple[str, str]] = []
    for route in app.main.app.routes:
        path = getattr(route, "path", "")
        if "/media" not in path:
            continue
        for method in sorted(getattr(route, "methods", set()) or set()):
            if method in ("HEAD", "OPTIONS"):
                continue
            out.append((method, path.replace(prefix, "", 1)))
    return out


def shadowed_routes(routes: list[tuple[str, str]]) -> list[str]:
    """Literal media routes that a parameterized route declared earlier swallows.

    The shape of the bug this catches: `GET /{asset_id}` before `GET /trash`
    means `/trash` is parsed as an asset id, and the request 422s before any
    handler runs. Only compares same-method pairs, and only when the literal's
    first segment would be consumed by an earlier `{param}` in the same
    position — a generic `/{asset_id}/variant` does not shadow
    `/trash/empty`, because the literal is a different segment count.
    """
    problems: list[str] = []
    for i, (method, path) in enumerate(routes):
        segments = path.strip("/").split("/")
        if "{" in path:
            continue
        for method_early, path_early in routes[:i]:
            if method_early != method or "{" not in path_early:
                continue
            early_segments = path_early.strip("/").split("/")
            if len(early_segments) != len(segments):
                continue
            if all(
                e == s or (e.startswith("{") and e.endswith("}"))
                for e, s in zip(early_segments, segments)
            ):
                problems.append(f"{method} {path} is shadowed by {method_early} {path_early}")
                break
    return problems


def main() -> int:
    calls = frontend_calls()
    routes = server_routes()
    served = {path for _, path in routes}
    # The server's own templated segments are `{asset_id}`; the frontend's are
    # normalised to `{x}` so a literal id in a sample url does not count.
    served_generic = {re.sub(r"\{[^}]+\}", "{x}", p) for p in served}
    served_pairs = {(m, re.sub(r"\{[^}]+\}", "{x}", p)) for m, p in routes}

    print(f"  (method, path) pairs the frontend calls: {len(calls)}")
    if os.environ.get("MEDIA_GATE_VERBOSE"):
        for method, path in sorted(calls):
            print(f"    called: {method} {path}")
    print(f"  media routes the server serves: {len(routes)}")

    missing_paths = sorted(p for _, p in calls if p not in served_generic)
    check("every path the frontend calls is served", not missing_paths,
          "; ".join(missing_paths[:6]))

    missing_methods = sorted(
        f"{m} {p}" for m, p in calls if (m, p) not in served_pairs
        and p in served_generic
    )
    check("every (method, path) the frontend calls is served",
          not missing_methods, "; ".join(missing_methods[:6]))

    shadows = shadowed_routes(routes)
    check("no literal media route is shadowed by an earlier parameterized one",
          not shadows, "; ".join(shadows[:4]))

    # A route whose whole path is served but whose method is not: `DELETE
    # /media/folders` exists, `DELETE /media/{id}` does not.
    called_generic = {(m, p) for m, p in calls}
    orphans = sorted(
        f"{m} {p}" for m, p in served_pairs
        if (m, p) not in called_generic and "{x}" not in p
    )
    print(f"  served but never called from the frontend: {orphans or 'none'}")

    # The two codenames the module's guards use must exist in the RBAC seed,
    # or every request 403s with a message nobody can act on.
    from app.modules.rbac.application.permission_catalog import (  # noqa: E402
        PERMISSION_CATALOG,
    )
    seeded = set()
    for entry in PERMISSION_CATALOG:
        codename = (entry.get("codename") if isinstance(entry, dict)
                    else getattr(entry, "codename", None))
        if codename:
            seeded.add(codename)

    # Every codename the module's guards actually use, read off the file rather
    # than hard-coded here. A list of two literals in the gate would pass while
    # the code guards a third, misspelt name that nobody can be granted.
    with open(os.path.join(BACKEND, "app", "modules", "media", "api",
                           "routes.py"), encoding="utf-8") as fh:
        used = set(re.findall(r'RequirePermissions\("([a-z:_]+)"\)',
                              fh.read()))
    absent = sorted(used - seeded)
    print(f"  media codenames in use: {sorted(used)}")
    check("every media codename exists in the RBAC seed", not absent,
          "; ".join(absent))

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: every media path the frontend calls is served, and every "
          "guard's codename exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())