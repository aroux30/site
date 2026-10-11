"""Regression guard: default SEO generation must eager-load `category`.

Touching ``post.category`` on an async session without eager loading raises
``MissingGreenlet`` — the exact failure that took down the blog list
(memory: blog-nested-eager-load-missinggreenlet). The Titles & Meta wave
introduced the same access pattern in ``_generate_default_seo``; it was
caught live and fixed with ``selectinload``. This test pins the fix at the
source level, because a unit test with a stubbed session cannot raise the
greenlet error the way a real async session does.

Also pins the second bug found in the same block: ``post.focus_keyword`` was
read via ``hasattr`` off the BlogPost row — the column lives in
``seo_metadata`` (seokw1), so the focus keyword silently never reached the
template.
"""

from __future__ import annotations

import inspect

from app.modules.seo.application import seo_service


def test_generate_default_seo_eager_loads_category():
    source = inspect.getsource(seo_service.SEOService._generate_default_seo)
    assert "selectinload" in source, (
        "post.category must be eager-loaded with selectinload — a lazy access "
        "on the async session raises MissingGreenlet (the blog-list-500 bug)."
    )
    assert "BlogPost.category" in source


def test_generate_default_seo_reads_focus_keyword_from_seo_metadata():
    source = inspect.getsource(seo_service.SEOService._generate_default_seo)
    # The focus keyword lives on the seo_metadata table; reading
    # post.focus_keyword off the BlogPost row silently yields nothing.
    assert "SEOMetadata.focus_keyword" in source
    assert "hasattr(post, \"focus_keyword\")" not in source
