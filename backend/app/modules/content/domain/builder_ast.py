"""Visual Page Builder AST (Abstract Syntax Tree) Pydantic v2 models (Phase P0).

Strict Type-Safe Schema for:
- Document / Page AST
- Containers (Flex / Grid)
- Widgets (Leaf nodes)
- Mobile-First Responsive Styles (Mobile Base -> Tablet md: -> Desktop lg:)
- Global Style Tokens and Unit Values
"""

from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_camel(name: str) -> str:
    """snake_case -> camelCase for wire compatibility with the builder.

    The stored AST is read by the frontend's Zod schema (``rootElements``,
    ``schemaVersion``, ``isLinked``, ``minHeight`` …). Pydantic's default
    snake_case dump meant every save stored ``root_elements``, which the
    frontend never saw — the page appeared to save but reloaded empty.
    """
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


class ASTModel(BaseModel):
    """Base for every AST node: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

# ── 1. Unit Values and Spacing ───────────────────────────────────────────────

CSS_LENGTH_REGEX = re.compile(r"^-?\d+(\.\d+)?(px|rem|%|vh|vw|em|pt)$")
ELEMENT_ID_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{5,15}$")


class UnitValue(ASTModel):
    """A scalar number with a CSS measurement unit."""

    model_config = ConfigDict(frozen=True, alias_generator=_to_camel, populate_by_name=True)

    value: float = 0.0
    unit: Literal["px", "rem", "%", "vh", "vw", "em", "pt", "auto"] = "px"

    def to_css(self) -> str:
        if self.unit == "auto":
            return "auto"
        # If float is integer-equivalent, format as integer
        val_str = f"{int(self.value)}" if self.value.is_integer() else f"{self.value}"
        return f"{val_str}{self.unit}"


class SpacingBox(ASTModel):
    """Padding or margin for four sides."""

    top: UnitValue = Field(default_factory=lambda: UnitValue(value=0, unit="px"))
    right: UnitValue = Field(default_factory=lambda: UnitValue(value=0, unit="px"))
    bottom: UnitValue = Field(default_factory=lambda: UnitValue(value=0, unit="px"))
    left: UnitValue = Field(default_factory=lambda: UnitValue(value=0, unit="px"))
    is_linked: bool = True


# ── 2. Styles ───────────────────────────────────────────────────────────────


class TypographyStyle(ASTModel):
    font_family: str = "inherit"
    font_size: UnitValue | None = None
    font_weight: Literal["300", "400", "500", "600", "700", "800", "900", "inherit"] = "inherit"
    line_height: UnitValue | None = None
    letter_spacing: UnitValue | None = None
    text_align: Literal["right", "center", "left", "justify", "inherit"] = "inherit"
    text_transform: Literal["none", "uppercase", "lowercase", "capitalize"] = "none"
    text_decoration: Literal["none", "underline", "line-through"] = "none"
    color: str | None = None  # hex, hsl(var(--token)), or semantic token key


class BorderStyle(ASTModel):
    style: Literal["none", "solid", "dashed", "dotted", "double"] = "none"
    width: SpacingBox | None = None
    color: str | None = None
    radius: SpacingBox | None = None


class BackgroundGradient(ASTModel):
    direction: Literal["to-r", "to-l", "to-t", "to-b", "to-tr", "to-tl"] = "to-l"
    from_color: str
    to_color: str


class BackgroundStyle(ASTModel):
    type: Literal["none", "color", "gradient", "image"] = "none"
    color: str | None = None
    gradient: BackgroundGradient | None = None
    image_url: str | None = None
    position: Literal["center", "top", "bottom", "left", "right"] = "center"
    size: Literal["cover", "contain", "auto"] = "cover"


class BackgroundOverlayStyle(ASTModel):
    type: Literal["none", "color", "gradient"] = "none"
    color: str | None = None
    gradient: BackgroundGradient | None = None
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)


class DeviceStyle(ASTModel):
    """Computed or override styles for one breakpoint."""

    typography: TypographyStyle | None = None
    margin: SpacingBox | None = None
    padding: SpacingBox | None = None
    border: BorderStyle | None = None
    background: BackgroundStyle | None = None
    background_overlay: BackgroundOverlayStyle | None = None
    width: UnitValue | None = None
    min_height: UnitValue | None = None
    display: Literal["block", "flex", "grid", "inline-block", "none", "inherit"] = "inherit"
    box_shadow: str | None = None
    filter: str | None = None
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    z_index: int | None = Field(default=None, ge=0, le=999)
    # Advanced Layout (P4)
    position: Literal["static", "relative", "absolute", "sticky", "inherit"] = "inherit"
    top: UnitValue | None = None
    bottom: UnitValue | None = None
    left: UnitValue | None = None
    right: UnitValue | None = None
    overflow: Literal["visible", "hidden", "scroll", "auto", "inherit"] = "inherit"
    flex_direction: Literal["row", "column", "row-reverse", "column-reverse", "inherit"] = "inherit"
    justify_content: Literal["start", "center", "end", "between", "around", "evenly", "inherit"] = "inherit"
    align_items: Literal["start", "center", "end", "stretch", "baseline", "inherit"] = "inherit"
    align_self: Literal["auto", "start", "center", "end", "stretch", "inherit"] | None = "inherit"
    order: int | None = None
    flex_grow: float | None = None
    flex_wrap: Literal["nowrap", "wrap", "wrap-reverse", "inherit"] = "inherit"
    gap: UnitValue | None = None
    grid_template_columns: str | None = None
    box_shadow: str | None = None


class ResponsiveStyles(ASTModel):
    """Mobile-first responsive styling. Mobile is base; tablet and desktop override."""

    mobile: DeviceStyle = Field(default_factory=DeviceStyle)
    tablet: DeviceStyle | None = None
    desktop: DeviceStyle | None = None
    custom_css_class: str | None = None
    custom_css_id: str | None = None
    custom_attributes: str | None = None
    direction: Literal["rtl", "ltr", "inherit"] = "inherit"
    animation: str | None = None  # e.g. "fade-in", "slide-up", "zoom-in"
    animation_duration: float | None = None  # in seconds (e.g. 0.5)
    animation_delay: float | None = None  # in seconds (e.g. 0.2)


# ── 3. Layout and Containers ────────────────────────────────────────────────


class ContainerLayout(ASTModel):
    """Flexbox or CSS Grid layout parameters for a container."""

    kind: Literal["flex", "grid"] = "flex"
    direction: Literal["row", "column", "row-reverse", "column-reverse"] = "column"
    justify_content: Literal["start", "center", "end", "between", "around", "evenly"] = "start"
    align_items: Literal["start", "center", "end", "stretch", "baseline"] = "stretch"
    flex_wrap: Literal["nowrap", "wrap", "wrap-reverse"] = "nowrap"
    gap: UnitValue = Field(default_factory=lambda: UnitValue(value=16, unit="px"))
    grid_columns: int = Field(default=3, ge=1, le=12)
    boxed_width: UnitValue | None = None  # None indicates full-width fluid


# ── 4. Elements and AST Nodes ───────────────────────────────────────────────


class BuilderElement(ASTModel):
    """A single node in the visual page tree (either a container or a widget)."""

    id: str
    name: str = Field(..., max_length=100)
    type: Literal["container", "widget"]
    is_locked: bool = False
    is_hidden: bool = False
    styles: ResponsiveStyles = Field(default_factory=ResponsiveStyles)
    layout: ContainerLayout | None = None
    widget_type: str | None = None
    widget_props: dict[str, Any] = Field(default_factory=dict)
    children: list[BuilderElement] = Field(default_factory=list)
    # Conditional visibility (P4)
    visible_on_desktop: bool = True
    visible_on_tablet: bool = True
    visible_on_mobile: bool = True
    auth_visibility: Literal["all", "authenticated", "guest"] = "all"
    # Synced / Global Components (P4)
    global_component_id: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        if not ELEMENT_ID_REGEX.match(v):
            raise ValueError(
                f"Element ID '{v}' is invalid. Must start with a letter and be 6-16 alphanumeric/dash characters."
            )
        return v


# ── 5. Document Root Schema ─────────────────────────────────────────────────


class PageAST(ASTModel):
    """Complete root AST document for a visual page."""

    schema_version: int = Field(default=1, ge=1, le=10)
    title: str = Field(..., min_length=1, max_length=300)
    slug: str = Field(..., min_length=1, max_length=220)
    global_styles: dict[str, Any] = Field(default_factory=dict)
    root_elements: list[BuilderElement] = Field(default_factory=list)
