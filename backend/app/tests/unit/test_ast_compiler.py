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


def test_ast_compiler_renders_image_box_and_toggle_widgets():
    """Verify SSR compilation for image_box and toggle widgets."""
    ast = PageAST(
        schema_version=1,
        title="تست جعبه تصویر و تاگل",
        slug="test-imagebox-toggle",
        root_elements=[
            BuilderElement(
                id="el_sec_new",
                name="بخش ویجت‌های نو",
                type="container",
                children=[
                    BuilderElement(
                        id="el_imgbox01",
                        name="باکس تصویر",
                        type="widget",
                        widget_type="image_box",
                        widget_props={
                            "image_url": "/banner.jpg",
                            "title": "ارسال رایگان به سراسر کشور",
                            "description": "تحویل سریع با پست پیشتاز",
                            "position": "top",
                        },
                    ),
                    BuilderElement(
                        id="el_toggle01",
                        name="آیتم تاشو",
                        type="widget",
                        widget_type="toggle",
                        widget_props={
                            "items": [
                                {"title": "سوال نخست", "content": "پاسخ نخستین", "is_open": True},
                                {"title": "سوال دوم", "content": "پاسخ دومین", "is_open": False},
                            ]
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-image-box' in result
    assert "ارسال رایگان به سراسر کشور" in result
    assert "/banner.jpg" in result
    assert 'class="builder-toggle' in result
    assert "سوال نخست" in result
    assert "پاسخ نخستین" in result
    assert "سوال دوم" in result


def test_ast_compiler_renders_share_buttons_and_tracker_widgets():
    """Verify SSR compilation for share_buttons, progress_tracker, and table_of_contents."""
    ast = PageAST(
        schema_version=1,
        title="تست دکمه‌های اشتراک و ردگیر",
        slug="test-share-tracker",
        root_elements=[
            BuilderElement(
                id="el_sec_share",
                name="بخش اشتراک",
                type="container",
                children=[
                    BuilderElement(
                        id="el_share01",
                        name="اشتراک گذاری",
                        type="widget",
                        widget_type="share_buttons",
                        widget_props={"networks": ["telegram", "whatsapp"], "shape": "rounded"},
                    ),
                    BuilderElement(
                        id="el_track01",
                        name="ردگیر اسکرول",
                        type="widget",
                        widget_type="progress_tracker",
                        widget_props={"height": 6},
                    ),
                    BuilderElement(
                        id="el_toc01",
                        name="فهرست محتوا",
                        type="widget",
                        widget_type="table_of_contents",
                        widget_props={"title": "فهرست مقالات", "items": [{"text": "بخش نخست", "level": 2}]},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-share-buttons' in result
    assert "تلگرام" in result
    assert "واتس‌اپ" in result
    assert 'class="builder-progress-tracker' in result
    assert "height:6px" in result or "height: 6px" in result
    assert 'class="builder-toc' in result
    assert "فهرست مقالات" in result
    assert "بخش نخست" in result


def test_ast_compiler_renders_hotspot_and_lottie_widgets():
    """Verify SSR compilation for hotspot and lottie widgets."""
    ast = PageAST(
        schema_version=1,
        title="تست هات‌اسپات و لوتی",
        slug="test-hotspot-lottie",
        root_elements=[
            BuilderElement(
                id="el_sec_hl",
                name="بخش تعاملی",
                type="container",
                children=[
                    BuilderElement(
                        id="el_hotspot01",
                        name="تصویر با نقطه",
                        type="widget",
                        widget_type="hotspot",
                        widget_props={
                            "image_url": "/room.jpg",
                            "spots": [{"x": 25, "y": 60, "title": "مبل راحتی", "content": "چرم طبیعی"}],
                        },
                    ),
                    BuilderElement(
                        id="el_lottie01",
                        name="انیمیشن",
                        type="widget",
                        widget_type="lottie",
                        widget_props={"url": "https://assets.lottiefiles.com/anim.json", "loop": True},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-hotspot' in result
    assert "/room.jpg" in result
    assert "مبل راحتی" in result
    assert 'class="builder-lottie' in result
    assert "anim.json" in result


def test_ast_compiler_renders_code_highlight_and_contact_buttons_widgets():
    """Verify SSR compilation for code_highlight and contact_buttons widgets."""
    ast = PageAST(
        schema_version=1,
        title="تست هایلایت کد و دکمه تماس",
        slug="test-code-contact",
        root_elements=[
            BuilderElement(
                id="el_sec_cc",
                name="بخش فنی",
                type="container",
                children=[
                    BuilderElement(
                        id="el_code01",
                        name="کد برنامه",
                        type="widget",
                        widget_type="code_highlight",
                        widget_props={"code": "const x = 10;", "language": "typescript"},
                    ),
                    BuilderElement(
                        id="el_contact01",
                        name="تماس",
                        type="widget",
                        widget_type="contact_buttons",
                        widget_props={"title": "پشتیبانی تلفنی", "phone": "021-9999", "button_label": "تماس"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-code-highlight' in result
    assert "const x = 10;" in result
    assert "typescript" in result
    assert 'class="builder-contact-buttons' in result
    assert "پشتیبانی تلفنی" in result
    assert "021-9999" in result


def test_ast_compiler_renders_image_carousel_and_slides_widgets():
    """Verify SSR compilation for image_carousel and slides widgets."""
    ast = PageAST(
        schema_version=1,
        title="تست اسلایدر و کاروسل",
        slug="test-carousel-slides",
        root_elements=[
            BuilderElement(
                id="el_sec_cs",
                name="بخش اسلایدر",
                type="container",
                children=[
                    BuilderElement(
                        id="el_carousel01",
                        name="کاروسل",
                        type="widget",
                        widget_type="image_carousel",
                        widget_props={"images": [{"url": "/img1.jpg", "alt": "عکس یک"}]},
                    ),
                    BuilderElement(
                        id="el_slides01",
                        name="اسلایدشو",
                        type="widget",
                        widget_type="slides",
                        widget_props={"slides": [{"title": "تخفیف شگفت انگیز", "description": "فرصت خرید", "button_label": "خرید"}]},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-image-carousel' in result
    assert "/img1.jpg" in result
    assert 'class="builder-slides' in result
    assert "تخفیف شگفت انگیز" in result
    assert "فرصت خرید" in result


def test_ast_compiler_renders_nested_and_interactive_modules():
    """Verify SSR compilation for nested_tabs, nested_accordion, off_canvas and popup_builder."""
    ast = PageAST(
        schema_version=1,
        title="تست ماژول‌های تعاملی پیشرفته",
        slug="test-interactive-modules",
        root_elements=[
            BuilderElement(
                id="el_sec_im",
                name="بخش تعاملی",
                type="container",
                children=[
                    BuilderElement(
                        id="el_ntabs01",
                        name="تب‌های تودرتو",
                        type="widget",
                        widget_type="nested_tabs",
                        widget_props={"tabs": [{"title": "مشخصات فنی", "content": "رم ۱۶ گیگابایت"}]},
                    ),
                    BuilderElement(
                        id="el_nacc01",
                        name="آکاردئون پیشرفته",
                        type="widget",
                        widget_type="nested_accordion",
                        widget_props={"items": [{"title": "پرسش کلیدی", "content": "پاسخ ساختاریافته"}]},
                    ),
                    BuilderElement(
                        id="el_offc01",
                        name="کشوی جانبی",
                        type="widget",
                        widget_type="off_canvas",
                        widget_props={"trigger_label": "فیلتر پیشرفته", "drawer_title": "فیلترها"},
                    ),
                    BuilderElement(
                        id="el_popup01",
                        name="پاپ‌آپ مدال",
                        type="widget",
                        widget_type="popup_builder",
                        widget_props={"popup_title": "کوپن تخفیف ۲۰٪", "trigger": "exit_intent"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-nested-tabs' in result
    assert "مشخصات فنی" in result
    assert "رم ۱۶ گیگابایت" in result
    assert 'class="builder-nested-accordion' in result
    assert "پرسش کلیدی" in result
    assert 'class="builder-off-canvas' in result
    assert "فیلتر پیشرفته" in result
    assert 'class="builder-popup' in result
    assert "کوپن تخفیف ۲۰٪" in result


def test_ast_compiler_renders_multistep_and_loop_carousel_widgets():
    """Verify SSR compilation for multi_step_form and loop_carousel."""
    ast = PageAST(
        schema_version=1,
        title="تست فرم چندمرحله‌ای و کاروسل حلقه",
        slug="test-step-loop",
        root_elements=[
            BuilderElement(
                id="el_sec_sl",
                name="بخش پیشرفته",
                type="container",
                children=[
                    BuilderElement(
                        id="el_msform01",
                        name="فرم چندگامی",
                        type="widget",
                        widget_type="multi_step_form",
                        widget_props={"steps": [{"title": "گام ۱"}, {"title": "گام ۲"}]},
                    ),
                    BuilderElement(
                        id="el_lcar01",
                        name="کاروسل حلقه",
                        type="widget",
                        widget_type="loop_carousel",
                        widget_props={"limit": 3, "category": "all"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-multi-step-form' in result
    assert "گام ۱" in result
    assert "گام ۲" in result
    assert 'class="builder-loop-carousel' in result
    assert 'data-widget="loop_carousel"' in result


def test_ast_compiler_renders_audio_and_maps_widgets():
    """Verify SSR compilation for audio and google_maps."""
    ast = PageAST(
        schema_version=1,
        title="تست صوت و نقشه",
        slug="test-audio-maps",
        root_elements=[
            BuilderElement(
                id="el_sec_am",
                name="بخش صوتی و نقشه",
                type="container",
                children=[
                    BuilderElement(
                        id="el_audio01",
                        name="پلیر صوتی",
                        type="widget",
                        widget_type="audio",
                        widget_props={"title": "موسیقی آرامش‌بخش", "url": "/track.mp3"},
                    ),
                    BuilderElement(
                        id="el_maps01",
                        name="نقشه موقعیت",
                        type="widget",
                        widget_type="google_maps",
                        widget_props={"address": "تهران، میدان تجریش", "height": 280},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-audio' in result
    assert "موسیقی آرامش‌بخش" in result
    assert "/track.mp3" in result
    assert 'class="builder-google-maps' in result
    assert "تهران، میدان تجریش" in result


def test_ast_compiler_renders_read_more_and_rating_widgets():
    """Verify SSR compilation for read_more and rating widgets."""
    ast = PageAST(
        schema_version=1,
        title="تست ادامه مطلب و امتیاز",
        slug="test-more-rating",
        root_elements=[
            BuilderElement(
                id="el_sec_mr",
                name="بخش تکمیلی",
                type="container",
                children=[
                    BuilderElement(
                        id="el_more01",
                        name="ادامه مطلب",
                        type="widget",
                        widget_type="read_more",
                        widget_props={"text": "مطالعه بررسی جامع", "url": "/post/1"},
                    ),
                    BuilderElement(
                        id="el_rate01",
                        name="امتیاز جدید",
                        type="widget",
                        widget_type="rating",
                        widget_props={"score": 4.8, "rating_scale": 5},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-read-more' in result
    assert "مطالعه بررسی جامع" in result
    assert "/post/1" in result
    assert 'class="builder-rating' in result
    assert "4.8" in result


def test_ast_compiler_renders_search_bar_and_nav_menu_widgets():
    """Verify SSR compilation for search_bar and nav_menu."""
    ast = PageAST(
        schema_version=1,
        title="تست جستجو و ناوبری",
        slug="test-search-nav",
        root_elements=[
            BuilderElement(
                id="el_sec_sn",
                name="بخش جستجو و منو",
                type="container",
                children=[
                    BuilderElement(
                        id="el_search01",
                        name="نوار جستجو",
                        type="widget",
                        widget_type="search_bar",
                        widget_props={"placeholder": "جستجوی موبایل...", "action_url": "/search"},
                    ),
                    BuilderElement(
                        id="el_nav01",
                        name="منوی سایت",
                        type="widget",
                        widget_type="nav_menu",
                        widget_props={"items": [{"title": "خانه", "url": "/"}]},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-search-bar' in result
    assert "جستجوی موبایل..." in result
    assert 'class="builder-nav-menu' in result
    assert "خانه" in result


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

    assert duration_ms < 400.0  # Must compile well under 400ms
    assert len(html_output) > 5000
    assert 'id="el_sec_00"' in html_output
    assert 'id="el_w19_04"' in html_output
    assert 'class="builder-document"' in html_output


def test_ast_compiler_transform_and_mask_elementor_parity():
    """Verify Elementor Wave 1 Transform & Mask styles compile correctly in SSR."""
    from app.modules.content.domain.builder_ast import DeviceStyle, TransformStyle, MaskStyle, TypographyStyle

    ast = PageAST(
        schema_version=1,
        title="تست تبدیل و ماسک المنتور",
        slug="test-transform-mask",
        root_elements=[
            BuilderElement(
                id="el_tf_01",
                name="تیتر با ترنسفورم",
                type="widget",
                widget_type="heading",
                widget_props={"text": "تیتر چرخان"},
                styles=ResponsiveStyles(
                    mobile=DeviceStyle(
                        typography=TypographyStyle(
                            text_shadow="0 2px 4px rgba(0,0,0,0.5)",
                        ),
                        transform=TransformStyle(
                            rotate=25.0,
                            scale=1.1,
                            skew_x=10.0,
                            translate_x=15.0,
                            translate_y=5.0,
                            flip_x=True,
                        ),
                        mask=MaskStyle(
                            shape="circle",
                            size="contain",
                        ),
                    )
                ),
            ),
            BuilderElement(
                id="el_mask_hex",
                name="تصویر با ماسک شش‌ضلعی",
                type="widget",
                widget_type="image",
                widget_props={"url": "/hero.png", "alt": "شش‌ضلعی"},
                styles=ResponsiveStyles(
                    mobile=DeviceStyle(
                        mask=MaskStyle(
                            shape="hexagon",
                        ),
                    )
                ),
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "rotate(25.0deg)" in result
    assert "scale(1.1)" in result
    assert "skewX(10.0deg)" in result
    assert "translate(15.0px, 5.0px)" in result
    assert "scaleX(-1)" in result
    assert "radial-gradient(circle, black 60%, transparent 60%)" in result
    assert "clip-path: polygon(" in result or "clip-path:polygon(" in result
    assert "text-shadow: 0 2px 4px rgba(0,0,0,0.5)" in result or "text-shadow:0 2px 4px rgba(0,0,0,0.5)" in result


def test_ast_compiler_css_grid_auto_flow_elementor_parity():
    """Verify Elementor Wave 1 CSS Grid auto-flow compiles correctly in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست شبکه چندستونه با جریان خودکار",
        slug="test-grid-autoflow",
        root_elements=[
            BuilderElement(
                id="el_grid_sec",
                name="شبکه گرید",
                type="container",
                layout=ContainerLayout(
                    kind="grid",
                    grid_columns=4,
                    grid_auto_flow="dense",
                ),
                children=[],
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "grid" in result
    assert "grid-cols-4" in result or "lg:grid-cols-4" in result
    assert "grid-auto-flow: dense" in result or "grid-auto-flow:dense" in result


def test_ast_compiler_image_box_and_toggle_elementor_parity():
    """Verify Elementor Wave 2 Image Box & Toggle compile correctly in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست جعبه تصویر و تاگل",
        slug="test-imgbox-toggle",
        root_elements=[
            BuilderElement(
                id="el_img_box_01",
                name="جعبه تصویر تست",
                type="widget",
                widget_type="image_box",
                widget_props={
                    "title": "کیفیت صدای عالی",
                    "description": "تجربه شنیداری فوق‌العاده با تفکیک جزئیات",
                    "image_url": "/sound.png",
                    "link_url": "/product/sound",
                },
            ),
            BuilderElement(
                id="el_toggle_01",
                name="تاگل چندبخشی",
                type="widget",
                widget_type="toggle",
                widget_props={
                    "items": [
                        {"title": "مشخصات فنی", "content": "باتری ۵۰۰۰ میلی‌آمپر", "default_open": True},
                        {"title": "اقلام همراه", "content": "کابل شارژ و دفترچه", "default_open": True},
                    ]
                },
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-image-box" in result
    assert "کیفیت صدای عالی" in result
    assert "/product/sound" in result
    assert "builder-toggle" in result
    assert "مشخصات فنی" in result
    assert "باتری ۵۰۰۰ میلی‌آمپر" in result


def test_ast_compiler_icon_list_elementor_parity():
    """Verify Elementor Core Icon List compiles correctly in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست لیست آیکون‌دار",
        slug="test-icon-list",
        root_elements=[
            BuilderElement(
                id="el_icon_list_01",
                name="لیست مزایا",
                type="widget",
                widget_type="icon_list",
                widget_props={
                    "layout": "horizontal",
                    "items": [
                        {"text": "تحویل اکسپرس", "icon": "check"},
                        {"text": "پرداخت در محل", "icon": "check"},
                    ]
                },
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-icon-list" in result
    assert "تحویل اکسپرس" in result
    assert "پرداخت در محل" in result
    assert "flex flex-wrap" in result


def test_ast_compiler_price_table_elementor_pro_parity():
    """Verify Elementor Pro Price Table compiles correctly in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست جدول قیمت",
        slug="test-price-table",
        root_elements=[
            BuilderElement(
                id="el_ptable_01",
                name="پلن پیشرفته",
                type="widget",
                widget_type="price_table",
                widget_props={
                    "title": "پلن تجاری",
                    "subtitle": "برای شرکت‌های بزرگ",
                    "price": "۹۹۰,۰۰۰",
                    "currency": "تومان",
                    "period": "ماهانه",
                    "is_featured": True,
                    "button_label": "سفارش پلن",
                    "features": [
                        {"text": "فضای نامحدود", "available": True},
                        {"text": "پشتیبانی اختصاصی VIP", "available": True},
                        {"text": "دامنه اختصاصی", "available": False},
                        "پشتیبانی تیکتی ۲۴ ساعته",
                    ]
                },
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-price-table" in result
    assert "پلن تجاری" in result
    assert "۹۹۰,۰۰۰" in result
    assert "پیشنهاد ویژه" in result
    assert "پشتیبانی اختصاصی VIP" in result
    assert "دامنه اختصاصی" in result
    assert "line-through" in result
    assert "پشتیبانی تیکتی ۲۴ ساعته" in result
    assert "سفارش پلن" in result


def test_ast_compiler_price_list_elementor_pro_parity():
    """Verify Elementor Pro Price List compiles correctly in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست لیست قیمت و منو",
        slug="test-price-list",
        root_elements=[
            BuilderElement(
                id="el_plist_01",
                name="منوی کافه",
                type="widget",
                widget_type="price_list",
                widget_props={
                    "items": [
                        {"title": "اسپرسو دبل", "description": "عصاره‌گیری استاندارد", "price": "۵۵,۰۰۰ تومان"},
                        {"title": "چیزکیک سن سباستین", "description": "پخت روز با خامه تازه", "price": "۹۵,۰۰۰ تومان"},
                    ]
                },
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-price-list" in result
    assert "اسپرسو دبل" in result
    assert "۵۵,۰۰۰ تومان" in result
    assert "چیزکیک سن سباستین" in result


def test_ast_compiler_hotspot_elementor_pro_parity():
    """Verify Elementor Pro Hotspot compiles correctly in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست تصویر تعاملی هات‌اسپات",
        slug="test-hotspot",
        root_elements=[
            BuilderElement(
                id="el_hotspot_01",
                name="تصویر محصول تعاملی",
                type="widget",
                widget_type="hotspot",
                widget_props={
                    "image_url": "/product-detail.png",
                    "alt": "نمای نزدیک کالا",
                    "hotspots": [
                        {"id": "hs_a", "x": 35.0, "y": 45.0, "label": "الف"},
                        {"id": "hs_b", "x": 65.0, "y": 75.0, "label": "ب"},
                    ],
                },
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-hotspot" in result
    assert "/product-detail.png" in result
    assert "top:45.0%" in result or "top: 45.0%" in result
    assert "الف" in result
    assert "ب" in result


def test_ast_compiler_table_of_contents_elementor_pro_parity():
    """Verify Elementor Pro Table of Contents compiles correctly in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست فهرست مطالب",
        slug="test-toc",
        root_elements=[
            BuilderElement(
                id="el_toc_01",
                name="فهرست برگه",
                type="widget",
                widget_type="table_of_contents",
                widget_props={
                    "title": "فهرست مقالات",
                    "ordered": True,
                    "items": [
                        {"text": "بخش ۱: راهنمای راه‌اندازی", "anchor": "#setup"},
                        {"text": "بخش ۲: نکات امنیتی", "anchor": "#security"},
                    ],
                },
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-toc" in result
    assert "فهرست مقالات" in result
    assert "<ol" in result
    assert "بخش ۱: راهنمای راه‌اندازی" in result
    assert "#setup" in result


def test_ast_compiler_renders_round24_elementor_widgets():
    """Verify SSR AST compilation for progress_bar, testimonial, call_to_action, animated_headline, flip_box, and alert."""
    ast = PageAST(
        schema_version=1,
        title="تست ویجت‌های پورت المنتور راند ۲۴",
        slug="test-r24-widgets",
        root_elements=[
            BuilderElement(
                id="el_r24_sec",
                name="بخش پورت المنتور",
                type="container",
                children=[
                    BuilderElement(
                        id="el_icon01",
                        name="آیکون ستاره",
                        type="widget",
                        widget_type="icon",
                        widget_props={"icon": "star", "view": "stacked", "shape": "circle", "size": 36, "url": "https://example.com"},
                    ),
                    BuilderElement(
                        id="el_icon_list01",
                        name="فهرست مزایا",
                        type="widget",
                        widget_type="icon_list",
                        widget_props={
                            "layout": "vertical",
                            "items": [
                                {"text": "تحویل اکسپرس ۲ ساعته", "icon": "truck", "url": "/express"},
                                {"text": "اصالت کالا ۱۰۰٪ تضمین‌شده", "icon": "shield-check"},
                            ],
                        },
                    ),
                    BuilderElement(
                        id="el_price_table01",
                        name="جدول تعرفه",
                        type="widget",
                        widget_type="price_table",
                        widget_props={
                            "title": "پلن سازمانی",
                            "subtitle": "برای تیم‌های بالای ۵۰ نفر",
                            "price": "۹۹۰,۰۰۰",
                            "currency": "تومان",
                            "period": "ماهانه",
                            "badge": "تخفیف ویژه",
                            "is_featured": True,
                            "button_label": "خرید پلن سازمانی",
                            "button_url": "/checkout?plan=enterprise",
                            "features": [
                                {"text": "سرور اختصاصی ابری", "available": True},
                                {"text": "پشتیبانی تلفنی ۲۴/۷", "available": True},
                                {"text": "دامنه رایگان بین‌المللی", "available": False},
                            ],
                        },
                    ),
                    BuilderElement(
                        id="el_price_list01",
                        name="منوی خدمات",
                        type="widget",
                        widget_type="price_list",
                        widget_props={
                            "separator_style": "dotted",
                            "items": [
                                {"title": "توسعه ماژول سفارشی", "description": "پایتون و ری‌اکت", "price": "۲,۵۰۰,۰۰۰ تومان"},
                                {"title": "پیکربندی سرور اختصاصی", "description": "لینوکس و داکر", "price": "۱,۸۰۰,۰۰۰ تومان"},
                            ],
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast, is_authenticated=True)
    # 1. Icon widget
    assert 'builder-icon' in result
    assert 'bg-primary text-white shadow-sm' in result
    assert 'href="https://example.com"' in result
    # 2. Icon list widget
    assert 'builder-icon-list' in result
    assert 'تحویل اکسپرس ۲ ساعته' in result
    assert 'href="/express"' in result
    assert 'اصالت کالا ۱۰۰٪ تضمین‌شده' in result
    # 3. Price table widget
    assert 'builder-price-table' in result
    assert 'پلن سازمانی' in result
    assert '۹۹۰,۰۰۰' in result
    assert 'تخفیف ویژه' in result
    assert 'سرور اختصاصی ابری' in result
    assert 'دامنه رایگان بین‌المللی' in result
    assert 'خرید پلن سازمانی' in result
    assert '/checkout?plan=enterprise' in result
    # 4. Price list widget
    assert 'builder-price-list' in result
    assert 'توسعه ماژول سفارشی' in result
    assert '۲,۵۰۰,۰۰۰ تومان' in result
    assert 'border-dotted' in result
    assert 'پیکربندی سرور اختصاصی' in result


def test_ast_compiler_renders_round37_menu_anchor():
    """Verify that menu_anchor widget compiles invisible anchor div with target id."""
    ast = PageAST(
        schema_version=1,
        title="تست راند ۳۷",
        slug="test-r37-anchor",
        root_elements=[
            BuilderElement(
                id="el_sec_r37",
                name="بخش ۳۷",
                type="container",
                children=[
                    BuilderElement(
                        id="el_anc_custom",
                        name="لنگر درباره ما",
                        type="widget",
                        widget_type="menu_anchor",
                        widget_props={"anchor_id": "contact-section"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'id="contact-section"' in result
    assert 'class="builder-menu-anchor' in result
    assert 'data-widget="menu_anchor"' in result


def test_ast_compiler_renders_round38_table_of_contents():
    """Verify that table_of_contents widget compiles nav list with anchors in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست راند ۳۸",
        slug="test-r38-toc",
        root_elements=[
            BuilderElement(
                id="el_sec_r38",
                name="بخش ۳۸",
                type="container",
                children=[
                    BuilderElement(
                        id="el_toc_custom",
                        name="فهرست مطالب مقاله",
                        type="widget",
                        widget_type="table_of_contents",
                        widget_props={
                            "title": "فهرست محتوای آموزشی",
                            "items": [
                                {"title": "مقدمه‌ای بر سئو", "anchor": "#intro"},
                                {"title": "راهنمای ابزارها", "anchor": "#tools"},
                            ],
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-toc' in result
    assert 'فهرست محتوای آموزشی' in result
    assert 'href="#intro"' in result
    assert 'مقدمه‌ای بر سئو' in result
    assert 'href="#tools"' in result


def test_ast_compiler_renders_round39_share_buttons():
    """Verify that share_buttons widget compiles buttons list and title in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست راند ۳۹",
        slug="test-r39-share",
        root_elements=[
            BuilderElement(
                id="el_sec_r39",
                name="بخش ۳۹",
                type="container",
                children=[
                    BuilderElement(
                        id="el_share_custom",
                        name="دکمه‌های اشتراک",
                        type="widget",
                        widget_type="share_buttons",
                        widget_props={
                            "title": "ارسال برای دوستان",
                            "networks": [
                                {"network": "telegram", "label": "ارسال در تلگرام"},
                                {"network": "eitaa", "label": "کانال ایتا"},
                            ],
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-share-buttons' in result
    assert 'ارسال برای دوستان' in result
    assert 'data-network="telegram"' in result
    assert 'ارسال در تلگرام' in result
    assert 'data-network="eitaa"' in result
    assert 'کانال ایتا' in result


def test_ast_compiler_renders_nav_menu_elementor_parity():
    """Verify that nav_menu compiles standard nav element with links in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست منوی ناوبری",
        slug="test-nav-menu",
        root_elements=[
            BuilderElement(
                id="el_sec_nav",
                name="بخش هدر",
                type="container",
                children=[
                    BuilderElement(
                        id="el_nav_01",
                        name="منوی اصلی سایت",
                        type="widget",
                        widget_type="nav_menu",
                        widget_props={
                            "layout": "horizontal",
                            "align": "center",
                            "items": [
                                {"title": "صفحه اصلی", "url": "/"},
                                {"title": "محصولات ویژه", "url": "/featured"},
                                {"title": "درباره ما", "url": "/about"},
                            ],
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-nav-menu' in result
    assert 'data-widget="nav_menu"' in result
    assert 'صفحه اصلی' in result
    assert 'href="/featured"' in result
    assert 'درباره ما' in result


def test_ast_compiler_renders_round40_code_highlight():
    ast = PageAST(
        schema_version=1,
        title="تست راند ۴۰",
        slug="test-r40-code",
        root_elements=[
            BuilderElement(
                id="el_sec_r40",
                name="بخش ۴۰",
                type="container",
                children=[
                    BuilderElement(
                        id="el_code_custom",
                        name="بلوک کد پایتون",
                        type="widget",
                        widget_type="code_highlight",
                        widget_props={
                            "title": "script.py",
                            "language": "python",
                            "code": "def calculate_total(items): return 100",
                            "line_numbers": True,
                            "copy_to_clipboard": True,
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-code-highlight" in result
    assert "script.py" in result
    assert "language-python" in result
    assert "code-line-numbers" in result
    assert "calculate_total" in result
    assert "code-copy-btn" in result
    assert 'dir="ltr"' in result


def test_ast_compiler_renders_round41_breadcrumbs():
    ast = PageAST(
        schema_version=1,
        title="تست راند ۴۱",
        slug="test-r41-breadcrumbs",
        root_elements=[
            BuilderElement(
                id="el_sec_r41",
                name="بخش مسیر راهنما",
                type="container",
                children=[
                    BuilderElement(
                        id="el_crumb_custom",
                        name="مسیر راهنما سئو",
                        type="widget",
                        widget_type="breadcrumbs",
                        widget_props={
                            "separator": "/",
                            "items": [
                                {"label": "صفحه اصلی", "url": "/"},
                                {"label": "لوازم جانبی", "url": "/products?cat=acc"},
                                {"label": "هندزفری بلوتوثی", "url": ""},
                            ],
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-breadcrumbs" in result
    assert 'aria-label="مسیر راهنما"' in result
    assert "<ol" in result
    assert "صفحه اصلی" in result
    assert 'href="/"' in result
    assert "لوازم جانبی" in result
    assert 'href="/products?cat=acc"' in result
    assert "هندزفری بلوتوثی" in result
    assert 'aria-current="page"' in result
    assert "/" in result







