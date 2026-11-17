"""Unit tests for Visual Page Builder ASTCompiler (Phase P0)."""

from __future__ import annotations

import pytest
from app.modules.content.application.ast_compiler import ASTCompiler
from app.modules.content.domain.builder_ast import (
    BuilderElement,
    ContainerLayout,
    PageAST,
    ResponsiveStyles,
    SpacingBox,
    UnitValue,
)


def test_ast_compiler_renders_semantic_html():
    ast = PageAST(
        schema_version=1,
        title="صفحه تست کامپایلر",
        slug="test-compile",
        root_elements=[
            BuilderElement(
                id="el_sec01",
                name="بخش یک",
                type="container",
                layout=ContainerLayout(kind="flex", direction="column"),
                children=[
                    BuilderElement(
                        id="el_head01",
                        name="سرتیتر",
                        type="widget",
                        widget_type="heading",
                        widget_props={"text": "عنوان تستی", "tag": "h1"},
                    ),
                    BuilderElement(
                        id="el_btn01",
                        name="دکمه",
                        type="widget",
                        widget_type="button",
                        widget_props={"label": "ثبت نام", "url": "/register"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert '<div class="builder-document" dir="rtl">' in result
    assert '<h1 id="el_head01"' in result
    assert "عنوان تستی</h1>" in result
    assert '<a href="/register" id="el_btn01"' in result
    assert "ثبت نام</a>" in result


def test_ast_compiler_strips_malicious_script_tags():
    ast = PageAST(
        schema_version=1,
        title="تست امنیت",
        slug="test-xss",
        root_elements=[
            BuilderElement(
                id="el_sec01",
                name="بخش امن",
                type="container",
                children=[
                    BuilderElement(
                        id="el_txt01",
                        name="متن غنی",
                        type="widget",
                        widget_type="text_editor",
                        widget_props={
                            "content": '<p>متن سالم</p><script>alert("hacked")</script><img src="x" onerror="alert(1)">'
                        },
                    )
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "<script>" not in result
    assert "alert" not in result
    assert "onerror" not in result
    assert "متن سالم" in result


def test_ast_compiler_renders_native_table_and_form_widgets():
    ast = PageAST(
        schema_version=1,
        title="تست ویجت‌های جدول و فرم",
        slug="test-table-form",
        root_elements=[
            BuilderElement(
                id="el_sec02",
                name="بخش جدول و فرم",
                type="container",
                children=[
                    BuilderElement(
                        id="el_tbl01",
                        name="جدول مشخصات",
                        type="widget",
                        widget_type="table",
                        widget_props={
                            "headers": ["ویژگی", "مدل A", "مدل B"],
                            "rows": [["گارانتی", "۱۸ ماه", "۱۲ ماه"], ["ارسال", "رایگان", "عادی"]],
                            "bordered": True,
                            "striped": True,
                        },
                    ),
                    BuilderElement(
                        id="el_inp01",
                        name="ورودی نام",
                        type="widget",
                        widget_type="form_input",
                        widget_props={
                            "label": "نام کامل",
                            "name": "full_name",
                            "placeholder": "مثلاً علی رضایی",
                            "required": True,
                        },
                    ),
                    BuilderElement(
                        id="el_txta01",
                        name="پیام",
                        type="widget",
                        widget_type="form_textarea",
                        widget_props={
                            "label": "متن پیام",
                            "name": "msg",
                            "placeholder": "پیام خود را بنویسید",
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert '<table class="w-full border-collapse' in result
    assert "<th" in result
    assert "مدل A" in result
    assert "۱۸ ماه" in result
    assert 'name="full_name"' in result
    assert 'placeholder="مثلاً علی رضایی"' in result
    assert 'name="msg"' in result
    assert "متن پیام</label>" in result


def test_ast_compiler_renders_phase_3_storefront_widgets():
    ast = PageAST(
        schema_version=1,
        title="تست ویجت‌های فروشگاهی فاز ۳",
        slug="test-p3-widgets",
        root_elements=[
            BuilderElement(
                id="el_p3_sec",
                name="بخش فروشگاه",
                type="container",
                children=[
                    BuilderElement(
                        id="el_card01",
                        name="کارت محصول",
                        type="widget",
                        widget_type="product_card",
                        widget_props={
                            "name": "ساعت هوشمند گلکسی",
                            "min_price": "۲,۵۰۰,۰۰۰",
                            "primary_image_url": "/watch.jpg",
                            "is_in_stock": True,
                        },
                    ),
                    BuilderElement(
                        id="el_star01",
                        name="امتیاز ستاره‌ای",
                        type="widget",
                        widget_type="star_rating",
                        widget_props={"value": 4.9, "reviewCount": 42},
                    ),
                    BuilderElement(
                        id="el_hist01",
                        name="نمودار نظرات",
                        type="widget",
                        widget_type="review_histogram",
                        widget_props={"averageRating": 4.7, "totalReviews": 95},
                    ),
                    BuilderElement(
                        id="el_rv01",
                        name="بازدیدهای اخیر",
                        type="widget",
                        widget_type="recently_viewed",
                        widget_props={"limit": 6},
                    ),
                    BuilderElement(
                        id="el_mega01",
                        name="مگامنو",
                        type="widget",
                        widget_type="mega_menu",
                        widget_props={"label": "دسته‌ها"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-product-card' in result
    assert 'ساعت هوشمند گلکسی' in result
    assert 'builder-star-rating' in result
    assert '★ 4.9' in result
    assert 'builder-review-histogram' in result
    assert '۴۲ نظر' in result or '(42 نظر)' in result
    assert 'builder-recently-viewed' in result
    assert 'builder-mega-menu' in result
    assert 'دسته‌ها' in result


def test_ast_compiler_renders_phase_4_entrance_animations():
    ast = PageAST(
        schema_version=1,
        title="تست انیمیشن‌های فاز ۴",
        slug="test-p4-animations",
        root_elements=[
            BuilderElement(
                id="el_anim_sec",
                name="بخش با انیمیشن",
                type="container",
                styles=ResponsiveStyles(
                    animation="slide-up",
                    animation_duration=0.8,
                    animation_delay=0.2,
                ),
                children=[
                    BuilderElement(
                        id="el_anim_hd",
                        name="سرتیتر متحرک",
                        type="widget",
                        widget_type="heading",
                        widget_props={"text": "عنوان با فید", "tag": "h2"},
                        styles=ResponsiveStyles(
                            animation="fade-in",
                            animation_duration=0.5,
                        ),
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-animate-slide-up' in result
    assert 'animation-duration:0.8s' in result or 'animation-duration: 0.8s' in result
    assert 'animation-delay:0.2s' in result or 'animation-delay: 0.2s' in result
    assert 'builder-animate-fade-in' in result
    assert 'animation-duration:0.5s' in result or 'animation-duration: 0.5s' in result
    assert 'عنوان با فید' in result



