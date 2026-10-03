"""The comment resource-consistency constraint must accept what the service allows.

This exists because a service-level fix is not enough on its own. Turning on
`supports_comments` made `create_comment` accept a comment on a custom post type
entry — and the INSERT was then refused by a check constraint that matched
exactly two shapes: a blog post and a CMS page. The flag was consulted, the
entry passed, and three lines later the database said no.

Two checks, because each catches a different failure:

  * the constraint mentions `content_entry` — so a migration that only touched
    the service is caught;
  * and it still enforces the two original shapes — a migration that replaced
    the check with something permissive would otherwise pass the first check
    and let a blog post with a mismatched `resource_id` into the table.

Run:  python scripts/wp-parity/check_comment_resource_constraint.py
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
sys.path.insert(0, os.path.join(ROOT, "backend"))

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    import asyncio

    import app.main  # noqa: F401 — boots the app, which is the point
    from sqlalchemy import text

    from app.core.database.session import _build_engine, async_sessionmaker

    async def definition() -> str | None:
        eng = _build_engine()
        try:
            async with async_sessionmaker(eng)() as db:
                return (await db.execute(text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname = 'ck_blog_comments_resource_consistency'"
                ))).scalar()
        finally:
            await eng.dispose()

    ddl = asyncio.run(definition())
    if ddl is None:
        print("  FAIL the constraint is missing from blog_comments")
        return 1

    check("the constraint exists", True)
    check("it accepts a custom post type entry", "content_entry" in ddl, ddl[:200])
    # The original two shapes must survive: a permissive replacement that says
    # "no constraint" would otherwise pass the check above.
    check("it still requires post_id on a blog_post",
          "post_id IS NOT NULL" in ddl)
    check("it still requires resource_id = post_id for a blog_post",
          "post_id" in ddl and "resource_id = post_id" in ddl)
    check("it still forbids post_id on a page",
          "cms_page" in ddl and "post_id IS NULL" in ddl)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the comment constraint accepts all three target shapes and "
          "still enforces the original two.")
    return 0


if __name__ == "__main__":
    sys.exit(main())