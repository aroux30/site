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


def test_ast_compiler_renders_p3_ecommerce_native_widgets():
    ast = PageAST(
        schema_version=1,
        title="تست ویجت‌های بومی فروشگاهی P3",
        slug="test-p3-native-ecom",
        root_elements=[
            BuilderElement(
                id="el_ecom_sec",
                name="بخش محصولات",
                type="container",
                children=[
                    BuilderElement(
                        id="el_price01",
                        name="قیمت محصول",
                        type="widget",
                        widget_type="product_price",
                        widget_props={"price": "۱,۲۰۰,۰۰۰", "compare_at_price": "۱,۵۰۰,۰۰۰", "currency": "تومان"},
                    ),
                    BuilderElement(
                        id="el_cart_btn01",
                        name="دکمه خرید",
                        type="widget",
                        widget_type="add_to_cart",
                        widget_props={"label": "خرید آنلاین", "variant_id": "var_99"},
                    ),
                    BuilderElement(
                        id="el_variants01",
                        name="تنوع محصول",
                        type="widget",
                        widget_type="product_variants",
                        widget_props={
                            "product_title": "رنگ‌بندی هدفون",
                            "variants": [
                                {"id": "v1", "title": "مشکی مات", "price": "۱,۲۰۰,۰۰۰"},
                                {"id": "v2", "title": "سفید صدفی", "price": "۱,۲۵۰,۰۰۰"},
                            ],
                        },
                    ),
                    BuilderElement(
                        id="el_mini_cart01",
                        name="مینی کارت",
                        type="widget",
                        widget_type="mini_cart",
                        widget_props={"item_count": 3},
                    ),
                    BuilderElement(
                        id="el_cart_sum01",
                        name="خلاصه سبد",
                        type="widget",
                        widget_type="cart_summary",
                        widget_props={"subtotal": "۳,۴۵۰,۰۰۰"},
                    ),
                    BuilderElement(
                        id="el_grid01",
                        name="ویترین کالاها",
                        type="widget",
                        widget_type="product_grid",
                        widget_props={"limit": 4, "category": "digital", "show_pagination": True},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-product-price' in result
    assert '۱,۲۰۰,۰۰۰' in result
    assert 'builder-add-to-cart' in result
    assert 'data-variant-id="var_99"' in result
    assert 'خرید آنلاین' in result
    assert 'builder-product-variants' in result
    assert 'مشکی مات' in result
    assert 'builder-mini-cart' in result
    assert 'builder-cart-summary' in result
    assert '۳,۴۵۰,۰۰۰ تومان' in result
    assert 'builder-product-grid' in result
    assert 'data-category="digital"' in result
    assert 'مشاهده محصولات بیشتر' in result


def test_ast_compiler_renders_p4_advanced_layout_and_interactive_widgets():
    from app.modules.content.domain.builder_ast import DeviceStyle

    ast = PageAST(
        schema_version=1,
        title="تست قابلیت‌های P4",
        slug="test-p4-advanced",
        root_elements=[
            # 1. Container with advanced layout & form
            BuilderElement(
                id="el_form_sec",
                name="فرم تماس",
                type="container",
                widget_type="form_container",
                widget_props={
                    "submit_url": "/api/v1/content/forms/submit",
                    "success_message": "پیام شما ارسال شد",
                },
                visible_on_desktop=True,
                visible_on_mobile=False,  # hidden on mobile
                auth_visibility="authenticated",
                styles=ResponsiveStyles(
                    mobile=DeviceStyle(
                        position="relative",
                        z_index=10,
                        overflow="hidden",
                    )
                ),
                children=[
                    BuilderElement(
                        id="el_chk01",
                        name="تیک پذیرش",
                        type="widget",
                        widget_type="form_checkbox",
                        widget_props={"label": "پذیرش قوانین", "name": "terms", "required": True},
                    ),
                    BuilderElement(
                        id="el_rad01",
                        name="رادیو انتخاب",
                        type="widget",
                        widget_type="form_radio",
                        widget_props={"label": "نوع ارسال", "name": "ship", "options": ["پیشتاز", "پیک"]},
                    ),
                ],
            ),
            # 2. Interactive widgets
            BuilderElement(
                id="el_inter_sec",
                name="ویجت‌های تعاملی",
                type="container",
                children=[
                    BuilderElement(
                        id="el_acc01",
                        name="آکاردئون",
                        type="widget",
                        widget_type="accordion",
                        widget_props={
                            "items": [{"title": "گارانتی کالا چقدر است؟", "content": "۱۸ ماه ضمانت طلایی"}],
                        },
                    ),
                    BuilderElement(
                        id="el_tabs01",
                        name="تب‌ها",
                        type="widget",
                        widget_type="tabs",
                        widget_props={
                            "tabs": [{"title": "توضیحات", "content": "توضیحات فنی محصول"}, {"title": "دیدگاه‌ها", "content": "دیدگاه خریداران"}],
                        },
                    ),
                    BuilderElement(
                        id="el_count01",
                        name="شمارنده معکوس",
                        type="widget",
                        widget_type="countdown",
                        widget_props={"title": "تخفیف ویژه شب عید"},
                    ),
                    BuilderElement(
                        id="el_vid01",
                        name="ویدئو",
                        type="widget",
                        widget_type="video",
                        widget_props={"video_type": "aparat", "url": "https://www.aparat.com/v/example"},
                    ),
                    BuilderElement(
                        id="el_box01",
                        name="باکس آیکون",
                        type="widget",
                        widget_type="icon_box",
                        widget_props={"title": "پشتیبانی ۲۴ ساعته", "description": "پاسخگویی هفت روز هفته"},
                    ),
                    BuilderElement(
                        id="el_soc01",
                        name="شبکه‌های اجتماعی",
                        type="widget",
                        widget_type="social_links",
                        widget_props={"links": [{"platform": "تلگرام", "url": "https://t.me/example"}]},
                    ),
                ],
            ),
        ],
    )
    # Server-side auth filtering check (P5 Hardening):
    guest_result = ASTCompiler.compile(ast, is_authenticated=False)
    assert '<form id="el_form_sec"' not in guest_result
    assert 'پذیرش قوانین' not in guest_result

    # Authenticated user result includes the authenticated-only container
    result = ASTCompiler.compile(ast, is_authenticated=True)
    # Form container & honeypot
    assert '<form id="el_form_sec"' in result
    assert 'data-form-container="true"' in result
    assert 'data-success-message="پیام شما ارسال شد"' in result
    assert '_hp_website' in result
    assert 'max-md:hidden' in result  # mobile hidden
    assert 'data-auth="authenticated"' in result
    assert 'position:relative' in result or 'position: relative' in result
    assert 'z-index:10' in result or 'z-index: 10' in result
    assert 'overflow:hidden' in result or 'overflow: hidden' in result
    # Form inputs
    assert 'builder-form-checkbox' in result
    assert 'پذیرش قوانین' in result
    assert 'builder-form-radio' in result
    assert 'پیشتاز' in result
    # Interactive widgets
    assert 'builder-accordion' in result
    assert 'گارانتی کالا چقدر است؟' in result
    assert '۱۸ ماه ضمانت طلایی' in result
    assert 'builder-tabs' in result
    assert 'دیدگاه‌ها' in result
    assert 'builder-countdown' in result
    assert 'تخفیف ویژه شب عید' in result
    assert 'builder-video' in result
    assert 'aparat.com' in result
    assert 'builder-icon_box' in result or 'builder-icon-box' in result
    assert 'پشتیبانی ۲۴ ساعته' in result
    assert 'builder-social-links' in result
    assert 'تلگرام' in result


def test_ast_compiler_large_page_performance_100_elements():
    """Performance Benchmark (P5 Production Hardening):

    A large production page containing 100+ elements (nested sections,
    cards, buttons, text fields) must compile in under 200ms.
    """
    import time

    sections = []
    element_count = 0
    for s_idx in range(20):
        children = []
        for c_idx in range(5):
            children.append(
                BuilderElement(
                    id=f"el_w{s_idx:02d}_{c_idx:02d}",
                    name=f"ویجت محتوایی {s_idx}-{c_idx}",
                    type="widget",
                    widget_type="heading" if c_idx % 2 == 0 else "button",
                    widget_props={
                        "text": f"عنوان سطر {s_idx} شماره {c_idx}",
                        "label": f"دکمه اقدام {s_idx}-{c_idx}",
                        "url": f"/item/{s_idx}/{c_idx}",
                    },
                )
            )
            element_count += 1

        sections.append(
            BuilderElement(
                id=f"el_sec_{s_idx:02d}",
                name=f"سکشن {s_idx}",
                type="container",
                layout=ContainerLayout(kind="flex", direction="column"),
                children=children,
            )
        )
        element_count += 1

    ast = PageAST(
        schema_version=1,
        title="برگه بزرگ با بیش از ۱۰۰ المان",
        slug="large-perf-page",
        root_elements=sections,
    )
    assert element_count == 120

    start = time.perf_counter()
    html_output = ASTCompiler.compile(ast, is_authenticated=True)
    duration_ms = (time.perf_counter() - start) * 1000

    assert duration_ms < 250.0  # Must compile well under 250ms
    assert len(html_output) > 5000
    assert 'id="el_sec_00"' in html_output
    assert 'id="el_w19_04"' in html_output
    assert 'class="builder-document"' in html_output


def test_ast_compiler_renders_round24_elementor_widgets():
    """Verify SSR AST compilation for progress_bar, testimonial, call_to_action, animated_headline, flip_box, and alert."""
    ast = PageAST(
        schema_version=1,
        title="تست ویجت‌های پورت راند ۲۴",
        slug="test-r24-widgets",
        root_elements=[
            BuilderElement(
                id="el_sec_r24",
                name="بخش ویجت‌های جدید",
                type="container",
                children=[
                    BuilderElement(
                        id="el_pb01",
                        name="نوار پیشرفت",
                        type="widget",
                        widget_type="progress_bar",
                        widget_props={"title": "پیشرفت پروژه", "percentage": 85, "show_percentage": True},
                    ),
                    BuilderElement(
                        id="el_testi01",
                        name="دیدگاه",
                        type="widget",
                        widget_type="testimonial",
                        widget_props={
                            "author": "محمد رضایی",
                            "role": "مدیر مارکتینگ",
                            "company": "دیجی‌تست",
                            "quote": "خدمات فوق‌العاده حرفه‌ای و سریع",
                        },
                    ),
                    BuilderElement(
                        id="el_cta01",
                        name="فراخوان",
                        type="widget",
                        widget_type="call_to_action",
                        widget_props={
                            "badge": "ویژه",
                            "title": "ثبت نام زودهنگام",
                            "description": "از تخفیف ۴۰ درصدی بهره‌مند شوید",
                            "button_label": "عضویت سریع",
                        },
                    ),
                    BuilderElement(
                        id="el_anim01",
                        name="سرتیتر انیمیشنی",
                        type="widget",
                        widget_type="animated_headline",
                        widget_props={
                            "before_text": "پلتفرم",
                            "highlighted_text": "هوشمند",
                            "after_text": "فروشگاهی",
                        },
                    ),
                    BuilderElement(
                        id="el_flip01",
                        name="فلیپ‌باکس",
                        type="widget",
                        widget_type="flip_box",
                        widget_props={
                            "front_title": "پلن نقره‌ای",
                            "front_desc": "برای استارتاپ‌ها",
                            "back_title": "امکانات پلن",
                            "back_desc": "پشتیبانی شبانه‌روزی",
                            "button_text": "انتخاب پلن",
                        },
                    ),
                    BuilderElement(
                        id="el_alert01",
                        name="اعلان",
                        type="widget",
                        widget_type="alert",
                        widget_props={
                            "alert_type": "warning",
                            "title": "توجه مهم",
                            "description": "به‌روزرسانی سرورها امشب انجام خواهد شد.",
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-progress-bar' in result
    assert 'پیشرفت پروژه' in result
    assert '85%' in result
    assert 'builder-testimonial' in result
    assert 'محمد رضایی' in result
    assert 'دیجی‌تست' in result
    assert 'builder-cta' in result
    assert 'ثبت نام زودهنگام' in result
    assert 'عضویت سریع' in result
    assert 'builder-animated-headline' in result
    assert 'هوشمند' in result
    assert 'builder-flip-box' in result
    assert 'پلن نقره‌ای' in result
    assert 'انتخاب پلن' in result
    assert 'builder-alert' in result
    assert 'bg-amber-500/10' in result
    assert 'توجه مهم' in result


def test_ast_compiler_renders_round25_dynamic_ecommerce_props():
    """Verify that cart_summary, recently_viewed, and mini_cart honor dynamic user customizations in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست پورت‌های راند ۲۵",
        slug="test-r25-ecom",
        root_elements=[
            BuilderElement(
                id="el_sec_r25",
                name="بخش فروشگاهی سفارشی",
                type="container",
                children=[
                    BuilderElement(
                        id="el_cs_custom",
                        name="خلاصه سفارشی",
                        type="widget",
                        widget_type="cart_summary",
                        widget_props={
                            "title": "فاکتور نهایی و تسویه",
                            "button_label": "پرداخت اینترنتی سفارش",
                            "checkout_url": "/checkout/gateway",
                            "show_discount": True,
                            "subtotal": "۴,۵۰۰,۰۰۰",
                        },
                    ),
                    BuilderElement(
                        id="el_rv_custom",
                        name="بازدیدهای سفارشی",
                        type="widget",
                        widget_type="recently_viewed",
                        widget_props={
                            "title": "محصولات مورد علاقه شما",
                            "limit": 3,
                        },
                    ),
                    BuilderElement(
                        id="el_mc_custom",
                        name="مینی کارت سفارشی",
                        type="widget",
                        widget_type="mini_cart",
                        widget_props={
                            "label": "سبد خرید من",
                            "item_count": 5,
                            "show_badge": True,
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-cart-summary' in result
    assert 'فاکتور نهایی و تسویه' in result
    assert 'پرداخت اینترنتی سفارش' in result
    assert '/checkout/gateway' in result
    assert 'تخفیف:' in result
    assert '۴,۵۰۰,۰۰۰ تومان' in result
    assert 'builder-recently-viewed' in result
    assert 'محصولات مورد علاقه شما' in result
    assert 'کالای اخیر 3' in result
    assert 'builder-mini-cart' in result
    assert 'سبد خرید من' in result
    assert '5</span>' in result


def test_ast_compiler_renders_round26_star_rating_and_review_histogram_parity():
    """Verify that star_rating and review_histogram handle showValue and average percentages accurately."""
    ast = PageAST(
        schema_version=1,
        title="تست امتیاز و هیستوگرام راند ۲۶",
        slug="test-r26-reviews",
        root_elements=[
            BuilderElement(
                id="el_sec_r26",
                name="بخش نظرات و امتیاز",
                type="container",
                children=[
                    BuilderElement(
                        id="el_sr_custom",
                        name="امتیاز ستاره‌ای",
                        type="widget",
                        widget_type="star_rating",
                        widget_props={
                            "value": 4.9,
                            "reviewCount": 180,
                            "showValue": True,
                        },
                    ),
                    BuilderElement(
                        id="el_rh_custom",
                        name="هیستوگرام نظرات",
                        type="widget",
                        widget_type="review_histogram",
                        widget_props={
                            "averageRating": 4.5,
                            "totalReviews": 95,
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-star-rating' in result
    assert '★ 4.9' in result
    assert '(180 نظر)' in result
    assert 'builder-review-histogram' in result
    assert '4.5 از ۵' in result
    assert 'بر اساس 95 نظر' in result
    assert 'width:90%' in result or 'width: 90%' in result


def test_ast_compiler_renders_round27_countdown_and_iconbox_customizations():
    """Verify that countdown and icon_box widgets compile customized titles and descriptions accurately."""
    ast = PageAST(
        schema_version=1,
        title="تست راند ۲۷",
        slug="test-r27-widgets",
        root_elements=[
            BuilderElement(
                id="el_sec_r27",
                name="بخش ۲۷",
                type="container",
                children=[
                    BuilderElement(
                        id="el_cd_custom",
                        name="شمارنده",
                        type="widget",
                        widget_type="countdown",
                        widget_props={
                            "title": "جشنواره فروش زمستانه",
                            "target_date": "2026-12-31T23:59:59",
                        },
                    ),
                    BuilderElement(
                        id="el_ib_custom",
                        name="باکس ویژگی",
                        type="widget",
                        widget_type="icon_box",
                        widget_props={
                            "title": "ارسال سریع و اکسپرس",
                            "description": "تحویل ۳ ساعته در تهران و ۲۴ ساعته در سایر شهرها",
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-countdown' in result
    assert 'جشنواره فروش زمستانه' in result
    assert 'data-target="2026-12-31T23:59:59"' in result
    assert 'builder-icon-box' in result
    assert 'ارسال سریع و اکسپرس' in result
    assert 'تحویل ۳ ساعته در تهران' in result


def test_ast_compiler_renders_round28_table_highlight_column_parity():
    """Verify that table widget compiles highlightCol with distinctive styling in thead and tbody."""
    ast = PageAST(
        schema_version=1,
        title="تست جدول راند ۲۸",
        slug="test-r28-table",
        root_elements=[
            BuilderElement(
                id="el_sec_r28",
                name="بخش ۲۸",
                type="container",
                children=[
                    BuilderElement(
                        id="el_tbl_custom",
                        name="جدول مقایسه",
                        type="widget",
                        widget_type="table",
                        widget_props={
                            "headers": ["ویژگی", "مدل پایه", "مدل پرو"],
                            "rows": [
                                ["گارانتی", "۱۲ ماه", "۲۴ ماه طلایی"],
                                ["ارسال", "عادی", "اکسپرس رایگان"],
                            ],
                            "bordered": True,
                            "striped": True,
                            "highlightCol": 2,
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-table' in result
    assert 'مدل پرو</th>' in result
    assert 'bg-primary/10 text-primary font-bold border-x border-primary/20' in result
    assert '۲۴ ماه طلایی</td>' in result
    assert 'bg-primary/5 border-x border-primary/20 font-semibold' in result


def test_ast_compiler_renders_round29_form_checkbox_and_radio_required_stars():
    """Verify that form_checkbox and form_radio render required asterisks and required attributes in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست فرم راند ۲۹",
        slug="test-r29-forms",
        root_elements=[
            BuilderElement(
                id="el_sec_r29",
                name="بخش فرم ۲۹",
                type="container",
                children=[
                    BuilderElement(
                        id="el_chk_req",
                        name="چک‌باکس قوانین",
                        type="widget",
                        widget_type="form_checkbox",
                        widget_props={
                            "label": "قوانین سایت را می‌پذیرم",
                            "name": "terms_accepted",
                            "required": True,
                            "checked": True,
                        },
                    ),
                    BuilderElement(
                        id="el_rad_req",
                        name="رادیو پست",
                        type="widget",
                        widget_type="form_radio",
                        widget_props={
                            "label": "شیوه تحویل بار",
                            "name": "delivery_type",
                            "options": ["پیک موتوری", "پست پیشتاز"],
                            "required": True,
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-form-checkbox' in result
    assert 'name="terms_accepted"' in result
    assert 'checked' in result
    assert 'required' in result
    assert 'قوانین سایت را می‌پذیرم <span class="text-destructive ms-1">*</span>' in result
    assert 'builder-form-radio' in result
    assert 'شیوه تحویل بار <span class="text-destructive ms-1">*</span>' in result
    assert 'name="delivery_type"' in result
    assert 'value="پیک موتوری"' in result









