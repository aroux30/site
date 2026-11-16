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


def test_token_cycle_error_detection():
    from app.modules.content.schemas.theme import TokenCycleError

    # Circular alias: A points to B, B points to C, C points to A
    cycle_raw = {
        "primitive": {
            "tokenA": {"$value": "{primitive.tokenB}"},
            "tokenB": {"$value": "{primitive.tokenC}"},
            "tokenC": {"$value": "{primitive.tokenA}"},
        }
    }
    schema = DesignTokensSchema.model_validate(cycle_raw)

    with pytest.raises(TokenCycleError) as exc_info:
        resolve_token_value("{primitive.tokenA}", schema)

    error_msg = str(exc_info.value)
    assert "Circular dependency detected" in error_msg
    assert "primitive.tokenA -> primitive.tokenB -> primitive.tokenC -> primitive.tokenA" in error_msg


def test_compile_all_semantic_and_component_tokens():
    from app.modules.content.schemas.theme import compile_dtcg_to_css_variables

    tokens = {
        "primitive": {
            "color": {
                "slate": {"900": {"$value": "#0f172a"}},
            }
        },
        "semantic": {
            "color": {
                "primary": {"$value": "#059669"},
                "secondary": {"$value": "#0d9488"},
                "success": {"$value": "#16a34a"},
                "warning": {"$value": "#f59e0b"},
                "destructive": {"$value": "#e11d48"},
                "info": {"$value": "#2563eb"},
                "surface": {"$value": "{primitive.color.slate.900}"},
            },
            "dimension": {
                "radius": {"$value": "16px"},
            },
            "typography": {
                "fontFamily": {"$value": "Vazirmatn"},
            },
        },
        "component": {
            "button": {
                "radius": {"$value": "{semantic.dimension.radius}"},
            },
        },
    }

    schema = DesignTokensSchema.model_validate(tokens)
    css_vars = compile_dtcg_to_css_variables(schema)

    assert css_vars["--primary"] == "#059669"
    assert css_vars["--secondary"] == "#0d9488"
    assert css_vars["--success"] == "#16a34a"
    assert css_vars["--warning"] == "#f59e0b"
    assert css_vars["--destructive"] == "#e11d48"
    assert css_vars["--info"] == "#2563eb"
    assert css_vars["--surface"] == "#0f172a"
    assert css_vars["--radius"] == "16px"
    assert css_vars["--font-vazirmatn"] == "Vazirmatn"
    assert css_vars["--button-radius"] == "16px"

