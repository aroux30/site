"""Link Genius: tokenizer, extraction, suggestion ranking, keyword maps.

Rank Math Pro parity (owner request 2026-10-11). The pieces pinned here:

* the Persian-aware tokenizer (ZWNJ folding, Arabic-char folding, no length
  floor, stopwords removed),
* TF-IDF cosine ranking (a topically-similar candidate outranks a random one;
  a candidate with zero overlap is dropped, not returned at score 0),
* link extraction (HTML parser, internal/external classification, URL
  normalization, dedup),
* keyword-map auto-linking (whole-word match, never inside an existing anchor,
  respects the per-post cap).

Several tests are negative/injection tests: they assert a guard FAILS when the
guard is removed, so a green suite means the guard is actually doing work.
"""

from __future__ import annotations

import inspect

import pytest


# ── Tokenizer ───────────────────────────────────────────────────────────────


def test_tokenizer_folds_arabic_yeh_and_kaf():
    """Arabic ي/ك and Persian ی/ک must produce the same token."""
    from app.modules.seo.application import link_text

    assert link_text.tokenize("كتاب") == link_text.tokenize("کتاب")
    assert link_text.tokenize("مي‌رود") == link_text.tokenize("می رود")


def test_tokenizer_drops_zwnj_but_keeps_both_parts():
    """A ZWNJ compound splits into its parts, and neither part is lost.

    Negative test: remove the ZWNJ substitution and «می‌شود» stays one token
    that never matches the separately-written «می شود».
    """
    from app.modules.seo.application import link_text

    tokens = link_text.tokenize("می‌شود")
    # «می» is a stopword, «شود» is too — but the POINT is that the compound is
    # split, not glued. Use a non-stopword compound to observe it.
    tokens2 = link_text.tokenize("پابجی‌موبایل")
    assert "پابجی" in tokens2
    assert "موبایل" in tokens2
    assert "پابجیموبایل" not in tokens2
    assert tokens == link_text.tokenize("می شود")


def test_tokenizer_keeps_short_persian_words():
    """No length floor: 3-char Persian words survive (the English rule is wrong
    for Persian, whose words are short)."""
    from app.modules.seo.application import link_text

    for word in ("کتاب", "خرید", "قیمت"):
        assert word in link_text.tokenize(word)


def test_tokenizer_removes_stopwords():
    from app.modules.seo.application import link_text

    tokens = link_text.tokenize("این کتاب را بخرید")
    assert "این" not in tokens
    assert "را" not in tokens
    assert "کتاب" in tokens


def test_tokenizer_strips_html_and_entities():
    from app.modules.seo.application import link_text

    tokens = link_text.tokenize("<p>کتاب&nbsp;خوب</p>")
    assert "کتاب" in tokens
    assert "خوب" in tokens


# ── TF-IDF ──────────────────────────────────────────────────────────────────


def test_cosine_ranks_similar_candidate_higher():
    from app.modules.seo.application import link_text

    target = link_text.tokenize("آموزش خرید پابجی موبایل و شارژ حساب")
    candidates = {
        "similar": link_text.tokenize("راهنمای شارژ حساب پابجی موبایل"),
        "unrelated": link_text.tokenize("طرز تهیه کیک شکلاتی خانگی"),
    }
    ranked = link_text.cosine_tfidf(target, candidates)
    assert ranked, "expected at least one suggestion"
    assert ranked[0][0] == "similar"


def test_cosine_drops_zero_overlap_candidate():
    """A candidate sharing nothing is dropped, not returned at score 0.

    Negative test: remove the `if score > 0.0` filter and the unrelated
    candidate appears in the list at 0.0 — a suggestion of "nothing in
    common", which is noise.
    """
    from app.modules.seo.application import link_text

    target = link_text.tokenize("آموزش خرید پابجی موبایل")
    candidates = {"unrelated": link_text.tokenize("طرز تهیه کیک شکلاتی")}
    ranked = link_text.cosine_tfidf(target, candidates)
    assert ranked == []


def test_cosine_empty_target_returns_empty():
    from app.modules.seo.application import link_text

    assert link_text.cosine_tfidf([], {"a": ["x"]}) == []
    assert link_text.cosine_tfidf(["x"], {}) == []


def test_contains_keyword_whole_word_only():
    """«پابجی» must not match inside «پابجیموبایل» when glued, but the tokenizer
    splits on ZWNJ so «پابجی‌موبایل» does contain «پابجی» as a word."""
    from app.modules.seo.application import link_text

    assert link_text.contains_keyword("من پابجی بازی می‌کنم", "پابجی")
    # Glued (no ZWNJ, no space) is one word — no match.
    assert not link_text.contains_keyword("پابجیموبایل عالیست", "پابجی")


def test_contains_keyword_empty_is_false():
    from app.modules.seo.application import link_text

    assert not link_text.contains_keyword("anything", "")
    assert not link_text.contains_keyword("", "x")


# ── URL normalization ───────────────────────────────────────────────────────


def test_normalize_url_lowercases_host_and_strips_fragment():
    from app.modules.seo.application import link_extraction_service as les

    assert (
        les.normalize_url("HTTPS://ArouxShop.com/Blog/Post/#section")
        == "https://arouxshop.com/Blog/Post"
    )


def test_normalize_url_trims_trailing_slash():
    from app.modules.seo.application import link_extraction_service as les

    assert les.normalize_url("https://x.com/a/") == "https://x.com/a"
    assert les.normalize_url("https://x.com/a") == "https://x.com/a"


def test_url_hash_is_stable_across_spellings():
    from app.modules.seo.application import link_extraction_service as les

    a = les.url_hash(les.normalize_url("https://X.com/a/"))
    b = les.url_hash(les.normalize_url("https://x.com/a#frag"))
    assert a == b


def test_slug_from_blog_url():
    from app.modules.seo.application import link_extraction_service as les

    assert les._slug_from_url("https://x.com/blog/pubg-mobile") == "pubg-mobile"
    # A product URL is internal but not a post slug.
    assert les._slug_from_url("https://x.com/products/x") is None


# ── Extraction ──────────────────────────────────────────────────────────────


def test_extract_anchors_parses_attribute_order():
    """An HTML parser, not a regex: attribute order must not matter.

    Negative test: a regex like `<a href="...">` fails when `rel` comes first;
    the parser does not.
    """
    from app.modules.seo.application import link_extraction_service as les

    html = '<a rel="nofollow noopener" target="_blank" href="/blog/x">متن</a>'
    anchors = les.extract_anchors(html)
    assert anchors == [("/blog/x", "متن", True, True)]


def test_extract_anchors_handles_multiline():
    from app.modules.seo.application import link_extraction_service as les

    html = '<a\n  href="/blog/y"\n  class="x">متن لینک</a>'
    anchors = les.extract_anchors(html)
    assert anchors[0][0] == "/blog/y"
    assert anchors[0][1] == "متن لینک"


def test_extract_anchors_survives_malformed_html():
    from app.modules.seo.application import link_extraction_service as les

    # Unclosed tag — must not raise.
    assert isinstance(les.extract_anchors('<a href="/x">no close'), list)


# ── Keyword map auto-linking ────────────────────────────────────────────────


def test_apply_keyword_map_inserts_link():
    from app.modules.seo.application import link_map_service as lms

    new, n = lms.apply_keyword_map(
        "<p>این پابجی عالیست</p>",
        keywords=["پابجی"],
        target_url="/products/pubg",
    )
    assert n == 1
    assert '<a href="/products/pubg">پابجی</a>' in new


def test_apply_keyword_map_respects_cap():
    from app.modules.seo.application import link_map_service as lms

    content = "<p>پابجی خوب است. پابجی عالی است. پابجی محشر است.</p>"
    new, n = lms.apply_keyword_map(
        content, keywords=["پابجی"], target_url="/x", max_links_per_post=2
    )
    assert n == 2
    assert new.count("<a ") == 2


def test_apply_keyword_map_never_nests_inside_existing_anchor():
    """A keyword already inside an <a> must not be wrapped again.

    Negative test: a naive string replace would produce nested anchors; the
    walker skips text inside an existing anchor.
    """
    from app.modules.seo.application import link_map_service as lms

    content = '<p><a href="/other">پابجی</a> و پابجی دیگر</p>'
    new, n = lms.apply_keyword_map(
        content, keywords=["پابجی"], target_url="/x", max_links_per_post=5
    )
    # Only the SECOND (bare) occurrence is linked; the one inside <a> is left.
    assert n == 1
    assert '<a href="/other">پابجی</a>' in new  # untouched
    assert new.count("<a ") == 2  # original + one inserted


def test_apply_keyword_map_skips_headings_and_code():
    from app.modules.seo.application import link_map_service as lms

    content = "<h2>پابجی</h2><code>پابجی</code><p>پابجی</p>"
    new, n = lms.apply_keyword_map(
        content, keywords=["پابجی"], target_url="/x", max_links_per_post=5
    )
    assert n == 1
    # The heading and code keyword stay unwrapped.
    assert "<h2>پابجی</h2>" in new
    assert "<code>پابجی</code>" in new


def test_apply_keyword_map_counts_existing_links_against_cap():
    """max_links_per_post is the TOTAL, including links that already exist."""
    from app.modules.seo.application import link_map_service as lms

    content = '<p><a href="/x">موجود</a> و پابجی</p>'
    _new, n = lms.apply_keyword_map(
        content, keywords=["پابجی"], target_url="/x", max_links_per_post=1
    )
    # One link to /x already exists → cap of 1 means no new link.
    assert n == 0


def test_apply_keyword_map_empty_inputs_noop():
    from app.modules.seo.application import link_map_service as lms

    assert lms.apply_keyword_map("", keywords=["x"], target_url="/y") == ("", 0)
    assert lms.apply_keyword_map("<p>x</p>", keywords=[], target_url="/y") == ("<p>x</p>", 0)
    assert lms.apply_keyword_map("<p>x</p>", keywords=["x"], target_url="") == ("<p>x</p>", 0)


def test_keyword_map_longest_keyword_wins():
    """«پابجی موبایل» must match before «پابجی» so the more specific phrase
    becomes the anchor text."""
    from app.modules.seo.application import link_map_service as lms

    new, n = lms.apply_keyword_map(
        "<p>پابجی موبایل بازی خوبی است</p>",
        keywords=["پابجی", "پابجی موبایل"],
        target_url="/x",
        max_links_per_post=1,
    )
    assert n == 1
    assert ">پابجی موبایل</a>" in new


# ── Route shadowing guard (the documented trap) ─────────────────────────────


def test_link_genius_routes_registered_before_generic_metadata_route():
    """`DELETE /admin/seo/link-maps/{id}` must not be swallowed by the generic
    `DELETE /admin/seo/{resource_type}/{resource_id}` handler.

    Negative test: swap the include order in `api/__init__.py` and the generic
    two-segment route is registered first, so the link-map delete answers
    `resource_type="link-maps"` and deletes nothing.
    """
    from app.modules.seo.api import admin_router

    paths = [r.path for r in admin_router.routes]
    link_map_idx = next(
        i for i, p in enumerate(paths) if p.endswith("/link-maps/{map_id}")
    )
    generic_idx = next(
        i
        for i, p in enumerate(paths)
        if p.endswith("/{resource_type}/{resource_id}")
    )
    assert link_map_idx < generic_idx, (
        "the Link Genius routes must be registered before the generic "
        "metadata route, or the delete is shadowed"
    )


def test_suggestion_service_uses_parser_not_regex_for_extraction():
    """Source guard: extraction uses html.parser, not a href regex.

    Negative test: replace `_AnchorCollector` with a regex and this fails.
    """
    from app.modules.seo.application import link_extraction_service as les

    src = inspect.getsource(les)
    assert "HTMLParser" in src
    assert "_AnchorCollector" in src


async def test_routes_reachable_over_http():
    """The routes exist AND are wired: public answers, admin requires auth.

    A 404 for the admin route would mean it was never registered (or was
    shadowed); a 401 proves the route exists and is permission-gated. The
    public route must answer 200 for a real published slug. This is the
    "a 200 in my env is not a 200 in theirs" check — registration alone does
    not prove the ASGI app serves the path.
    """
    import httpx
    from sqlalchemy import select

    from app.core.database.session import async_session_factory, engine
    from app.main import app
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus

    async with async_session_factory() as db:
        slug = (
            await db.execute(
                select(BlogPost.slug)
                .where(
                    BlogPost.status == BlogPostStatus.PUBLISHED,
                    BlogPost.deleted_at.is_(None),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
    assert slug is not None, "no published post in the test DB"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        public = await client.get(f"/api/v1/seo/blog/{slug}/related?limit=3")
        assert public.status_code == 200, public.text
        assert "items" in public.json()

        # Admin route: exists (not 404) and is gated (401/403).
        admin = await client.get("/api/v1/admin/seo/link-maps")
        assert admin.status_code in (401, 403), (
            f"expected auth gate, got {admin.status_code} — a 404 means the "
            "route is missing or shadowed"
        )
    await engine.dispose()


# ── Live DB roundtrips ──────────────────────────────────────────────────────


async def test_index_post_links_roundtrip_and_incoming():
    """Live DB: index a post's links, then read the reverse-link edge.

    Creates two throwaway posts, links the second from the first, indexes,
    and asserts the incoming-link query returns the first. Cleans up after
    itself. Uses the shared test database.
    """
    import uuid as _uuid

    from sqlalchemy import delete, select

    from app.core.database.session import async_session_factory, engine
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.seo.application import link_extraction_service as les
    from app.modules.seo.domain.link_models import SeoInternalLink
    from app.modules.users.domain.models import User

    async with async_session_factory() as db:
        author = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        assert author is not None, "no user in the test DB to author a post"

        suffix = _uuid.uuid4().hex[:8]
        target = BlogPost(
            author_id=author.id,
            title="مقصد تست",
            slug=f"pytest-lg-target-{suffix}",
            content="محتوای مقصد",
            status=BlogPostStatus.PUBLISHED,
        )
        source = BlogPost(
            author_id=author.id,
            title="منبع تست",
            slug=f"pytest-lg-source-{suffix}",
            content=f'<p>متن <a href="/blog/pytest-lg-target-{suffix}">مقصد</a></p>',
            status=BlogPostStatus.PUBLISHED,
        )
        db.add(target)
        db.add(source)
        await db.commit()
        await db.refresh(target)
        await db.refresh(source)

        try:
            n = await les.index_post_links(
                db,
                post_id=source.id,
                content=source.content,
                site_hosts={"arouxshop.com", "www.arouxshop.com"},
            )
            assert n == 1

            row = (
                await db.execute(
                    select(SeoInternalLink).where(SeoInternalLink.post_id == source.id)
                )
            ).scalar_one()
            assert row.target_post_id == target.id
            assert row.link_type == "internal"
            assert row.anchor_text == "مقصد"

            # Re-indexing replaces, not duplicates.
            n2 = await les.index_post_links(
                db,
                post_id=source.id,
                content=source.content,
                site_hosts={"arouxshop.com"},
            )
            assert n2 == 1
            count = (
                await db.execute(
                    select(SeoInternalLink).where(SeoInternalLink.post_id == source.id)
                )
            ).scalars().all()
            assert len(count) == 1
        finally:
            await db.execute(
                delete(SeoInternalLink).where(
                    SeoInternalLink.post_id.in_([source.id, target.id])
                )
            )
            await db.execute(
                delete(BlogPost).where(BlogPost.id.in_([source.id, target.id]))
            )
            await db.commit()
    await engine.dispose()


async def test_suggest_links_ranks_topically_similar_post_first():
    """Live DB: a candidate sharing vocabulary outranks an unrelated one."""
    import uuid as _uuid

    from sqlalchemy import delete, select

    from app.core.database.session import async_session_factory, engine
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.seo.application import link_suggestion_service as lss
    from app.modules.users.domain.models import User

    async with async_session_factory() as db:
        author = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        assert author is not None

        suffix = _uuid.uuid4().hex[:8]
        source = BlogPost(
            author_id=author.id,
            title="آموزش شارژ حساب پابجی موبایل",
            slug=f"pytest-lg-src2-{suffix}",
            content="<p>در این مقاله روش‌های شارژ حساب بازی پابجی موبایل را یاد می‌گیرید.</p>",
            status=BlogPostStatus.PUBLISHED,
        )
        similar = BlogPost(
            author_id=author.id,
            title="راهنمای شارژ حساب پابجی موبایل",
            slug=f"pytest-lg-sim-{suffix}",
            content="<p>شارژ حساب پابجی موبایل از طریق کد و گیفت کارت.</p>",
            status=BlogPostStatus.PUBLISHED,
        )
        unrelated = BlogPost(
            author_id=author.id,
            title="طرز تهیه کیک شکلاتی",
            slug=f"pytest-lg-unrel-{suffix}",
            content="<p>آرد و شکر و کاکائو را مخلوط کنید.</p>",
            status=BlogPostStatus.PUBLISHED,
        )
        for p in (source, similar, unrelated):
            db.add(p)
        await db.commit()
        for p in (source, similar, unrelated):
            await db.refresh(p)

        try:
            results = await lss.suggest_links(db, post_id=source.id, limit=10)
            ids = [r["post_id"] for r in results]
            assert similar.id in ids, "the similar post must be suggested"
            # The unrelated post shares no tokens → dropped entirely.
            assert unrelated.id not in ids
        finally:
            await db.execute(
                delete(BlogPost).where(
                    BlogPost.id.in_([source.id, similar.id, unrelated.id])
                )
            )
            await db.commit()
    await engine.dispose()


async def test_apply_link_map_writes_into_post_and_reindexes():
    """Live DB: a saved map, applied to one post, edits the body and the index.

    Exercises the full write path the admin "apply" action takes: create the
    map (with variations), apply it to a post, and assert both the body edit
    and the refreshed link index. Cleans up its rows.
    """
    import uuid as _uuid

    from sqlalchemy import delete, select

    from app.core.database.session import async_session_factory, engine
    from app.modules.blog.domain.models import BlogPost, BlogPostStatus
    from app.modules.seo.application import link_extraction_service as les
    from app.modules.seo.domain.link_models import (
        SeoInternalLink,
        SeoLinkMap,
        SeoLinkMapVariation,
    )
    from app.modules.users.domain.models import User

    async with async_session_factory() as db:
        author = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        assert author is not None

        suffix = _uuid.uuid4().hex[:8]
        target_slug = f"pytest-lg-map-target-{suffix}"
        post = BlogPost(
            author_id=author.id,
            title="مقالهٔ تست نقشه",
            slug=f"pytest-lg-map-post-{suffix}",
            content="<p>برای بازی پابجی باید حساب بسازی. پابجی بازی محبوبی است.</p>",
            status=BlogPostStatus.PUBLISHED,
        )
        link_map = SeoLinkMap(
            name=f"map-{suffix}",
            target_url=f"/blog/{target_slug}",
            max_links_per_post=1,
            auto_link_on_publish=False,
            is_active=True,
        )
        db.add(post)
        db.add(link_map)
        await db.commit()
        await db.refresh(post)
        await db.refresh(link_map)
        db.add(SeoLinkMapVariation(map_id=link_map.id, keyword="پابجی", kind="manual"))
        await db.commit()

        try:
            # Read the variations with a direct query (the map's `variations`
            # collection was loaded empty before the row existed).
            keywords = (
                await db.execute(
                    select(SeoLinkMapVariation.keyword).where(
                        SeoLinkMapVariation.map_id == link_map.id
                    )
                )
            ).scalars().all()
            assert list(keywords) == ["پابجی"]

            from app.modules.seo.application import link_map_service as lms

            new_content, inserted = lms.apply_keyword_map(
                post.content,
                keywords=list(keywords),
                target_url=link_map.target_url,
                max_links_per_post=link_map.max_links_per_post,
            )
            assert inserted == 1  # cap of 1, though the body says it twice
            post.content = new_content
            await db.commit()

            await les.index_post_links(
                db,
                post_id=post.id,
                content=new_content,
                site_hosts={"arouxshop.com"},
            )
            links = (
                await db.execute(
                    select(SeoInternalLink).where(SeoInternalLink.post_id == post.id)
                )
            ).scalars().all()
            assert len(links) == 1
            assert links[0].link_type == "internal"
        finally:
            await db.execute(
                delete(SeoInternalLink).where(SeoInternalLink.post_id == post.id)
            )
            await db.execute(
                delete(SeoLinkMapVariation).where(SeoLinkMapVariation.map_id == link_map.id)
            )
            await db.execute(delete(SeoLinkMap).where(SeoLinkMap.id == link_map.id))
            await db.execute(delete(BlogPost).where(BlogPost.id == post.id))
            await db.commit()
    await engine.dispose()
