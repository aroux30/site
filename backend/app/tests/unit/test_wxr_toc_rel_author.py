"""The three 2026-10-08 article-fidelity fixes, each pinned by sabotage.

1. **ToC linking** (`shared/content/toc.py`): a migrated article's ToC was an
   inert `<ol>` — clicking an entry did nothing (true on the source site too).
   `add_toc_links` gives the matching headings `id`s and wraps the entries in
   `#toc-N` anchors. Negative test: set `_MATCH_RATIO` to 1.1 and no list ever
   qualifies; the assertions below go red.

2. **Link rel preserved** (`shared/content/html_sanitizer.py`): the sanitizer
   used `bleach.callbacks.nofollow`, which stamped `rel="nofollow"` on every
   link that lacked one — internal store links included — and the comment
   above it promised `noopener` instead. Negative test: swap `_link_rel` back
   to `bleach.callbacks.nofollow` and the internal-link assertion fails.

3. **Author display name** (`wxr_import._apply_author_display_name` +
   `blog_service.get_author_name`): imported articles showed "کاربر 0000"
   (phone-tail fallback) because `display_name` was never read. Negative
   test: drop the display_name branch from `get_author_name` and the author
   test's predicate flips.
"""

from __future__ import annotations

import re

from app.shared.content.html_sanitizer import sanitize_html
from app.shared.content.toc import add_toc_links

TOC_ARTICLE = """
<h1>راهنما</h1>
<h2>فهرست مطالب</h2>
<ol><li>معرفی کلی بازی</li><li>راهنمای دانلود</li><li>سوالات متداول</li></ol>
<h2>1. معرفی کلی بازی</h2><p>متن یک</p>
<h2>2. راهنمای دانلود</h2><p>متن دو</p>
<h2>3. سوالات متداول</h2><p>متن سه</p>
"""


def test_toc_entries_link_to_their_headings():
    """Every ToC entry becomes an anchor; every anchor target exists.

    Negative test: raise `_MATCH_RATIO` above 1 so no list qualifies — the
    link count comes back 0 and this fails.
    """
    out = add_toc_links(TOC_ARTICLE)
    links = re.findall(r'<a href="#(toc-\d+)">([^<]*)</a>', out)
    assert len(links) == 3
    ids = set(re.findall(r'id="(toc-\d+)"', out))
    for href, _text in links:
        assert href in ids, f"anchor {href} has no target"


def test_toc_ids_follow_document_order():
    """First section is toc-1 — not the last one (a bug found in review).

    Negative test: assign ids while walking the list in reverse; the first
    heading then carries toc-3 and this fails.
    """
    out = add_toc_links(TOC_ARTICLE)
    first_h2 = re.search(r'<h2[^>]*id="(toc-\d+)"[^>]*>1\. معرفی', out)
    assert first_h2 is not None
    assert first_h2.group(1) == "toc-1"


def test_toc_is_idempotent():
    """Second render changes nothing — no double-wrapped links.

    Negative test: drop the `if "<a" in inner` guard and the second pass
    nests an anchor inside an anchor; the equality fails.
    """
    once = add_toc_links(TOC_ARTICLE)
    twice = add_toc_links(once)
    assert twice == once
    assert once.count('<a href="#toc-1">') == 1


def test_ordinary_list_is_not_linked():
    """A bullet list that is not a ToC must not sprout anchors.

    Negative test: lower `_MIN_MATCHES` to 0 and this list (one item shares
    no heading) gains links.
    """
    html = "<h2>یک تیتر</h2><ul><li>آیتم نامرتبط</li><li>آیتم دیگر</li></ul>"
    out = add_toc_links(html)
    assert '<a href="#toc-' not in out


def test_internal_links_keep_no_rel_and_external_nofollow_survives():
    """The sanitizer must not invent nofollow, nor drop an authored one.

    Negative test: restore `bleach.callbacks.nofollow` as the callback — the
    internal link gains `rel="nofollow"` and the first assertion fails.
    """
    internal = sanitize_html(
        '<a href="https://arouxshop.com/category/x/">داخلی</a>'
    )
    assert "rel=" not in internal, "internal link must stay dofollow"

    external = sanitize_html(
        '<a href="https://www.pubgmobile.com/" target="_blank" rel="noopener nofollow">ext</a>'
    )
    assert "nofollow" in external, "authored nofollow must survive"

    # And a new-tab link without rel gets noopener, not nofollow.
    blank = sanitize_html('<a href="https://example.com/" target="_blank">x</a>')
    assert "noopener" in blank
    assert "nofollow" not in blank


async def test_author_display_name_preferred_over_phone_fallback():
    """An author with only a display_name must NOT render as "کاربر 0000".

    Negative test: remove the `display` branch from
    `BlogService.get_author_name` and this returns "کاربر 0000" — the exact
    live report.

    Uses the real database (shared with the stack) and restores the profile
    row afterwards.
    """
    import uuid

    from sqlalchemy import delete, select

    from app.core.database.session import async_session_factory
    from app.modules.blog.application.blog_service import BlogService
    from app.modules.users.domain.models import User, UserProfile

    uid = uuid.UUID("5ae8aeaa-715e-459b-995a-0a91fdb1deff")
    async with async_session_factory() as db:
        user = await db.get(User, uid)
        assert user is not None, "admin user missing from test database"
        profile = (
            await db.execute(select(UserProfile).where(UserProfile.user_id == uid))
        ).scalar_one_or_none()
        original = profile.display_name if profile else None
        try:
            if profile is None:
                db.add(UserProfile(user_id=uid, display_name="آروکس"))
            else:
                profile.display_name = "آروکس"
            await db.flush()
            name = await BlogService(db).get_author_name(uid)
            assert name == "آروکس"
        finally:
            await db.rollback()
            # rollback restores whatever was there; nothing to undo
        _ = original
    from app.core.database.session import engine

    await engine.dispose()


def test_body_h1_is_demoted_to_h2():
    """A migrated body's own <h1> must not create a second page title.

    Negative test: remove `demote_body_h1` from `render_body`'s chain and the
    page renders two H1s — the live SEO bug found in the final check.
    """
    from app.shared.content.heading_normalizer import demote_body_h1

    out = demote_body_h1('<h1>عنوان مقاله</h1><h2>بخش</h2>')
    assert "<h1" not in out
    assert "<h2>عنوان مقاله</h2>" in out
    # Idempotent: nothing left to demote on a second pass.
    assert demote_body_h1(out) == out
