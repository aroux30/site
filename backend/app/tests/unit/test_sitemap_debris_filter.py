"""F-05 (SEO audit 2026-10-10): sitemap must not advertise test debris.

The live DB held 37 empty categories: 34 test/import debris and 3 real
Persian ones (تلگرام، گیفت-کارت، دسته-بندی-محصولات). The sitemap listed all
38 — and the 3 real ones are ALSO empty, so an "empty = skip" rule would
silently undo the F-01 fix. The filter is therefore an explicit denylist.

Negative test: empty `_DEBRIS_CATEGORY_SLUGS` and the first case fails;
add "تلگرام" to it and the second case fails (the guard against the
emptiness-rule regression).
"""

from __future__ import annotations

from app.modules.content.application import sitemap_service


def test_debris_slugs_are_denylisted():
    assert "probe" in sitemap_service._DEBRIS_CATEGORY_SLUGS
    assert "woodmart" in sitemap_service._DEBRIS_CATEGORY_SLUGS
    assert "p1attach-term0-f665faec" in sitemap_service._DEBRIS_TAG_SLUGS


def test_real_persian_categories_are_not_denylisted():
    """The three F-01 categories must stay advertised despite being empty.

    This is the lock against "skip empty categories" — a rule that would
    look correct and silently hide the real ones.
    """
    for slug in ("تلگرام", "گیفت-کارت", "دسته-بندی-محصولات"):
        assert slug not in sitemap_service._DEBRIS_CATEGORY_SLUGS
