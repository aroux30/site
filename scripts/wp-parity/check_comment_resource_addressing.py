"""Guard: nothing may post a comment by reading `post_id` off a comment.

Reported by a peer session on the P0 "دیدگاه روی صفحات CMS" work: the
storefront was fixed to post by (resource_type, resource_id), but the admin
moderation tab still called `submitPostComment(replyTarget.post_id, ...)`. For a
CMS-page comment the API sends `post_id: null`, so the reply went to
`/blog/posts/null/comments` and 422'd — a moderator could read a page comment
and not answer it.

Two things had to be true for that to ship and stay invisible:
  1. `BlogComment.post_id` was typed `string`, so TypeScript reported no
     possible null even though the API always sends one for page comments; and
  2. no caller went through a helper that resolves the address for them.

So this asserts the type is honest and that no call site posts by post_id.
It is a shape check, not a runtime one —
`backend/scripts/verify_page_comment_reply.py` proves the runtime half
against the real database.

    python scripts/wp-parity/check_comment_resource_addressing.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOG_API = ROOT / "frontend" / "lib" / "api" / "blog.ts"
FRONTEND = ROOT / "frontend" / "app"
COMPONENTS = ROOT / "frontend" / "components"

# Calls that must not read a bare `post_id` off a comment object.
POSTS_BY_POST_ID = re.compile(r"submitPostComment\(\s*[\w.]+\.post_id")
COMMENTS_SCHEMA = ROOT / "backend" / "app" / "modules" / "blog" / "schemas" / "blog.py"

failures: list[str] = []


def check_type_is_honest() -> None:
    src = BLOG_API.read_text(encoding="utf-8")
    m = re.search(r"export interface BlogComment \{(.*?)\n\}", src, re.S)
    if not m:
        failures.append("could not find the BlogComment interface in blog.ts")
        return
    body = m.group(1)
    pm = re.search(r"^  post_id:\s*([^;]+);", body, re.M)
    if not pm:
        failures.append("BlogComment no longer declares post_id")
    elif "null" not in pm.group(1):
        failures.append(
            "BlogComment.post_id is typed %r but the API sends null for a "
            "CMS-page comment, so the type hides a real null" % pm.group(1).strip()
        )
    # Both halves of the address are required, and each is checked on its own.
    # An earlier version accepted the pair as satisfied by either one, so
    # dropping resource_type alone passed while every caller was left unable to
    # say what kind of object a page comment belongs to.
    for field in ("resource_type", "resource_id"):
        if not re.search(r"^  %s:" % field, body, re.M):
            failures.append(
                "BlogComment does not declare %s, so no caller can address a "
                "comment that has no post_id" % field
            )
    if "commentTarget" not in src:
        failures.append(
            "blog.ts no longer exports commentTarget, so callers have to "
            "hand-roll the resource_id ?? post_id fallback and get it wrong"
        )


def check_no_caller_posts_by_post_id() -> None:
    hits: list[str] = []
    for base in (FRONTEND, COMPONENTS):
        for path in base.rglob("*.tsx"):
            src = path.read_text(encoding="utf-8", errors="replace")
            for m in POSTS_BY_POST_ID.finditer(src):
                line = src[: m.start()].count("\n") + 1
                hits.append(
                    "%s:%d posts a comment from a comment's post_id"
                    % (path.relative_to(ROOT).as_posix(), line)
                )
    for h in hits:
        failures.append(h)


def check_backend_contract() -> None:
    """The backend must be the side that says post_id is optional.

    If it ever goes back to required, the frontend type and this guard are both
    describing a contract that no longer exists.
    """
    src = COMMENTS_SCHEMA.read_text(encoding="utf-8")
    m = re.search(r"class BlogCommentResponse\b.*?\n(.*?)\n\nclass ", src, re.S)
    if not m:
        failures.append("could not find BlogCommentResponse in the backend schema")
        return
    pm = re.search(r"^    post_id:\s*([^=]+)= None", m.group(1), re.M)
    if not pm:
        failures.append(
            "BlogCommentResponse.post_id is no longer optional in the backend, so "
            "the nullable frontend type and the addressing fix no longer apply"
        )


def main() -> int:
    check_type_is_honest()
    check_no_caller_posts_by_post_id()
    check_backend_contract()

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d problem(s). A comment is addressed by (resource_type, resource_id)." % len(failures))
        return 1

    print("PASS: comments are typed and addressed by resource, not by a nullable post_id.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
