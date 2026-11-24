"""Unit tests for Visual Page Builder AST and Validation Engine (Phase P0)."""

from __future__ import annotations

import pytest
from app.core.exceptions.handlers import ValidationError
from app.modules.content.domain.builder_ast import (
    BuilderElement,
    ContainerLayout,
    PageAST,
    ResponsiveStyles,
    UnitValue,
)
from app.modules.content.domain.builder_validation import (
    CircularReferenceError,
    DuplicateElementIdError,
    InvalidCssError,
    InvalidNodeStructureError,
    InvalidWidgetTypeError,
    MaxDepthExceededError,
    validate_custom_css,
    validate_page_ast,
    validate_tree_topology,
    validate_unique_element_ids,
    validate_widget_types,
)


def _make_valid_ast() -> PageAST:
    return PageAST(
        schema_version=1,
        title="تست برگه اصلی",
        slug="test-home",
        root_elements=[
            BuilderElement(
                id="el_sec001",
                name="بخش اصلی",
                type="container",
                layout=ContainerLayout(kind="flex", direction="column"),
                children=[
                    BuilderElement(
                        id="el_head01",
                        name="سرتیتر",
                        type="widget",
                        widget_type="heading",
                        widget_props={"text": "خوش آمدید", "tag": "h1"},
                    ),
                    BuilderElement(
                        id="el_btn001",
                        name="دکمه خرید",
                        type="widget",
                        widget_type="button",
                        widget_props={"label": "مشاهده محصولات", "url": "/products"},
                    ),
                ],
            )
        ],
    )


def test_valid_ast_passes_validation():
    ast = _make_valid_ast()
    result = validate_page_ast(ast)
    assert result.slug == "test-home"
    assert len(result.root_elements) == 1
    assert len(result.root_elements[0].children) == 2


def test_duplicate_element_id_fails():
    ast = _make_valid_ast()
    # Inject duplicate ID
    ast.root_elements[0].children.append(
        BuilderElement(
            id="el_head01",  # duplicate ID
            name="دوبل سرتیتر",
            type="widget",
            widget_type="heading",
        )
    )
    with pytest.raises(DuplicateElementIdError) as exc_info:
        validate_unique_element_ids(ast)
    assert "duplicate element id detected" in str(exc_info.value.detail).lower()


def test_circular_reference_fails():
    # Construct a cycle: root contains child, child contains root
    root = BuilderElement(
        id="el_root01",
        name="والد",
        type="container",
        children=[],
    )
    child = BuilderElement(
        id="el_child01",
        name="فرزند",
        type="container",
        children=[root],  # cycle!
    )
    root.children.append(child)

    ast = PageAST(title="تست دور", slug="test-cycle", root_elements=[root])
    with pytest.raises(CircularReferenceError) as exc_info:
        validate_tree_topology(ast)
    assert "circular reference detected" in str(exc_info.value.detail).lower()


def test_max_depth_exceeded_fails():
    # Build a chain of 7 nested containers (limit is 5)
    current = BuilderElement(
        id="el_deep07",
        name="عمق ۷",
        type="widget",
        widget_type="heading",
    )
    for i in range(6, 0, -1):
        parent = BuilderElement(
            id=f"el_cont0{i}",
            name=f"کانتینر {i}",
            type="container",
            children=[current],
        )
        current = parent

    ast = PageAST(title="تست عمق", slug="test-depth", root_elements=[current])
    with pytest.raises(MaxDepthExceededError) as exc_info:
        validate_tree_topology(ast, max_depth=5)
    assert "max container nesting depth of 5 exceeded" in str(exc_info.value.detail).lower()


def test_widget_with_children_fails():
    ast = PageAST(
        title="تست ویجت با فرزند",
        slug="test-widget-child",
        root_elements=[
            BuilderElement(
                id="el_widg01",
                name="ویجت ناقض",
                type="widget",
                widget_type="heading",
                children=[
                    BuilderElement(
                        id="el_widg02",
                        name="فرزند نامجاز",
                        type="widget",
                        widget_type="button",
                    )
                ],
            )
        ],
    )
    with pytest.raises(InvalidNodeStructureError) as exc_info:
        validate_tree_topology(ast)
    assert "cannot contain children" in str(exc_info.value.detail).lower()


def test_unrecognized_widget_type_fails():
    ast = PageAST(
        title="تست ویجت ناشناخته",
        slug="test-unknown-widget",
        root_elements=[
            BuilderElement(
                id="el_unk001",
                name="ویجت نامعتبر",
                type="widget",
                widget_type="malicious_crypto_miner",
            )
        ],
    )
    with pytest.raises(InvalidWidgetTypeError) as exc_info:
        validate_widget_types(ast)
    assert "unrecognized widget type" in str(exc_info.value.detail).lower()


def test_element_id_regex_enforcement():
    with pytest.raises(ValueError):
        # Must not start with number
        BuilderElement(id="123_invalid", name="نامعتبر", type="container")

    with pytest.raises(ValueError):
        # Must not contain special characters
        BuilderElement(id="el_<script>", name="نامعتبر", type="container")


def test_custom_css_security_allowed_passes():
    css = "color: #10b981; margin-top: 16px; font-weight: 700;"
    # Should not raise
    validate_custom_css(css)


def test_custom_css_security_disallowed_property_fails():
    css = "behavior: url(script.htc); color: red;"
    with pytest.raises(InvalidCssError):
        validate_custom_css(css)


def test_custom_css_security_url_injection_fails():
    css = "background-image: url('http://evil.com/hack.jpg');"
    with pytest.raises(InvalidCssError):
        validate_custom_css(css)


def test_template_import_validation_rejects_xss_and_invalid_tokens():
    """Verify that validate_page_ast used during template import catches security violations."""
    # 1. Template with forbidden CSS tokens in customCssClass
    bad_ast_dict = {
        "schemaVersion": 1,
        "title": "قالب مخرب",
        "slug": "malicious-template",
        "rootElements": [
            {
                "id": "el_sec_bad",
                "name": "سکشن مخرب",
                "type": "container",
                "styles": {
                    "mobile": {},
                    "customCssClass": "test <script>alert(1)</script>",
                },
                "children": [],
            }
        ],
    }
    with pytest.raises(InvalidCssError):
        validate_page_ast(bad_ast_dict)

    # 2. Template with unregistered widget type
    unregistered_widget_ast = {
        "schemaVersion": 1,
        "title": "قالب با ویجت نامعتبر",
        "slug": "invalid-widget-template",
        "rootElements": [
            {
                "id": "el_sec_good",
                "name": "سکشن",
                "type": "container",
                "children": [
                    {
                        "id": "el_wid_bad",
                        "name": "ویجت غیرمجاز",
                        "type": "widget",
                        "widgetType": "unauthorized_remote_eval",
                        "children": [],
                    }
                ],
            }
        ],
    }
    with pytest.raises(InvalidWidgetTypeError):
        validate_page_ast(unregistered_widget_ast)


def test_theme_builder_widgets_validation_allowed():
    """Verify that breadcrumbs, search_bar, and nav_menu are in STANDARD_WIDGET_TYPES and valid."""
    from app.modules.content.domain.builder_validation import STANDARD_WIDGET_TYPES, validate_page_ast

    assert "breadcrumbs" in STANDARD_WIDGET_TYPES
    assert "search_bar" in STANDARD_WIDGET_TYPES
    assert "nav_menu" in STANDARD_WIDGET_TYPES

    valid_ast_dict = {
        "schemaVersion": 1,
        "title": "قالب با ویجت‌های ناوبری و مسیر",
        "slug": "valid-theme-builder-widgets",
        "rootElements": [
            {
                "id": "el_sec_valid",
                "name": "سکشن",
                "type": "container",
                "children": [
                    {
                        "id": "el_wid_bread",
                        "name": "مسیر راهنما",
                        "type": "widget",
                        "widgetType": "breadcrumbs",
                        "widgetProps": {"separator": "/"},
                        "children": [],
                    },
                    {
                        "id": "el_wid_search",
                        "name": "فرم جستجو",
                        "type": "widget",
                        "widgetType": "search_bar",
                        "widgetProps": {"placeholder": "جستجو..."},
                        "children": [],
                    },
                    {
                        "id": "el_wid_nav",
                        "name": "فهرست ناوبری",
                        "type": "widget",
                        "widgetType": "nav_menu",
                        "widgetProps": {"items": [{"title": "خانه", "url": "/"}]},
                        "children": [],
                    },
                ],
            }
        ],
    }
    validated = validate_page_ast(valid_ast_dict)
    assert len(validated.root_elements[0].children) == 3

