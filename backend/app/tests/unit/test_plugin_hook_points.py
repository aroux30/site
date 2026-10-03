"""Tests for the plugin hook points on the blog, comments and media.

The CMS page had four hook points and the blog had none, which is why a plugin
could restyle a page body and had no way to touch a post. These tests pin the
wiring: a hook that is declared and never dispatched is the failure mode this
project keeps finding, and it is silent.

The last two tests are the load-bearing ones. A filter on a public read is a
place a plugin could remove moderation, and the guard that stops it is the
public type filter, not the hook.
"""

from __future__ import annotations

import inspect
import re

import pytest

import app.modules.blog.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.shared.plugins import registry as reg


# -------------------------------------------------------- the names exist


def test_the_blog_hooks_are_declared():
    # A hook name a plugin binds to must not change: renaming one silently
    # unbinds every plugin that used it.
    for name in (
        reg.HOOK_POST_BEFORE_SAVE,
        reg.HOOK_POST_AFTER_SAVE,
        reg.HOOK_POST_AFTER_PUBLISH,
        reg.HOOK_POST_BODY_RENDER,
        reg.HOOK_POST_STATUS_CHANGE,
    ):
        assert name.startswith("blog.post.")
    assert reg.HOOK_COMMENT_BEFORE_CREATE == "blog.comment.before_create"
    assert reg.HOOK_COMMENT_AFTER_CREATE == "blog.comment.after_create"
    assert reg.HOOK_MEDIA_BEFORE_DELETE == "media.before_delete"


def test_the_page_hooks_are_untouched():
    # The page hooks predate these; a plugin already binds to them.
    assert reg.HOOK_PAGE_BEFORE_SAVE == "cms.page.before_save"
    assert reg.HOOK_PAGE_AFTER_PUBLISH == "cms.page.after_publish"
    assert reg.HOOK_PAGE_BODY_RENDER == "cms.page.body_render"
    assert reg.HOOK_SEO_METADATA == "seo.metadata"


# ------------------------------------------- every declared hook is dispatched


def _sources() -> dict[str, str]:
    from app.modules.blog.application import blog_service, comment_service
    from app.modules.content.application import cms_page_service

    return {
        "blog_service": inspect.getsource(blog_service),
        "comment_service": inspect.getsource(comment_service),
        "cms_page_service": inspect.getsource(cms_page_service),
    }


def test_every_blog_hook_is_dispatched_somewhere():
    """The gap this closes is exactly "declared and never dispatched".

    Asserted on the *constant name* rather than its string value: a call site
    writes ``apply_filters(HOOK_POST_BEFORE_SAVE, ...)``, and searching for the
    literal "blog.post.before_save" would find only the registry itself and
    report every hook as undispatched.
    """
    sources = _sources()
    for const in (
        "HOOK_POST_BEFORE_SAVE",
        "HOOK_POST_AFTER_SAVE",
        "HOOK_POST_AFTER_PUBLISH",
        "HOOK_POST_BODY_RENDER",
        "HOOK_POST_STATUS_CHANGE",
        "HOOK_COMMENT_BEFORE_CREATE",
        "HOOK_COMMENT_AFTER_CREATE",
    ):
        # A dispatch mentions the constant twice: in the import and at the call.
        hits = sum(src.count(const) for src in sources.values())
        assert hits >= 2, f"{const} is declared but never dispatched ({hits} mention)"


def _method_body(src: str, name: str) -> str:
    """The source of one method, not the rest of the file after it.

    Splitting on the name and taking everything to the end of the file made an
    earlier version of this test read `create_post`'s `sanitize_html` while
    asserting about `update_post` — so deleting the sanitiser from the update
    path left the test green. The body has to stop at the next method.
    """
    tail = src.split(f"async def {name}", 1)[1]
    m = re.search(r"\n    (?:async )?def ", tail)
    return tail[: m.start()] if m else tail


def test_before_save_runs_after_the_sanitizer():
    # The filter receives an already-sanitised dict, so a plugin cannot
    # re-inject the markup the sanitiser just removed. Order is the whole
    # property, and it has to be checked inside each method that does it.
    src = _sources()["blog_service"]

    update = _method_body(src, "update_post")
    assert "sanitize_html" in update, (
        "update_post no longer sanitises the body at all — a hook, or any "
        "future write path, could then store raw markup"
    )
    assert update.index("sanitize_html") < update.index("HOOK_POST_BEFORE_SAVE"), (
        "the filter must see sanitised content, not the raw request"
    )

    # In create_post the sanitiser runs *inside* the dict literal the filter
    # receives, so the comparison is: the dict is built (and sanitised) before
    # apply_filters is called with it.
    create = _method_body(src, "create_post")
    build = create.index("create_fields = {")
    sanitise = create.index("sanitize_html(data.content)", build)
    call = create.index("HOOK_POST_BEFORE_SAVE, create_fields", build)
    assert build < sanitise < call, (
        "the create filter must receive content the sanitizer already ran on"
    )


def test_the_body_render_hook_runs_after_expansion():
    # A hook that saw the raw token instead of the final HTML would have to
    # re-implement block expansion to be useful.
    src = _sources()["blog_service"]
    body = src.split("async def _render_content", 1)[1].split("async def ", 1)[0]
    assert body.index("render_body") < body.index("HOOK_POST_BODY_RENDER")


def test_after_publish_runs_after_the_commit():
    # A hook that fires before the commit and then reads the row would read the
    # pre-save state, which is the version the plugin is trying to react to.
    src = _sources()["blog_service"]
    create = src.split("async def create_post", 1)[1].split("async def update_post", 1)[0]
    # The *call* has to be after the commit, not the name: the constant is
    # imported near the top of the method, before anything runs.
    assert create.rindex("await self.db.commit()") < create.rindex(
        "HOOK_POST_AFTER_PUBLISH"
    ), "after_publish must fire once the row is committed"


# -------------------------------------------- the public path stays guarded


def test_a_plugin_cannot_widen_a_public_comment_list():
    """The type filter is a query clause, not a filter a plugin can undo.

    A plugin bound to any hook cannot make a private note visible: the row is
    excluded in SQL, so there is nothing in the response to re-add.
    """
    from app.modules.blog.application import comment_service

    src = inspect.getsource(comment_service.CommentService.list_comments)
    assert "comment_type == COMMENT_TYPE_COMMENT" in src


def test_the_comment_type_filter_is_a_query_clause_not_a_hook():
    """If the type filter were a hook, removing the hook would publish every
    private note.

    Checked per read path by name. A module-wide count is satisfied by the same
    filter repeated four times, so deleting the one in ``_get_replies`` still
    leaves three and the test passes — which is exactly the shape of the bug:
    the reply tree is reached from a different caller than the list, and it is
    the one most likely to be missed.
    """
    from app.modules.blog.application import comment_service

    for method in (
        "list_comments",
        "_get_replies",
        "get_comment_count",
        "get_resource_comment_count",
    ):
        src = inspect.getsource(getattr(comment_service.CommentService, method))
        assert "COMMENT_TYPE_COMMENT" in src, (
            f"{method} does not filter on comment_type, so a private note is "
            f"reachable through it. Every read path needs the filter as a SQL "
            f"clause — it must not be a hook, or removing the hook would "
            f"publish every note."
        )
        for line in src.split("\n"):
            if "COMMENT_TYPE_COMMENT" in line:
                assert "registry" not in line, (
                    f"the type filter must be a SQL clause, not a hook: "
                    f"{line.strip()}"
                )
