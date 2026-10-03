"""Page lock and autosave must be reachable, and not just declared.

WordPress applies one editing-lock mechanism to everything an author can
edit. Here the services were already generic — `PostLockService` and
`AutosaveService` take a bare UUID and never look at the model — and only the
routes were post-only. So a CMS page had no lock and no autosave: two editors
working on the same page overwrote each other silently, and a lost draft was
lost.

This checks the three layers, and the third is the one that matters most:
routes on both object types, a client that can address both, and a consumer in
the page editor. A route with no caller is the failure mode this gate exists to
prevent.

Run:  python scripts/wp-parity/check_page_lock_autosave_wired.py
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
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "blog.ts")
PAGE_EDITOR = os.path.join(ROOT, "frontend", "app", "admin", "pages", "page.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    for path in (ROUTES, CLIENT, PAGE_EDITOR):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    routes, client, editor = (read(p) for p in (ROUTES, CLIENT, PAGE_EDITOR))

    # 1. routes exist for pages, and only pages — a check that passes for both
    #    proves nothing about either.
    for suffix in ("/lock", "/lock/heartbeat", "/lock/take-over", "/autosave"):
        check(f"pages have a {suffix} route",
              f'"/pages/{{page_id}}{suffix}"' in routes)
        check(f"posts still have a {suffix} route",
              f'"/posts/{{post_id}}{suffix}"' in routes)

    # 2. the page access gate, so a lock route cannot be used to edit a page
    #    somebody else owns
    check("the page access guard exists", "_require_page_access" in routes)
    check("and it is used by the lock routes",
          routes.count("await _require_page_access") >= 4,
          str(routes.count("await _require_page_access")))

    # The take-over is its own route on both types: `acquire` reports
    # "already held" for a foreign lock, so a client that only had acquire
    # could never break one.
    check("the client has a take-over method", "takeOverLock" in client)

    # 3. the client can address both, and defaults to posts so existing
    #    callers keep working
    for fn in ("acquireLock", "releaseLock", "heartbeatLock", "checkLock",
               "saveAutosave", "getAutosave", "clearAutosave"):
        block = client[client.find(f"{fn}: async"):][:400]
        check(f"the client's {fn} takes an object kind",
              '"posts" | "pages"' in block,
              block[:90].replace("\n", " "))

    # 4. The consumer. Without this the routes exist and nobody calls them,
    #    which is the state the feature was in when this gate was written.
    #
    #    Counting "Lock" or "Autosave" occurrences is not enough: the *import*
    #    of the hook contains both words, so removing the call site entirely
    #    still leaves a passing check. This looks for the destructured hook call
    #    in the component body, which is what actually renders the banner.
    body = editor[editor.find("export default"):] if "export default" in editor else editor
    check("the page editor calls the lock hook",
          "usePageEditingLock(" in body,
          "the hook is imported but never called")
    check("the page editor calls the autosave hook",
          "usePageAutosave(" in body,
          "the hook is imported but never called")
    check("and renders the lock banner",
          "lockedByOther" in body and "تصاحب ویرایش" in body,
          "the lock state is computed but never shown")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: CMS pages have the same lock and autosave posts have, "
          "addressed by one client and used by the page editor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())