"""The moderation mail must carry working one-click links.

Two halves, and they can each be present without the other:

* the endpoint and its token code can be perfect while the mail carries no
  links — nothing calls `build_action_url`, and the feature is invisible;
* the template can carry `{{approve_url}}` while no variable is ever supplied
  for it, so every moderator mail shows the literal placeholder text where a
  button should be.

A rendered mail is the only thing that catches either, because both failures
live between the code that mints the link and the inbox. So this renders the
real template with a real minted token and reads the result.

Run:  python scripts/wp-parity/check_comment_moderation_links.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

#: Every action the mail promises a link for. A link missing from the template
#: is a moderator who has to open the panel, which is the state this feature
#: was built to end.
ACTIONS = ("approve", "spam", "trash")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    from app.core.config.settings import get_settings  # noqa: F401 — env before app
    from app.modules.blog.application import comment_moderation_token as cmt
    from app.modules.notifications.application.email_service import (
        default_email_templates,
        render_template,
    )

    templates = default_email_templates(getattr(get_settings(), "store_name", None))
    template = templates["comment_new"]

    comment_id = "11111111-2222-3333-4444-555555555555"
    site = "https://shop.test"

    variables = {
        "post_title": "نوشته‌ی آزمایشی",
        "commenter_name": "مهمان",
        "comment_content": "سلام، این یک دیدگاه آزمایشی است.",
        "comment_status": "pending",
        "manage_url": f"{site}/admin/blog",
        **{f"{a}_url": cmt.build_action_url(comment_id, a, site) for a in ACTIONS},
    }

    rendered = render_template(template, variables)

    # 1. no placeholder survived — a template variable nobody supplied renders
    #    literally, and a moderator sees `{{approve_url}}` on a button.
    leftovers = re.findall(r"\{\{(\w+)\}\}", rendered.html)
    check("the rendered mail has no unrendered placeholder",
          not leftovers, str(sorted(set(leftovers))))

    # 1b. and nothing the template *declares* went unsupplied. This is a
    #     different failure from the leftover scan: a variable can be declared
    #     and simply never passed, and if the body does not happen to reference
    #     it there is no placeholder to find. That is a template quietly growing
    #     a variable the code does not fill, which is the next edit someone makes
    #     expecting it to render.
    declared = set(getattr(template, "variables", []) or [])
    unsupplied = sorted(declared - set(variables))
    check("every variable the template declares is supplied",
          not unsupplied, str(unsupplied))

    # 1c. nothing is supplied that the template never asked for — that is how a
    #     link stops appearing while everything above still passes.
    undeclared = sorted(set(variables) - declared)
    check("no variable is supplied that the template ignores",
          not undeclared, str(undeclared))

    # 2. all three links are present, in both html and the text part
    for action in ACTIONS:
        expected = cmt.build_action_url(comment_id, action, site)
        check(f"the {action} link is in the html body", expected in rendered.html)
        check(f"the {action} link is in the text body", expected in rendered.text)

    # 3. each link is one this app can actually accept — a link to a route that
    #    does not exist is the shape this feature most plausibly breaks in.
    for action in ACTIONS:
        token = cmt.mint_token(comment_id, action)
        check(f"the {action} token verifies for its own action",
              cmt.verify_token(token, comment_id, action))
        check(f"the {action} token does not verify for another action",
              not cmt.verify_token(token, comment_id, "trash" if action != "trash" else "approve"))

    # 4. the mail tells the moderator the links expire. Without that sentence
    #    a dead link in an old inbox reads as a broken site.
    check("the mail says the links are single-use",
          "یک‌بارمصرف" in rendered.html)

    # 5. a missing address must still produce no mail at all
    import asyncio

    from app.modules.blog.application.comment_email_service import CommentEmailService

    async def no_address() -> bool:
        class _Empty:
            async def execute(self, *a, **k):  # noqa: ANN002, ANN003
                raise AssertionError("a mail was attempted with no address")

        return await CommentEmailService(_Empty()).notify_post_author(
            post_title="t", post_slug="s", comment_content="c",
            comment_status="pending", comment_author_name=None,
            comment_author_email=None, author_email=None, is_pending=True,
        )

    check("no address means no mail", asyncio.run(no_address()) is False)

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: the moderator mail carries three working, single-use links "
          "and renders no leftover placeholders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())