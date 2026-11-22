"""Visual Page Builder Validation Engine (Phase P0).

Provides independent, deterministic validators for:
1. Unique Element IDs (DFS Set Accumulation)
2. Tree Topology, Max Nesting Depth, and Acyclic Guarantees
3. Widget Leaf-Node Constraints and Allowed Types
4. Custom CSS Security (tinycss2 property & value parser)
"""

from __future__ import annotations

import re
from typing import Any
import tinycss2

from app.core.exceptions.handlers import ValidationError
from app.modules.content.domain.builder_ast import BuilderElement, PageAST


class DuplicateElementIdError(ValidationError):
    pass


class CircularReferenceError(ValidationError):
    pass


class MaxDepthExceededError(ValidationError):
    pass


class InvalidNodeStructureError(ValidationError):
    pass


class InvalidWidgetTypeError(ValidationError):
    pass


class InvalidCssError(ValidationError):
    pass


# ── Allowed Widget Registry Keys ────────────────────────────────────────────

STANDARD_WIDGET_TYPES: frozenset[str] = frozenset({
    # Basic widgets
    "heading",
    "text_editor",
    "image",
    "video",
    "button",
    "icon",
    "divider",
    "spacer",
    "html_custom",
    "table",
    "form_input",
    "form_textarea",
    "form_select",
    "form_checkbox",
    "form_radio",
    "form_container",
    # Advanced widgets
    "tabs",
    "nested_tabs",
    "accordion",
    "nested_accordion",
    "toggle",
    "image_carousel",
    "testimonial",
    "testimonials",
    "price_table",
    "pricing_table",
    "price_list",
    "countdown",
    "lead_form",
    "counter",
    "stats_counter",
    "alert",
    "progress_bar",
    "progress_tracker",
    "call_to_action",
    "animated_headline",
    "flip_box",
    "blockquote",
    "menu_anchor",
    "icon_box",
    "image_box",
    "icon_list",
    "share_buttons",
    "table_of_contents",
    "hotspot",
    "lottie",
    "slides",
    "code_highlight",
    "contact_buttons",
    "floating_buttons",
    "off_canvas",
    "popup_builder",
    "multi_step_form",
    "loop_carousel",
    "audio",
    "google_maps",
    "read_more",
    "rating",
    "search_bar",
    "nav_menu",
    "faq",
    "video",
    "social_links",
    # Store widgets (Phase P2 & Phase P3)
    "product_grid",
    "product_card",
    "product_title",
    "product_price",
    "add_to_cart",
    "product_variants",
    "mini_cart",
    "cart_summary",
    "product_rating",
    "product_categories",
    "product_gallery",
    "shopping_cart",
    "image_gallery",
    "star_rating",
    "review_histogram",
    "recently_viewed",
    "mega_menu",
    # Structural & Legacy
    "global_ref",
    "legacy_html",
})

# ── Allowed CSS Properties Whitelist for Custom CSS ─────────────────────────

ALLOWED_CSS_PROPERTIES: frozenset[str] = frozenset({
    "color",
    "background-color",
    "background",
    "font-size",
    "font-weight",
    "font-family",
    "line-height",
    "letter-spacing",
    "text-align",
    "text-transform",
    "text-decoration",
    "padding",
    "padding-top",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-inline-start",
    "padding-inline-end",
    "margin",
    "margin-top",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-inline-start",
    "margin-inline-end",
    "width",
    "max-width",
    "min-width",
    "height",
    "max-height",
    "min-height",
    "border",
    "border-width",
    "border-style",
    "border-color",
    "border-radius",
    "box-shadow",
    "text-shadow",
    "opacity",
    "transform",
    "transition",
    "z-index",
    "overflow",
    "overflow-x",
    "overflow-y",
    "gap",
    "row-gap",
    "column-gap",
    "flex",
    "flex-direction",
    "flex-wrap",
    "justify-content",
    "align-items",
    "align-self",
    "display",
    "grid-template-columns",
    "grid-template-rows",
    "grid-column",
    "grid-row",
    "position",
    "top",
    "bottom",
    "left",
    "right",
})

FORBIDDEN_CSS_PATTERNS = re.compile(
    r"(javascript:|expression\(|url\(|@import|@font-face|-moz-binding|behavior:|<script|<\/script)",
    re.IGNORECASE,
)


# ── Validator 1: Unique Element IDs ─────────────────────────────────────────


def validate_unique_element_ids(ast: PageAST) -> None:
    """Ensure every element across the entire tree has a globally unique ID."""
    seen_ids: set[str] = set()

    def _traverse(element: BuilderElement) -> None:
        if element.id in seen_ids:
            raise DuplicateElementIdError(
                detail=f"Duplicate element ID detected: '{element.id}'"
            )
        seen_ids.add(element.id)
        for child in element.children:
            _traverse(child)

    for root_el in ast.root_elements:
        _traverse(root_el)


# ── Validator 2: Tree Topology, Depth, and Leaf Structure ───────────────────


def validate_tree_topology(ast: PageAST, max_depth: int = 5) -> None:
    """Validate hierarchy: prevent cycles, bound nesting depth, enforce leaf nodes.

    - Containers can nest up to `max_depth` levels.
    - Widgets must be leaf nodes (children must be empty).
    - Circular references in ancestry chains are forbidden.
    """
    def _traverse(element: BuilderElement, ancestry: set[str], current_depth: int) -> None:
        if element.id in ancestry:
            raise CircularReferenceError(
                detail=f"Circular reference detected: element '{element.id}' is its own ancestor"
            )

        if element.type == "widget":
            if element.children:
                raise InvalidNodeStructureError(
                    detail=f"Widget element '{element.id}' ({element.widget_type}) cannot contain children."
                )
            return

        # It's a container
        if current_depth > max_depth:
            raise MaxDepthExceededError(
                detail=f"Max container nesting depth of {max_depth} exceeded at element '{element.id}'"
            )

        new_ancestry = ancestry | {element.id}
        for child in element.children:
            _traverse(child, new_ancestry, current_depth + 1)

    for root_el in ast.root_elements:
        _traverse(root_el, ancestry=set(), current_depth=1)


# ── Validator 3: Widget Types Whitelist ──────────────────────────────────────


def validate_widget_types(
    ast: PageAST,
    allowed_types: frozenset[str] = STANDARD_WIDGET_TYPES,
) -> None:
    """Verify that every widget specifies a recognized and supported widget_type."""
    def _check_element(element: BuilderElement) -> None:
        if element.type == "widget":
            if not element.widget_type or element.widget_type not in allowed_types:
                raise InvalidWidgetTypeError(
                    detail=f"Unrecognized widget type: '{element.widget_type}' in element '{element.id}'"
                )
        for child in element.children:
            _check_element(child)

    for root_el in ast.root_elements:
        _check_element(root_el)


# ── Validator 4: Custom CSS Parsing and Security ────────────────────────────


def validate_custom_css(css_text: str | None) -> None:
    """Parse custom CSS declarations and reject any disallowed property or dangerous payload."""
    if not css_text or not css_text.strip():
        return

    raw = css_text.strip()
    if FORBIDDEN_CSS_PATTERNS.search(raw):
        raise InvalidCssError(
            detail="Custom CSS contains dangerous tokens (url(), @import, javascript:, or script tags)."
        )

    # Parse declarations using tinycss2
    declarations = tinycss2.parse_declaration_list(raw, skip_whitespace=True)
    for decl in declarations:
        if decl.type == "declaration":
            prop_name = decl.lower_name
            if prop_name not in ALLOWED_CSS_PROPERTIES:
                raise InvalidCssError(
                    detail=f"CSS property '{prop_name}' is not in the allowed properties whitelist."
                )
            # Reconstruct value string and check tokens
            val_tokens = tinycss2.serialize(decl.value).strip()
            if FORBIDDEN_CSS_PATTERNS.search(val_tokens):
                raise InvalidCssError(
                    detail=f"Value for CSS property '{prop_name}' contains disallowed functions or URLs."
                )


# ── Master Orchestrator Validator ───────────────────────────────────────────


def validate_page_ast(
    ast_input: dict[str, Any] | PageAST,
    allowed_types: frozenset[str] = STANDARD_WIDGET_TYPES,
) -> PageAST:
    """Perform full-spectrum validation of Page AST.

    1. Schema validation (Pydantic v2)
    2. Unique ID verification
    3. Structural topology and max depth bounds
    4. Widget type whitelist verification
    5. Custom CSS sanitization check
    """
    if isinstance(ast_input, PageAST):
        ast = ast_input
    else:
        ast = PageAST.model_validate(ast_input)

    validate_unique_element_ids(ast)
    validate_tree_topology(ast)
    validate_widget_types(ast, allowed_types)

    # Inspect custom CSS on elements if provided
    def _inspect_styles(el: BuilderElement) -> None:
        if el.styles.custom_css_class and FORBIDDEN_CSS_PATTERNS.search(el.styles.custom_css_class):
            raise InvalidCssError(detail="custom_css_class contains invalid characters.")
        for child in el.children:
            _inspect_styles(child)

    for root_el in ast.root_elements:
        _inspect_styles(root_el)

    return ast
