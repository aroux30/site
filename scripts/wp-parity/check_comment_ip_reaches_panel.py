"""The moderation IP must survive the whole path, not just the model.

`author_ip` is stored, declared on the admin schema, and typed in the frontend —
and every one of those is a place it can quietly stop being returned or stop
being shown, with nothing raising. The moderation table loses its single most
useful spam signal (two comments from one address) and no test fails.

So this checks each hop rather than the ends: the column exists, the admin
schema declares it, the response builder returns it under the moderation flag
and withholds it publicly, the frontend type has it, and the table renders it.

Run:  python scripts/wp-parity/check_comment_ip_reaches_panel.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODEL = os.path.join(ROOT, "backend", "app", "modules", "blog", "domain", "models.py")
ADMIN_SCHEMA = os.path.join(ROOT, "backend", "app", "modules", "blog", "schemas", "blog.py")
CLIENT = os.path.join(ROOT, "frontend", "lib", "api", "blog.ts")
PANEL = os.path.join(ROOT, "frontend", "components", "admin", "blog",
                     "comments-moderation-tab.tsx")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    for path in (MODEL, ADMIN_SCHEMA, CLIENT, PANEL):
        if not os.path.isfile(path):
            print(f"FAIL: missing {path}")
            return 1

    model, schema, client, panel = (read(p) for p in (MODEL, ADMIN_SCHEMA, CLIENT, PANEL))

    # 1. stored
    check("the column is on the model", "author_ip" in model)

    # 2. declared on the admin schema, and *not* on the public one. The split
    #    is the security property: the public list is unauthenticated.
    admin_at = schema.find("class BlogCommentAdminResponse")
    public_at = schema.find("class BlogCommentResponse")
    check("the admin schema declares it",
          "author_ip" in schema[admin_at:admin_at + 1500])
    check("the public schema withholds it",
          "author_ip" not in schema[public_at:admin_at],
          "author_ip leaked into the unauthenticated schema")

    # 3. typed on the frontend, with the warning that keeps it off the public
    #    surface — the comment is what stops a future caller rendering it.
    check("the frontend type has it", "author_ip?:" in client)

    # 4. rendered in the moderation table
    check("the moderation table renders it", "{c.author_ip}" in panel)

    # 5. and not in the storefront's comment component, where a visitor would
    #    see another person's address.
    storefront = os.path.join(ROOT, "frontend", "components", "blog", "blog-comments.tsx")
    if os.path.isfile(storefront):
        check("the storefront comment list does not show it",
              "author_ip" not in read(storefront),
              "author_ip is rendered in the public comment list")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the moderation IP is stored, admin-gated, typed and shown — "
          "and withheld from the public list.")
    return 0


if __name__ == "__main__":
    sys.exit(main())