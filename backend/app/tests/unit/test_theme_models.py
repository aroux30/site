"""Unit tests for SiteTheme, ThemeRevision and PageTemplate category."""

from __future__ import annotations

import uuid
import pytest
from app.modules.content.domain.models import PageTemplate
from app.modules.content.domain.theme_models import SiteTheme, ThemeRevision


def test_site_theme_model_instantiation():
    theme_id = uuid.uuid4()
    sample_tokens = {
        "color": {
            "primary": {"$value": "#10b981", "$type": "color"},
            "secondary": {"$value": "#0d9488", "$type": "color"},
        },
        "dimension": {
            "radius": {"$value": "12px", "$type": "dimension"},
        },
    }

    theme = SiteTheme(
        id=theme_id,
        name="تم پیش‌فرض سازمانی",
        slug="default-corporate-theme",
        description="تم رسمی سازمانی بر مبنای دیزاین سیستم",
        is_active=True,
        tokens=sample_tokens,
    )

    assert theme.id == theme_id
    assert theme.name == "تم پیش‌فرض سازمانی"
    assert theme.slug == "default-corporate-theme"
    assert theme.is_active is True
    assert theme.tokens["color"]["primary"]["$value"] == "#10b981"
    assert repr(theme) == f"<SiteTheme(slug={theme.slug}, active=True)>"


def test_theme_revision_model_instantiation():
    theme_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    tokens = {
        "color": {
            "primary": {"$value": "#059669", "$type": "color"},
        }
    }

    revision = ThemeRevision(
        id=rev_id,
        theme_id=theme_id,
        revision_number=1,
        name="نسخه اولیه",
        tokens=tokens,
    )

    assert revision.id == rev_id
    assert revision.theme_id == theme_id
    assert revision.revision_number == 1
    assert revision.tokens["color"]["primary"]["$value"] == "#059669"
    assert repr(revision) == f"<ThemeRevision(theme_id={theme_id}, rev=1)>"


def test_page_template_has_category_attribute():
    template = PageTemplate(
        title="الگوی سرتیتر هیرو",
        slug="hero-header-template",
        template_type="section",
        category="هیرو و بنر",
        builder_data={"schemaVersion": 1, "rootElements": []},
    )

    assert template.category == "هیرو و بنر"
    assert hasattr(PageTemplate, "category")
