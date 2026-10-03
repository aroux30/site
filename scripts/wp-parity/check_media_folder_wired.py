"""The create-folder button must exist, because the endpoint alone is not a folder.

A folder that can only be made by uploading into it is not a folder an operator
can plan with. The endpoint, the service and the fixture all pass while the
library has no way to reach any of it — which is the same disconnect the
comment-trash gate guards against, and worth the same treatment.

Also pinned: the two states that are easy to get wrong in the UI. Creating a
folder that exists reports "already there" rather than failing, and the dialog
is Enter-submittable, because a modal with a button and no Enter is a modal
everybody clicks twice.

Run:  python scripts/wp-parity/check_media_folder_wired.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "media.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "media", "page.tsx")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "media", "api", "routes.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    for path in (CLIENT, PAGE, ROUTES):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    client, page, routes = (read(p) for p in (CLIENT, PAGE, ROUTES))

    # 1. backend
    check("a POST /folders route exists", '"/folders",' in routes
          and "create_media_folder" in routes)
    check("a DELETE /folders route exists", "delete_media_folder" in routes)
    check("the delete route takes the explicit flag",
          "delete_assets: bool = Field(" in routes)

    # 2. client
    check("the client can create a folder", "createFolder" in client)
    check("the client can delete one", "deleteFolder" in client)
    check("and the delete carries the flag", "delete_assets: deleteAssets" in client)

    # 3. page
    check("the page has a create handler", "handleCreateFolder" in page)
    check("the button opens the dialog", "setNewFolderOpen(true)" in page)
    check("the dialog is wired to the state", "newFolderOpen" in page)
    check("the dialog input exists", "media-new-folder" in page)
    check("Enter submits — otherwise the button gets double-clicked",
          'e.key === "Enter"' in page)
    check("the button is disabled while the path is empty",
          "!newFolderPath.trim()" in page)
    check("creating an existing folder is reported, not failed",
          "این پوشه از قبل وجود دارد" in page)

    # Read the create handler's own body rather than the page at large: the
    # invalidation has to be in *this* call, and a page-level check passes on
    # any other mutation that happens to invalidate the media list. The window
    # is the handler up to its closing `};` — anything wider reaches the next
    # function and finds its own invalidation.
    start = page.find("const handleCreateFolder = async () => {")
    if start == -1:
        body = ""
    else:
        end = page.find("\n  };", start)
        body = page[start:end if end != -1 else start + 900]
    check("the create handler is found", bool(body))
    check("and it invalidates the media list, so the tree refreshes",
          "invalidateKeys" in body and "MEDIA_QUERY_KEY" in body,
          "the create succeeds but the folder does not appear in the tree")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: an empty folder can be created from the library, and "
          "creating one that exists says so.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
