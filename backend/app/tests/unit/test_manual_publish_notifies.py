"""Regression: the MANUAL publish transition must announce the post.

``update_post`` was the path a writer uses almost every time, and it never
called ``_notify_published`` — only the scheduled-publish sweep did. So
notification watchers (and, later, instant-indexing hooks) saw only scheduled
posts publish. The fix fires on the *transition* into published; editing an
already-published post must NOT re-announce it.

Source-level pin: the trigger condition and the notify call must both exist
in ``update_post``, and the condition must compare against the previous
status (not just check the new one).
"""

from __future__ import annotations

import inspect

from app.modules.blog.application import blog_service


def _source() -> str:
    return inspect.getsource(blog_service.BlogService.update_post)


def test_update_post_calls_notify_published():
    source = _source()
    assert "_notify_published" in source, (
        "update_post must announce a manual publish — without it, only "
        "scheduled posts ever fire the publish notification/indexing hook."
    )


def test_trigger_requires_status_transition_not_just_status():
    source = _source()
    # The guard must reference the previous status; a bare
    # `status == PUBLISHED` check would re-announce every save.
    assert "previous_status" in source, (
        "The publish announcement must fire on the TRANSITION "
        "(previous_status != PUBLISHED), not on every save of a live post."
    )
    assert "previous_status = post.status" in source, (
        "previous_status must be captured BEFORE the update loop applies "
        "the new values."
    )


def test_announcement_happens_after_commit():
    """The notify runs post-commit: an announcement for a rolled-back write
    would announce a post that does not exist."""
    source = _source()
    commit_at = source.index("await self.db.commit()")
    notify_at = source.index("await self._notify_published([post])")
    assert notify_at > commit_at
