"""Design Tokens Community Group (DTCG) and Site Theme schemas (Pydantic v2).

Complies with DTCG specification for design tokens ($value, $type, $description, and alias references).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DTCGTokenType = Literal[
    "color",
    "dimension",
    "fontFamily",
    "fontWeight",
    "duration",
    "cubicBezier",
    "number",
    "shadow",
]

_ALIAS_PATTERN = re.compile(r"^\{([a-zA-Z0-9_.-]+)\}$")


class DTCGToken(BaseModel):
    """Single design token following DTCG specification."""

    model_config = ConfigDict(populate_by_name=True)

    value: Any = Field(alias="$value")
    type: DTCGTokenType | str | None = Field(default=None, alias="$type")
    description: str | None = Field(default=None, alias="$description")

    def is_alias(self) -> bool:
        """Check if token value points to another token reference (e.g. {color.emerald.500})."""
        if isinstance(self.value, str):
            return bool(_ALIAS_PATTERN.match(self.value.strip()))
        return False

    def alias_target(self) -> str | None:
        """Return the target path if this token is an alias reference."""
        if isinstance(self.value, str):
            m = _ALIAS_PATTERN.match(self.value.strip())
            return m.group(1) if m else None
        return None


def _parse_token_tree(data: Any) -> Any:
    """Recursively parse dictionaries into DTCGToken objects if leaf has '$value'."""
    if not isinstance(data, dict):
        return data

    if "$value" in data or "value" in data:
        return DTCGToken.model_validate(data)

    parsed = {}
    for key, value in data.items():
        parsed[key] = _parse_token_tree(value)
    return parsed


class DesignTokensSchema(BaseModel):
    """Root design token document structure (primitive, semantic, component)."""

    model_config = ConfigDict(populate_by_name=True)

    primitive: dict[str, Any] = Field(default_factory=dict)
    semantic: dict[str, Any] = Field(default_factory=dict)
    component: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def parse_token_hierarchy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        return {
            "primitive": _parse_token_tree(data.get("primitive", {})),
            "semantic": _parse_token_tree(data.get("semantic", {})),
            "component": _parse_token_tree(data.get("component", {})),
        }


def _lookup_path(tree: dict[str, Any], path_parts: list[str]) -> Any:
    current = tree
    for part in path_parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, BaseModel) and hasattr(current, part):
            current = getattr(current, part)
        elif isinstance(current, DTCGToken):
            return current.value
        else:
            return None
    return current


class TokenCycleError(ValueError):
    """Raised when a circular reference is detected in design token aliases."""

    def __init__(self, cycle_path: list[str]) -> None:
        self.cycle_path = cycle_path
        path_str = " -> ".join(cycle_path)
        super().__init__(f"Circular dependency detected in design token aliases: {path_str}")


def resolve_token_value(value_or_alias: Any, tokens: DesignTokensSchema, max_depth: int = 10) -> Any:
    """Resolve token aliases using a Directed Acyclic Graph (DAG) resolver with cycle detection."""
    current_val = value_or_alias
    visited_chain: list[str] = []

    while isinstance(current_val, str) and _ALIAS_PATTERN.match(current_val.strip()):
        path_str = _ALIAS_PATTERN.match(current_val.strip()).group(1)

        if path_str in visited_chain:
            cycle = visited_chain + [path_str]
            raise TokenCycleError(cycle)

        if len(visited_chain) >= max_depth:
            raise ValueError(f"Max alias resolution depth of {max_depth} exceeded for {value_or_alias}")

        visited_chain.append(path_str)
        parts = path_str.split(".")

        root_key = parts[0]
        if root_key == "primitive":
            target = _lookup_path(tokens.primitive, parts[1:])
        elif root_key == "semantic":
            target = _lookup_path(tokens.semantic, parts[1:])
        elif root_key == "component":
            target = _lookup_path(tokens.component, parts[1:])
        else:
            # Try global lookup across all groups
            target = _lookup_path(tokens.primitive, parts) or _lookup_path(tokens.semantic, parts)

        if target is None:
            raise KeyError(f"Unable to resolve design token alias: '{path_str}'")

        if isinstance(target, DTCGToken):
            current_val = target.value
        elif isinstance(target, dict) and ("$value" in target or "value" in target):
            current_val = target.get("$value", target.get("value"))
        else:
            current_val = target

    return current_val


def compile_dtcg_to_css_variables(tokens: DesignTokensSchema) -> dict[str, str]:
    """Dynamically compile all semantic and component tokens into standard CSS variables."""
    css_vars: dict[str, str] = {
        "--primary": "#059669",
        "--secondary": "#0d9488",
        "--background": "#ffffff",
        "--foreground": "#09090b",
        "--radius": "12px",
        "--font-vazirmatn": "Vazirmatn, system-ui, sans-serif",
    }

    # Helper to recursively walk a dict and yield (path_tuple, DTCGToken)
    def _walk(d: Any, prefix: list[str]) -> list[tuple[list[str], Any]]:
        items = []
        if isinstance(d, DTCGToken):
            items.append((prefix, d.value))
        elif isinstance(d, dict):
            if "$value" in d or "value" in d:
                val = d.get("$value", d.get("value"))
                items.append((prefix, val))
            else:
                for k, v in d.items():
                    items.extend(_walk(v, prefix + [k]))
        return items

    # Standard semantic shorthands
    SHORTHAND_MAP = {
        ("color", "primary"): "--primary",
        ("color", "secondary"): "--secondary",
        ("color", "background"): "--background",
        ("color", "foreground"): "--foreground",
        ("color", "surface"): "--surface",
        ("color", "muted"): "--muted",
        ("color", "border"): "--border",
        ("color", "input"): "--input",
        ("color", "ring"): "--ring",
        ("color", "success"): "--success",
        ("color", "warning"): "--warning",
        ("color", "destructive"): "--destructive",
        ("color", "info"): "--info",
        ("dimension", "radius"): "--radius",
        ("typography", "fontFamily"): "--font-vazirmatn",
    }

    # 1. Process Semantic tokens
    for path, raw_val in _walk(tokens.semantic, []):
        try:
            resolved = str(resolve_token_value(raw_val, tokens))
        except Exception:
            resolved = str(raw_val)

        tuple_key = tuple(path[:2])
        if tuple_key in SHORTHAND_MAP:
            css_vars[SHORTHAND_MAP[tuple_key]] = resolved

        # Also emit standard kebab-case var name
        kebab_name = "--" + "-".join(p.replace("_", "-") for p in path)
        css_vars[kebab_name] = resolved

    # 2. Process Component tokens
    for path, raw_val in _walk(tokens.component, []):
        try:
            resolved = str(resolve_token_value(raw_val, tokens))
        except Exception:
            resolved = str(raw_val)

        kebab_name = "--" + "-".join(p.replace("_", "-") for p in path)
        css_vars[kebab_name] = resolved

    return css_vars


class SiteThemeCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = False
    tokens: DesignTokensSchema


class SiteThemeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    tokens: DesignTokensSchema | None = None


class SiteThemeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    name: str
    slug: str
    description: str | None = None
    is_active: bool
    tokens: dict[str, Any]
    css_variables: dict[str, str] = Field(default_factory=dict)
    author_id: uuid.UUID | None = None


class ThemeRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    theme_id: uuid.UUID
    version: int
    name: str
    change_summary: str | None = None
    tokens: dict[str, Any]
    created_by: uuid.UUID | None = None
    created_at: datetime


class ThemeCloneRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(min_length=2, max_length=180)
