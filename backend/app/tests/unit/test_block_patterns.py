"""Unit tests for block patterns domain service."""

from __future__ import annotations

import pytest

from app.core.exceptions.handlers import NotFoundError
from app.modules.content.domain.block_patterns import (
    PATTERNS,
    BlockPattern,
    get_pattern,
    grouped_patterns,
    render_pattern,
)


def test_patterns_registry_has_expected_entries():
    """Verify registry has at least 21 base patterns with non-empty fields."""
    assert len(PATTERNS) >= 21
    for slug, pattern in PATTERNS.items():
        assert pattern.slug == slug
        assert len(pattern.title) > 0
        assert len(pattern.description) > 0
        assert len(pattern.category) > 0
        assert len(pattern.html) > 0
        assert isinstance(pattern.keywords, tuple)
        assert isinstance(pattern.variables, tuple)


def test_get_pattern_success():
    """Verify getting a valid pattern returns BlockPattern instance."""
    p = get_pattern("hero-banner")
    assert isinstance(p, BlockPattern)
    assert p.slug == "hero-banner"
    assert p.category == "بنر و هیرو"


def test_get_pattern_not_found():
    """Verify requesting an unknown pattern raises NotFoundError."""
    with pytest.raises(NotFoundError) as exc_info:
        get_pattern("unknown-pattern-slug-xyz")
    assert "not found" in str(exc_info.value).lower()


def test_grouped_patterns():
    """Verify grouped_patterns returns list of category dicts."""
    groups = grouped_patterns()
    assert isinstance(groups, list)
    assert len(groups) >= 9
    for group in groups:
        assert "category" in group
        assert "patterns" in group
        assert len(group["patterns"]) > 0
        for item in group["patterns"]:
            assert "slug" in item
            assert "title" in item
            assert "variables" in item


def test_render_pattern_with_defaults():
    """Verify render_pattern resolves all slots with default values."""
    html = render_pattern("hero-banner")
    assert "<section" in html
    assert "{{title}}" not in html
    assert "{{subtitle}}" not in html


def test_render_pattern_html_escaping():
    """Verify user-provided variables are escaped to prevent XSS injection."""
    malicious = "<script>alert('xss')</script>"
    html = render_pattern("hero-banner", {"title": malicious})
    assert "<script>" not in html
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html


def test_new_curated_patterns_exist_and_render_cleanly():
    """Verify all 7 new Elementor-inspired e-commerce patterns exist and render without unresolved slots."""
    new_slugs = [
        "comparison-table",
        "process-steps",
        "lead-capture-form",
        "alert-banner",
        "floating-contact-bar",
        "brand-logo-carousel",
        "product-highlights",
    ]
    assert len(PATTERNS) >= 28
    for slug in new_slugs:
        p = get_pattern(slug)
        assert p.slug == slug
        rendered = render_pattern(slug)
        assert len(rendered) > 100
        # No unresolved {{...}} template tags remaining
        assert "{{" not in rendered
        assert "}}" not in rendered

