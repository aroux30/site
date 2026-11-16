"""Unit tests for DTCG Design Token Schemas (Pydantic v2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.content.schemas.theme import (
    DTCGToken,
    DesignTokensSchema,
    SiteThemeCreateRequest,
    SiteThemeUpdateRequest,
    SiteThemeResponse,
    resolve_token_value,
)


def test_dtcg_token_validation_valid():
    token = DTCGToken(
        value="#10b981",
        type="color",
        description="Brand primary emerald",
    )
    assert token.value == "#10b981"
    assert token.type == "color"
    assert token.model_dump(by_alias=True)["$value"] == "#10b981"
    assert token.model_dump(by_alias=True)["$type"] == "color"


def test_dtcg_token_alias_reference():
    token = DTCGToken(
        value="{color.emerald.500}",
        type="color",
    )
    assert token.value == "{color.emerald.500}"
    assert token.is_alias() is True


def test_design_tokens_schema_structure():
    raw = {
        "primitive": {
            "color": {
                "emerald": {
                    "500": {"$value": "#10b981", "$type": "color"},
                    "600": {"$value": "#059669", "$type": "color"},
                }
            },
            "font": {
                "vazirmatn": {"$value": "Vazirmatn, system-ui", "$type": "fontFamily"},
            },
        },
        "semantic": {
            "color": {
                "primary": {"$value": "{primitive.color.emerald.600}", "$type": "color"},
                "secondary": {"$value": "#0d9488", "$type": "color"},
            },
            "dimension": {
                "radius": {"$value": "12px", "$type": "dimension"},
            },
        },
        "component": {
            "button": {
                "radius": {"$value": "{semantic.dimension.radius}", "$type": "dimension"},
            }
        },
    }

    schema = DesignTokensSchema.model_validate(raw)
    assert schema.semantic["color"]["primary"].value == "{primitive.color.emerald.600}"

    # Test alias resolution
    resolved_primary = resolve_token_value("{primitive.color.emerald.600}", schema)
    assert resolved_primary == "#059669"


def test_site_theme_create_request_validation():
    req = SiteThemeCreateRequest(
        name="تم پاییزی",
        slug="autumn-theme",
        description="تم فصلی برای کمپین پاییز",
        is_active=False,
        tokens={
            "semantic": {
                "color": {
                    "primary": {"$value": "#f59e0b", "$type": "color"},
                }
            }
        },
    )
    assert req.name == "تم پاییزی"
    assert req.slug == "autumn-theme"
    assert req.tokens.semantic["color"]["primary"].value == "#f59e0b"
