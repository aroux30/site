"""The media attach feature must be reachable, not just implemented.

A filter, an endpoint and a column that nothing reads is the exact shape of
"claimed but not implemented" this project has hit repeatedly: every backend
test passes, and an operator looking at the library sees a blank column and no
filter. So this reads the consumer chain the way the comment-trash gate does —
client method, page state, the filter control, and the attach/detach controls.

Two things worth pinning beyond presence:

  * the attach fires on blur, not on change. On change, a half-typed uuid
    404s on the first character and the field becomes unusable.
  * detaching has its own control. Without it the column is a one-way door —
    the operator can attach a file and never undo it.

Run:  python scripts/wp-parity/check_media_attach_wired.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "media.ts")
PAGE = os.path.join(ROOT, "frontend", "app", "admin", "media", "page.tsx")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "media", "api", "routes.py")
SCHEMA = os.path.join(ROOT, "backend", "app", "modules", "media",
                      "schemas", "media.py")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    for path in (CLIENT, PAGE, ROUTES, SCHEMA):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1
    client, page, routes, schema = (read(p) for p in (CLIENT, PAGE, ROUTES, SCHEMA))

    # 1. the backend half: route, filter params, schema field
    check("the attach route exists", '"/{asset_id}/attach"' in routes)
    check("the list filter takes post_id", "post_id: uuid.UUID | None = Query(" in routes)
    check("the list filter takes unattached", "unattached: bool = Query(" in routes)
    check("the contradictory pair is refused, not resolved",
          "post_id و unattached" in routes)
    check("the response carries post_id", "post_id: uuid.UUID | None = None" in schema)

    # 2. the client half
    check("the client exposes attach", "attachToPost" in client)
    check("the client list accepts the filters",
          "unattached?: boolean" in client and "post_id?: string" in client)
    check("the asset type carries post_id", "post_id?: string | null" in client)

    # 3. the page half
    check("the page holds the unattached filter", "unattachedOnly" in page)
    check("the page sends it to the API", "unattached: unattachedOnly" in page)
    check("there is a control for it", "media-unattached-filter" in page)
    check("changing it returns to page one",
          "setUnattachedOnly" in page and "setPage(1)" in page)

    # 4. attach and detach, both present
    check("the page has an attach handler", "handleAttach" in page)
    check("and a detach handler", "handleDetach" in page)
    check("detach calls the client with null",
          "attachToPost(detailAsset.id, null)" in page)

    # 5. the attach call has to live inside the blur handler, not merely
    #    somewhere on the page. Checking for `onBlur` alone passed while the
    #    call sat in an onChange — the shape that 404s on the first keystroke,
    #    because a half-typed uuid is not a post. So the handler's own body is
    #    read and the call looked for there.
    on_change_idx = page.find("onChange={() => {\n")
    blur_idx = page.find("onBlur={() => {\n")
    attach_in = [ln.strip() for ln in page.splitlines()
                 if "handleAttach(detailPostId)" in ln]
    check("the attach call is reachable from a handler", bool(attach_in))

    if blur_idx != -1:
        # The body runs from the handler's opening brace to the next `/>` of
        # the input, which is where the prop list ends in this component.
        body = page[blur_idx:blur_idx + 700]
        check("and it fires on blur, not per keystroke",
              "handleAttach(detailPostId)" in body,
              "the attach call is not inside the onBlur handler")
    else:
        check("and it fires on blur, not per keystroke", False,
              "no onBlur handler on the post field")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: media assets can be attached and detached from the library, "
          "and filtered both ways.")
    return 0


if __name__ == "__main__":
    sys.exit(main())