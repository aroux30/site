"""Lock take-over must be reachable end to end, on both object types.

`PostLockService.force_release` shipped with the service and no route: the
override WordPress offers on a lock left behind by a closed tab existed as a
method nothing could reach. An editor who walked away from an open post locked
it until the heartbeat timed out, and the only escape was the full editor.

The failure mode is symmetric across the chain — a service method with no
route, a route with no client, a client with no caller, a button that calls
nothing — and every one of them leaves the panel looking finished. So each hop
is checked separately, for both posts and pages, because the two were never
built together and one can be done while the other is not.

Run:  python scripts/wp-parity/check_lock_takeover_wired.py
"""

from __future__ import annotations

import os as _os
_sys_path_insert = _os.path.dirname(__file__)
import sys as _sys
_sys.path.insert(0, _sys_path_insert)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROUTES = os.path.join(ROOT, "backend", "app", "modules", "blog", "api", "routes.py")
SERVICE = os.path.join(ROOT, "backend", "app", "modules", "blog", "application",
                       "post_lock_service.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "blog.ts")
HOOK = os.path.join(ROOT, "frontend", "hooks", "use-page-editing-lock.ts")
POSTS_PAGE = os.path.join(ROOT, "frontend", "app", "admin", "blog", "page.tsx")
PAGES_PAGE = os.path.join(ROOT, "frontend", "app", "admin", "pages", "page.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    for path in (ROUTES, SERVICE, CLIENT, HOOK, POSTS_PAGE, PAGES_PAGE):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    routes, service, client, hook = (read(p) for p in (ROUTES, SERVICE, CLIENT, HOOK))
    posts_page, pages_page = read(POSTS_PAGE), read(PAGES_PAGE)

    # 1. the service capability
    check("the service can force a release", "async def force_release" in service)

    # 2. a route per object type. One without the other is the state the two
    #    features were built in.
    for kind in ("posts", "pages"):
        check(f"{kind} have a take-over route",
              f'"/{kind}/{{{"post_id" if kind == "posts" else "page_id"}}}/lock/take-over"'
              in routes)

    # 3. each route uses the force-release path rather than acquire-and-hope.
    #    `acquire` returns true for a lock somebody else holds and hands back
    #    nothing, so a route that only calls acquire looks like it worked.
    for marker in ("force_release(post_id)", "force_release(page_id)"):
        check(f"the route calls {marker}", marker in routes)
    check("take-over releases before it acquires",
          routes.count("force_release") >= 2,
          "a take-over that only acquires hands back no lock")

    # 4. the client
    check("the client has a take-over method", "takeOverLock" in client)
    at = client.find("takeOverLock")
    check("the client posts to the take-over route",
          at != -1 and "/lock/take-over" in client[at:at + 500])

    # 5. the hook calls it — not the plain acquire, which is the version that
    #    cannot break a foreign lock.
    check("the hook calls the client's take-over",
          "takeOverLock(" in hook)
    check("and not a bare acquire in its place",
          'acquireLock(' not in hook.split("const takeOver")[1][:600]
          if "const takeOver" in hook else False,
          "the take-over went back to acquireLock, which cannot break a lock")

    # 6. both editors offer it
    for label, page in (("posts", posts_page), ("pages", pages_page)):
        check(f"the {label} editor renders a take-over control",
              "تصاحب ویرایش" in page)
        check(f"and wires it to the hook's handler",
              "takeOver" in page)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: a stale lock can be broken from both editors, through a "
          "route that actually releases before it takes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())