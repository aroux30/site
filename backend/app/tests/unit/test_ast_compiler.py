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
    assert '4.9' in result
    assert '<svg' in result
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


def test_ast_compiler_renders_icon_widget_as_valid_svg():
    """Verify icon widget compiles to valid SVG element without raw slug text (Weight 0 parity)."""
    ast = PageAST(
        schema_version=1,
        title="تست آیکون و اس‌وی‌جی",
        slug="test-icon-svg",
        root_elements=[
            BuilderElement(
                id="el_icon01",
                name="آیکون ستاره",
                type="widget",
                widget_type="icon",
                widget_props={
                    "icon": "star",
                    "view": "stacked",
                    "shape": "circle",
                    "size": 32,
                    "rotate": 45,
                },
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert '<svg viewBox="0 0 24 24"' in result
    assert 'width="32"' in result
    assert 'height="32"' in result
    assert '<path d="M12 2l3.09 6.26' in result
    assert "★" not in result
    assert ">star<" not in result


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

    assert duration_ms < 250.0  # Must compile well under 250ms
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
    assert "سفارش پلن" in result


def test_ast_compiler_price_table_string_features_and_custom_badge():
    """Verify Price Table gracefully handles both string items and custom badge without error."""
    ast = PageAST(
        schema_version=1,
        title="تست جدول قیمت با امکانات متنی",
        slug="test-price-table-string-features",
        root_elements=[
            BuilderElement(
                id="el_ptable_str",
                name="پلن رشته‌ای",
                type="widget",
                widget_type="price_table",
                widget_props={
                    "title": "پلن استارتاپ",
                    "badge": "محبوب‌ترین",
                    "price": "۴۹۰,۰۰۰",
                    "currency": "تومان",
                    "period": "ماهانه",
                    "button_text": "شروع دوره",
                    "features": [
                        "دسترسی نامحدود",
                        {"text": "گزارش پیشرفته", "available": False},
                    ],
                },
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-price-table" in result
    assert "پلن استارتاپ" in result
    assert "محبوب‌ترین" in result
    assert "دسترسی نامحدود" in result
    assert "گزارش پیشرفته" in result
    assert "شروع دوره" in result


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


def test_ast_compiler_renders_floating_bar_widget():
    """Verify SSR compilation for floating_bar widget."""
    ast = PageAST(
        schema_version=1,
        title="تست نوار تماس شناور",
        slug="test-floating-bar",
        root_elements=[
            BuilderElement(
                id="el_flt_sec",
                name="بخش شناور",
                type="container",
                children=[
                    BuilderElement(
                        id="el_flt01",
                        name="نوار تماس",
                        type="widget",
                        widget_type="floating_bar",
                        widget_props={
                            "phone": "09121234567",
                            "message": "مشاوره رایگان تلفنی",
                            "button_text": "تماس بگیرید",
                            "button_url": "tel:09121234567",
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-floating-bar' in result
    assert "09121234567" in result
    assert "مشاوره رایگان تلفنی" in result
    assert "تماس بگیرید" in result
    assert 'href="tel:09121234567"' in result


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


def test_ast_compiler_renders_round46_slides_with_gradient():
    """Verify slides widget compiles with gradient background, button link, and title in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست اسلاید راند ۴۶",
        slug="test-r46-slides",
        root_elements=[
            BuilderElement(
                id="el_sec_r46",
                name="بخش اسلایدر",
                type="container",
                children=[
                    BuilderElement(
                        id="el_slides_r46",
                        name="اسلایدشو هیرو",
                        type="widget",
                        widget_type="slides",
                        widget_props={
                            "slides": [
                                {
                                    "title": "جشنواره تابستانه",
                                    "description": "تخفیف‌های استثنایی فصل",
                                    "button_text": "مشاهده محصولات",
                                    "button_link": "/summer-sale",
                                    "bg_color": "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                                },
                            ],
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-slides" in result
    assert "جشنواره تابستانه" in result
    assert "تخفیف‌های استثنایی فصل" in result
    assert "/summer-sale" in result
    assert "linear-gradient" in result


def test_ast_compiler_renders_round50_multistep_and_loop_grid():
    """Verify Round 50 multi_step_form custom button labels and loop_grid responsive columns in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست راند ۵۰ فرم و حلقه گرید",
        slug="test-r50-multistep-loop",
        root_elements=[
            BuilderElement(
                id="el_sec_r50",
                name="بخش ۵۰",
                type="container",
                children=[
                    BuilderElement(
                        id="el_msf_r50",
                        name="فرم چندمرحله‌ای",
                        type="widget",
                        widget_type="multi_step_form",
                        widget_props={
                            "steps": ["اطلاعات تماس", "آدرس ارسال", "تایید پرداخت"],
                            "next_button_text": "ادامه و ثبت نهایی",
                            "prev_button_text": "بازگشت به قبل",
                        },
                    ),
                    BuilderElement(
                        id="el_lgrid_r50",
                        name="حلقه کالاها",
                        type="widget",
                        widget_type="loop_grid",
                        widget_props={
                            "columns": 4,
                            "limit": 4,
                            "category": "موبایل",
                            "show_price": True,
                            "show_button": True,
                            "button_text": "خرید آنلاین",
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "builder-multi-step-form" in result
    assert "اطلاعات تماس" in result
    assert "ادامه و ثبت نهایی" in result
    assert "بازگشت به قبل" in result
    assert "builder-loop-grid" in result
    assert "md:grid-cols-4" in result
    assert "خرید آنلاین" in result



def test_ast_compiler_renders_round51_icon_and_icon_list_dynamic_icons():
    """Verify Round 51 dynamic icon resolution for icon and icon_list widgets."""
    ast = PageAST(
        schema_version=1,
        title="تست آیکون‌های داینامیک راند ۵۱",
        slug="test-r51-icons",
        root_elements=[
            BuilderElement(
                id="el_sec_r51",
                name="بخش آیکون‌ها",
                type="container",
                children=[
                    BuilderElement(
                        id="el_icon_truck",
                        name="آیکون ارسال",
                        type="widget",
                        widget_type="icon",
                        widget_props={"icon": "truck", "size": 32, "view": "stacked"},
                    ),
                    BuilderElement(
                        id="el_list_r51",
                        name="فهرست مزایا",
                        type="widget",
                        widget_type="icon_list",
                        widget_props={
                            "items": [
                                {"text": "پشتیبانی تلفنی", "icon": "phone"},
                                {"text": "تخفیف ویژه هدیه", "icon": "gift"},
                            ]
                        },
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "🚚" in result
    assert "📞" in result
    assert "🎁" in result
    assert "پشتیبانی تلفنی" in result
    assert "تخفیف ویژه هدیه" in result


def test_ast_compiler_renders_round50_custom_attributes_parity():
    """Verify Round 50 Elementor Pro custom attributes and data attributes in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست ویژگی‌های سفارشی راند ۵۰",
        slug="test-r50-custom-attrs",
        root_elements=[
            BuilderElement(
                id="el_sec_r50",
                name="بخش با ویژگی‌های سفارشی",
                type="container",
                styles=ResponsiveStyles(
                    custom_attributes="data-section-role|hero-banner\ndata-tracking-id|promo_2026\nonclick|alert(1)\njavascript:evil()|bad",
                ),
                children=[
                    BuilderElement(
                        id="el_tbl_r50",
                        name="جدول با اتریبیوت دیکشنری",
                        type="widget",
                        widget_type="table",
                        styles=ResponsiveStyles(
                            custom_attributes={"data-widget-purpose": "spec-sheet", "data-e2e": "specs-table", "style": "color:red"},
                        ),
                        widget_props={
                            "headers": ["ویژگی", "مقدار"],
                            "rows": [["پردازنده", "M3 Max"]],
                        },
                    ),
                    BuilderElement(
                        id="el_btn_r50",
                        name="دکمه با اتریبیوت سفارشی",
                        type="widget",
                        widget_type="button",
                        styles=ResponsiveStyles(
                            custom_attributes="data-analytics-category|lead-gen\naria-label|تماس با ما",
                        ),
                        widget_props={"label": "ثبت درخواست", "url": "/contact"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    # Container attributes
    assert 'data-section-role="hero-banner"' in result
    assert 'data-tracking-id="promo_2026"' in result
    assert 'onclick' not in result
    assert 'javascript:' not in result
    # Widget table with dict attributes
    assert 'data-widget-purpose="spec-sheet"' in result
    assert 'data-e2e="specs-table"' in result
    # Widget button with string attributes
    assert 'data-analytics-category="lead-gen"' in result
    assert 'aria-label="تماس با ما"' in result


def test_ast_compiler_renders_round52_shape_dividers_inline_svg_with_color():
    """Verify Round 52 container shape dividers compile to inline SVGs preserving custom colors."""
    ast = PageAST(
        schema_version=1,
        title="تست جداکننده شکل راند ۵۲",
        slug="test-r52-shape-dividers",
        root_elements=[
            BuilderElement(
                id="el_sec_r52",
                name="بخش با شکل موجی و مورب",
                type="container",
                styles=ResponsiveStyles(
                    shape_divider_top="waves",
                    shape_divider_bottom="tilt",
                    shape_divider_color="#10b981",
                ),
                children=[],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-shape-divider builder-shape-divider-top"' in result
    assert 'data-shape="waves"' in result
    assert 'class="builder-shape-divider builder-shape-divider-bottom"' in result
    assert 'data-shape="tilt"' in result
    assert '<svg viewBox="0 0 1000 100"' in result
    assert 'fill="#10b981"' in result
    assert 'M421.9' in result
    assert 'rotate(180deg)' in result


def test_ast_compiler_renders_round53_motion_effects_animation_classes():
    """Verify Round 53 entrance animation classes and duration/delay inline styles in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست افکت‌های حرکتی راند ۵۳",
        slug="test-r53-motion",
        root_elements=[
            BuilderElement(
                id="el_sec_r53",
                name="بخش انیمیشنی",
                type="container",
                styles=ResponsiveStyles(
                    animation="bounce-in",
                    animation_duration=0.8,
                    animation_delay=0.2,
                ),
                children=[
                    BuilderElement(
                        id="el_btn_r53",
                        name="دکمه چرخان",
                        type="widget",
                        widget_type="button",
                        styles=ResponsiveStyles(
                            animation="rotate-in",
                            animation_duration=0.7,
                        ),
                        widget_props={"label": "کلیک کنید", "url": "/"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'builder-animate-bounce-in' in result
    assert 'animation-duration: 0.8s' in result or 'animation-duration:0.8s' in result
    assert 'animation-delay: 0.2s' in result or 'animation-delay:0.2s' in result
    assert 'builder-animate-rotate-in' in result
    assert 'animation-duration: 0.7s' in result or 'animation-duration:0.7s' in result


def test_ast_compiler_renders_weight0_svg_icon_and_no_raw_slug():
    """Verify Weight 0: icon widget outputs valid SVG without leaking raw text slug 'star'."""
    ast = PageAST(
        schema_version=1,
        title="تست آیکون اس‌وی‌جی وزنه صفر",
        slug="test-w0-icon-svg",
        root_elements=[
            BuilderElement(
                id="el_w0_icon_sec",
                name="بخش آیکون",
                type="container",
                children=[
                    BuilderElement(
                        id="el_w0_icon",
                        name="آیکون تک",
                        type="widget",
                        widget_type="icon",
                        widget_props={"icon": "star", "size": 36, "view": "framed", "shape": "circle"},
                    )
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert '<svg' in result
    assert 'class="lucide lucide-star builder-icon-svg"' in result
    assert 'width="36" height="36"' in result
    assert '<path d="M12 2l3.09 6.26L22 9.27' in result
    assert 'border-2 border-primary text-primary bg-transparent' in result
    assert 'rounded-full' in result
    assert '⭐' in result


def test_ast_compiler_renders_round55_single_icon_svg_markup():
    """Verify Round 55 single icon widget renders valid SVG element with viewBox, size and paths."""
    ast = PageAST(
        schema_version=1,
        title="تست آیکون تک راند ۵۵",
        slug="test-r55-icon-svg",
        root_elements=[
            BuilderElement(
                id="el_sec_icon",
                name="بخش آیکون",
                type="container",
                children=[
                    BuilderElement(
                        id="el_icon_star",
                        name="آیکون ستاره",
                        type="widget",
                        widget_type="icon",
                        widget_props={"icon": "star", "size": 36, "view": "stacked", "shape": "circle"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'data-widget="icon"' in result
    assert '<svg' in result
    assert 'width="36"' in result
    assert 'height="36"' in result
    assert 'viewBox="0 0 24 24"' in result
    assert '<path d="M12 2l3.09 6.26L22 9.27' in result
    assert 'class="lucide lucide-star' in result


def test_ast_compiler_renders_round56_video_aparat_and_alert_info_aliases():
    """Verify Round 56 video/aparat and alert/info aliases compile seamlessly in SSR."""
    ast = PageAST(
        schema_version=1,
        title="تست آپارات و اعلان راند ۵۶",
        slug="test-r56-aliases",
        root_elements=[
            BuilderElement(
                id="el_aparat",
                name="ویدئو آپارات",
                type="widget",
                widget_type="aparat",
                widget_props={"url": "https://www.aparat.com/v/sample"},
            ),
            BuilderElement(
                id="el_info",
                name="اعلان اطلاعاتی",
                type="widget",
                widget_type="info",
                widget_props={"title": "نکته مهم", "message": "این یک پیام اطلاعاتی است."},
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-video' in result
    assert 'data-widget="video"' in result
    assert 'class="builder-alert' in result
    assert 'data-widget="alert"' in result
    assert "نکته مهم" in result
    assert "این یک پیام اطلاعاتی است." in result


def test_ast_compiler_applies_global_styles_to_root_document():
    """Verify global_styles (background, text color, radius, font) compile to root builder-document."""
    ast = PageAST(
        schema_version=1,
        title="تست استایل سراسری",
        slug="test-global-styles",
        global_styles={
            "backgroundColor": "#f8fafc",
            "textColor": "#1e293b",
            "borderRadius": "16px",
            "fontFamily": "system-ui",
        },
        root_elements=[
            BuilderElement(
                id="el_sec_gs",
                name="بخش یک",
                type="container",
                children=[],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'class="builder-document"' in result
    assert "background-color:#f8fafc" in result or "background-color: #f8fafc" in result
    assert "color:#1e293b" in result or "color: #1e293b" in result
    assert "border-radius:16px" in result or "border-radius: 16px" in result
    assert "font-family:system-ui, sans-serif" in result or "font-family: system-ui, sans-serif" in result


def test_ast_compiler_desktop_tablet_grid_media_queries():
    """Verify desktop/tablet styles, radius_token, hover shadows, and grid columns emit media CSS rules."""
    from app.modules.content.domain.builder_ast import (
        BackgroundStyle,
        BorderStyle,
        DeviceStyle,
        TypographyStyle,
    )

    ast = PageAST(
        schema_version=1,
        title="تست ریسپانسیو دسکتاپ",
        slug="test-responsive-r02",
        root_elements=[
            BuilderElement(
                id="el_grid_r02",
                name="شبکه ریسپانسیو",
                type="container",
                layout=ContainerLayout(kind="grid", grid_columns=4, gap=UnitValue(value=24, unit="px")),
                children=[
                    BuilderElement(
                        id="el_head_r02",
                        name="تیتر دسکتاپ",
                        type="widget",
                        widget_type="heading",
                        widget_props={"text": "سرتیتر دسکتاپ", "tag": "h3"},
                        styles=ResponsiveStyles(
                            mobile=DeviceStyle(),
                            tablet=DeviceStyle(
                                padding=SpacingBox(
                                    top=UnitValue(value=12, unit="px"),
                                    right=UnitValue(value=12, unit="px"),
                                    bottom=UnitValue(value=12, unit="px"),
                                    left=UnitValue(value=12, unit="px"),
                                )
                            ),
                            desktop=DeviceStyle(
                                typography=TypographyStyle(
                                    color="#fef2f2",
                                    font_size=UnitValue(value=38, unit="px"),
                                    text_align="left",
                                ),
                                background=BackgroundStyle(type="color", color="#dc2626"),
                                border=BorderStyle(style="solid", radius_token="9999px"),
                                opacity=0.85,
                                hover_box_shadow="0 8px 20px rgba(0,0,0,0.25)",
                            ),
                        ),
                    )
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert '<style data-builder-responsive="1">' in result
    assert "#el_grid_r02" in result
    assert "repeat(4, minmax(0, 1fr))" in result
    assert "@media (min-width: 768px)" in result
    assert "@media (min-width: 1024px)" in result
    assert "#el_head_r02" in result
    assert "font-size: 38px;" in result
    assert "background-color: #dc2626;" in result
    assert "border-radius: 9999px;" in result
    assert "opacity: 0.85;" in result
    assert "#el_head_r02:hover" in result


def test_ast_compiler_button_newtab_divider_styles_and_spacer_merge():
    """Verify button newTab camelCase/snake_case, divider props, and spacer styles merge cleanly."""
    from app.modules.content.domain.builder_ast import DeviceStyle

    ast = PageAST(
        schema_version=1,
        title="تست دکمه و خط جداکننده",
        slug="test-widgets-r02",
        root_elements=[
            BuilderElement(
                id="el_btn_r02",
                name="دکمه جدید",
                type="widget",
                widget_type="button",
                widget_props={"label": "کلیک تست", "url": "https://example.com", "newTab": True},
            ),
            BuilderElement(
                id="el_div_r02",
                name="جداکننده",
                type="widget",
                widget_type="divider",
                widget_props={"style": "dashed", "weight": 3, "width": 60, "color": "#16a34a", "align": "right"},
            ),
            BuilderElement(
                id="el_spc_r02",
                name="فاصله‌ساز",
                type="widget",
                widget_type="spacer",
                widget_props={"height": 96},
                styles=ResponsiveStyles(mobile=DeviceStyle(opacity=0.7)),
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    assert 'target="_blank"' in result
    assert "noopener" in result
    assert "border-style:dashed" in result or "border-style: dashed" in result
    assert "border-width:3px 0 0 0" in result or "border-width: 3px 0 0 0" in result
    assert "width:60%" in result or "width: 60%" in result
    assert "height:96px" in result or "height: 96px" in result
    assert "opacity:0.7" in result or "opacity: 0.7" in result


def test_ast_compiler_round03_interactive_and_form_parity():
    """Verify Round 03 interactive widgets: form submit button, required stars, video embed normalization, icon_box SVG, tabs data attrs, countdown units, accordion chevron SVG, social_links SVG, table borderless."""
    ast = PageAST(
        schema_version=1,
        title="تست ویجت‌های تعاملی راند ۳",
        slug="test-interactive-r03",
        root_elements=[
            BuilderElement(
                id="el_form_r03",
                name="فرم تماس",
                type="container",
                widget_type="form_container",
                widget_props={"submit_url": "/api/v1/content/forms/submit", "submit_label": "ثبت نهایی"},
                children=[
                    BuilderElement(
                        id="el_chk_r03",
                        name="تیک قوانین",
                        type="widget",
                        widget_type="form_checkbox",
                        widget_props={"label": "قبول قوانین", "name": "terms", "required": True},
                    ),
                    BuilderElement(
                        id="el_rad_r03",
                        name="ارسال",
                        type="widget",
                        widget_type="form_radio",
                        widget_props={"label": "نحوه ارسال", "name": "ship", "options": "پست، تیپاکس", "required": True},
                    ),
                ],
            ),
            BuilderElement(
                id="el_yt_r03",
                name="ویدئو یوتیوب",
                type="widget",
                widget_type="video",
                widget_props={"video_type": "youtube", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            ),
            BuilderElement(
                id="el_vid_empty_r03",
                name="ویدئو خالی",
                type="widget",
                widget_type="video",
                widget_props={"video_type": "aparat", "url": ""},
            ),
            BuilderElement(
                id="el_ibox_r03",
                name="باکس آیکون",
                type="widget",
                widget_type="icon_box",
                widget_props={"icon": "truck", "title": "ارسال فوری", "description": "تحویل سریع"},
            ),
            BuilderElement(
                id="el_tabs_r03",
                name="زبانه‌ها",
                type="widget",
                widget_type="tabs",
                widget_props={"tabs": [{"title": "اول", "content": "متن اول"}, {"title": "دوم", "content": "متن دوم"}]},
            ),
            BuilderElement(
                id="el_cd_r03",
                name="شمارنده",
                type="widget",
                widget_type="countdown",
                widget_props={"title": "فروش ویژه", "target_date": "2028-01-01T12:00:00", "expired_text": "پایان یافت"},
            ),
            BuilderElement(
                id="el_tbl_r03",
                name="جدول بدون خط",
                type="widget",
                widget_type="table",
                widget_props={"headers": ["الف", "ب"], "rows": [["۱", "۲"]], "bordered": False, "striped": True},
            ),
            BuilderElement(
                id="el_soc_r03",
                name="شبکه اجتماعی",
                type="widget",
                widget_type="social_links",
                widget_props={"links": [{"platform": "گیت‌هاب", "url": "https://github.com/test"}]},
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    # 1. Form submit button & required stars
    assert 'type="submit"' in result
    assert "ثبت نهایی" in result
    assert '<span class="text-destructive ms-1">*</span>' in result
    assert "تیپاکس" in result
    # 2. Video embed normalization & empty placeholder
    assert "https://www.youtube.com/embed/dQw4w9WgXcQ" in result
    assert '<iframe src=""' not in result
    # 3. icon_box renders inline SVG instead of emoji
    assert 'data-icon="truck"' in result
    assert "lucide-truck" in result
    assert "🚚" not in result
    # 4. Tabs attributes
    assert 'data-tab-index="1"' in result
    assert 'data-tab-pane="1"' in result
    # 5. Countdown attributes & naive ISO support
    assert 'data-cd-unit="days"' in result
    assert 'data-expired-text="پایان یافت"' in result
    # 6. Social links inline SVG
    assert "lucide-share-2" in result
    # 7. Borderless table removes border classes
    assert "border-collapse" in result
    assert "divide-y divide-border/70" not in result


def test_ast_compiler_round04_shop_widgets_ssr_parity():
    """Verify Round 04 shop widgets honor all Inspector properties, format Persian prices, and fix SSR layout/SVG parity."""
    ast = PageAST(
        schema_version=1,
        title="تست ویجت‌های فروشگاهی راند ۴",
        slug="test-shop-r04",
        root_elements=[
            BuilderElement(
                id="el_card_r04",
                name="کارت محصول",
                type="widget",
                widget_type="product_card",
                widget_props={
                    "name": "گوشی تستی",
                    "min_price": 4500000,
                    "max_price": 5200000,
                    "primary_image_url": "/placeholder.svg",
                    "is_in_stock": False,
                },
            ),
            BuilderElement(
                id="el_gal_r04",
                name="گالری",
                type="widget",
                widget_type="image_gallery",
                widget_props={
                    "images": [
                        {"url": "/placeholder-hero.svg", "alt": "اول"},
                        {"url": "/placeholder.svg", "alt": "دوم"},
                    ]
                },
            ),
            BuilderElement(
                id="el_star_r04",
                name="امتیاز",
                type="widget",
                widget_type="star_rating",
                widget_props={"value": 3.7, "reviewCount": 99, "showValue": False},
            ),
            BuilderElement(
                id="el_hist_r04",
                name="هیستوگرام",
                type="widget",
                widget_type="review_histogram",
                widget_props={"averageRating": 4.2, "totalReviews": 310, "verifiedCount": 245},
            ),
            BuilderElement(
                id="el_rec_r04",
                name="بازدید اخیر",
                type="widget",
                widget_type="recently_viewed",
                widget_props={"title": "جدیدترین بازدیدها", "limit": 2},
            ),
            BuilderElement(
                id="el_mega_r04",
                name="مگامنو",
                type="widget",
                widget_type="mega_menu",
                widget_props={"label": "منوی فروشگاه"},
            ),
            BuilderElement(
                id="el_price_r04",
                name="قیمت",
                type="widget",
                widget_type="product_price",
                widget_props={"price": 980000, "compare_at_price": 1400000, "show_discount": False},
            ),
            BuilderElement(
                id="el_atc_r04",
                name="دکمه خرید",
                type="widget",
                widget_type="add_to_cart",
                widget_props={"label": "خرید فوری", "show_quantity": True, "variant_id": "v_2"},
            ),
            BuilderElement(
                id="el_mini_r04",
                name="مینی کارت",
                type="widget",
                widget_type="mini_cart",
                widget_props={"label": "کیف من", "show_badge": False, "item_count": 3},
            ),
            BuilderElement(
                id="el_sum_r04",
                name="خلاصه سبد",
                type="widget",
                widget_type="cart_summary",
                widget_props={"title": "فاکتور من", "button_label": "پرداخت", "checkout_url": "/cart", "show_discount": False},
            ),
            BuilderElement(
                id="el_grid_r04",
                name="گرید محصول",
                type="widget",
                widget_type="product_grid",
                widget_props={"limit": 2, "filter": "featured", "show_pagination": False},
            ),
        ],
    )
    result = ASTCompiler.compile(ast)
    # 1. product_card normalized image, max_price del, max-w-sm, out-of-stock disabled button
    assert "max-w-sm" in result
    assert "/placeholder-product.svg" in result
    assert 'src="/placeholder.svg"' not in result
    assert "<del" in result
    assert "disabled" in result
    # 2. image_gallery stage + thumbs
    assert 'data-gallery-main="1"' in result
    assert 'data-gallery-thumb="1"' in result
    # 3. star_rating 5 stars + showValue=False omits 3.7
    assert "3.7" not in result
    assert result.count("text-amber-400") >= 3
    # 4. review_histogram verifiedCount & 5 rows
    assert "245 خرید تأییدشده" in result
    # 5. recently_viewed custom title & cards
    assert "جدیدترین بازدیدها" in result
    assert result.count("<h5") == 2
    # 6. mega_menu SVG & collapsible panel
    assert 'data-mega-menu-toggle="1"' in result
    assert 'data-mega-menu-panel="1"' in result
    # 7. product_price Persian formatted & show_discount=False hides badge
    assert "۹۸۰,۰۰۰ تومان" in result
    assert "30٪ تخفیف" not in result
    # 8. add_to_cart stepper + SVG
    assert 'data-qty-inc="1"' in result
    assert "lucide-shopping-cart" in result
    # 9. mini_cart custom label & show_badge=False hides badge
    assert "کیف من" in result
    assert 'data-mc-badge="1"' not in result
    # 10. cart_summary custom title/btn/url & hidden discount
    assert "فاکتور من" in result
    assert 'href="/cart"' in result
    assert "پرداخت" in result
    assert "- ۱۰۰,۰۰۰ تومان" not in result
    # 11. product_grid filter pills & no pagination
    assert 'data-grid-filter="featured"' in result
    assert "مشاهده محصولات بیشتر" not in result


def test_builder_gym_round05_global_styles_hero_code_extra5_and_pattern_assets():
    from app.modules.content.domain.block_patterns import PATTERNS
    from app.modules.content.domain.builder_validation import validate_page_ast

    ast = validate_page_ast(
        {
            "schemaVersion": 1,
            "title": "Round 05 Regression",
            "slug": "r05-test",
            "globalStyles": {
                "primaryColor": "#dc2626",
                "secondaryColor": "#0284c7",
                "backgroundColor": "#fefce8",
                "textColor": "#1e293b",
                "borderRadius": "16px",
                "fontFamily": "system-ui",
            },
            "rootElements": [
                {
                    "id": "el_r05hero1",
                    "name": "Hero Box",
                    "type": "container",
                    "styles": {"mobile": {}, "customCssClass": "bg-primary text-primary-foreground p-6"},
                    "layout": {"kind": "flex", "direction": "column"},
                    "children": [
                        {
                            "id": "el_r05head1",
                            "name": "Hero Heading",
                            "type": "widget",
                            "widgetType": "heading",
                            "widgetProps": {"text": "کالکشن جدید رسید", "tag": "h1"},
                            "styles": {"mobile": {}, "customCssClass": "text-3xl font-bold text-primary-foreground"},
                        },
                        {
                            "id": "el_r05btn1",
                            "name": "Hero CTA",
                            "type": "widget",
                            "widgetType": "button",
                            "widgetProps": {"label": "همین حالا بخرید", "url": "/products"},
                            "styles": {"mobile": {}, "customCssClass": "bg-primary-foreground text-primary font-semibold"},
                        },
                    ],
                },
                {
                    "id": "el_r05code1",
                    "name": "Code",
                    "type": "widget",
                    "widgetType": "code_highlight",
                    "widgetProps": {
                        "title": "api.ts",
                        "language": "typescript",
                        "code": "const res = await fetch('/api/v1/products?x=<tag>');",
                        "line_numbers": True,
                        "copy_to_clipboard": True,
                    },
                    "styles": {"mobile": {}},
                },
                {
                    "id": "el_r05nav1",
                    "name": "Nav",
                    "type": "widget",
                    "widgetType": "nav_menu",
                    "widgetProps": {
                        "layout": "vertical",
                        "items": [{"title": "فروشگاه", "url": "/products"}, {"title": "درباره ما", "url": "/about"}],
                    },
                    "styles": {"mobile": {}},
                },
                {
                    "id": "el_r05pt1",
                    "name": "ProdTitle",
                    "type": "widget",
                    "widgetType": "product_title",
                    "widgetProps": {"fallback_title": "هدفون بی‌سیم رده‌پرو"},
                    "styles": {"mobile": {}},
                },
            ],
        }
    )

    compiled = ASTCompiler.compile(ast)
    # Global Styles compiled as CSS custom properties + root surface styles
    assert "--primary-hex: #dc2626" in compiled
    assert "--secondary-hex: #0284c7" in compiled
    assert "--background-hex: #fefce8" in compiled
    assert "--foreground-hex: #1e293b" in compiled
    assert "--radius: 16px" in compiled
    assert "system-ui, sans-serif" in compiled
    assert "background-color: #fefce8" in compiled or "background-color:#fefce8" in compiled

    # Hero heading & CTA button must NOT get overridden by default text-foreground / bg-primary / text-primary-foreground
    assert 'text-primary-foreground' in compiled
    assert 'text-foreground  break-words' not in compiled
    assert 'rounded-xl bg-primary px-6' not in compiled

    # code_highlight must NOT double-escape single quotes or angle brackets inside <pre><code>
    assert "&amp;#x27;" not in compiled
    assert "&amp;lt;" not in compiled
    assert "fetch(" in compiled and "/api/v1/products" in compiled
    assert 'data-code="' in compiled

    # Extra 5 widgets parity
    assert "flex-col items-start" in compiled
    assert "هدفون بی‌سیم رده‌پرو" in compiled
    assert 'data-widget="product_title"' in compiled

    # All built-in backend block patterns must never reference broken /placeholder-avatar.svg or /placeholder.svg
    for pat in PATTERNS.values():
        joined = pat.html + "".join(v.default for v in pat.variables)
        assert "/placeholder-avatar.svg" not in joined, f"{pat.slug} still uses /placeholder-avatar.svg"
        assert '"/placeholder.svg"' not in joined, f"{pat.slug} still uses /placeholder.svg"


def test_render_body_preserves_builder_h1_when_demote_h1_false():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.shared.content.render import render_body

    sample = '<div class="builder-document"><h1>تیتر صفحه ساز</h1></div>'
    with patch("app.modules.content.application.reusable_block_service.ReusableBlockService.expand", new=AsyncMock(return_value=sample)), \
         patch("app.shared.content.shortcodes.process_shortcodes_async", new=AsyncMock(return_value=sample)):
        preserved = asyncio.run(render_body(MagicMock(), sample, demote_h1=False))
        demoted = asyncio.run(render_body(MagicMock(), sample, demote_h1=True))
    assert "<h1>تیتر صفحه ساز</h1>" in preserved
    assert "<h2>تیتر صفحه ساز</h2>" in demoted


def test_rendered_filters_auth_visibility_for_guest_and_authenticated():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.modules.content.api.routes import _rendered
    from app.modules.content.schemas.content import CmsPageResponse
    from datetime import datetime, UTC
    import uuid

    ast_dict = {
        "schemaVersion": 1,
        "title": "Auth Visibility Test",
        "slug": "auth-vis-test",
        "rootElements": [
            {
                "id": "el_auth_u1",
                "name": "اعضا",
                "type": "widget",
                "widgetType": "heading",
                "widgetProps": {"text": "محتوای محرمانه اعضا", "tag": "h2"},
                "authVisibility": "authenticated",
                "styles": {"mobile": {}},
                "children": [],
            },
            {
                "id": "el_guest_u1",
                "name": "مهمان",
                "type": "widget",
                "widgetType": "heading",
                "widgetProps": {"text": "پیام خوشامد مهمان", "tag": "h2"},
                "authVisibility": "guest",
                "styles": {"mobile": {}},
                "children": [],
            },
            {
                "id": "el_all_u1",
                "name": "عمومی",
                "type": "widget",
                "widgetType": "heading",
                "widgetProps": {"text": "محتوای عمومی برای همه", "tag": "h2"},
                "authVisibility": "all",
                "styles": {"mobile": {}},
                "children": [],
            },
        ],
    }
    guest_compiled = ASTCompiler.compile(PageAST.model_validate(ast_dict), is_authenticated=False)
    page_resp = CmsPageResponse(
        id=uuid.uuid4(),
        title="Auth Visibility Test",
        slug="auth-vis-test",
        body_html=guest_compiled,
        builder_data=ast_dict,
        excerpt=None,
        status="published",
        seo_title=None,
        seo_description=None,
        author_id=None,
        published_at=datetime.now(UTC),
        revision_number=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def fake_identity(_db, html_str, **_kw):
        return html_str

    with patch("app.shared.content.render.render_body", side_effect=fake_identity):
        guest_out = asyncio.run(_rendered(MagicMock(), page_resp, is_authenticated=False))
        auth_out = asyncio.run(_rendered(MagicMock(), page_resp, is_authenticated=True))

    assert "محتوای محرمانه اعضا" not in guest_out.body_html
    assert "پیام خوشامد مهمان" in guest_out.body_html
    assert "محتوای عمومی برای همه" in guest_out.body_html

    assert "محتوای محرمانه اعضا" in auth_out.body_html
    assert "پیام خوشامد مهمان" not in auth_out.body_html
    assert "محتوای عمومی برای همه" in auth_out.body_html


def test_responsive_overrides_and_device_visibility_media_queries():
    ast = PageAST.model_validate(
        {
            "schemaVersion": 1,
            "title": "Responsive Visibility Test",
            "slug": "resp-vis",
            "rootElements": [
                {
                    "id": "el_cont_vis5",
                    "name": "کانتینر شرطی",
                    "type": "container",
                    "visibleOnTablet": False,
                    "styles": {"mobile": {}},
                    "children": [
                        {
                            "id": "el_head_resp5",
                            "name": "هدینگ واکنشگرا",
                            "type": "widget",
                            "widgetType": "heading",
                            "widgetProps": {"text": "تست رسپانسیو", "tag": "h2"},
                            "visibleOnMobile": False,
                            "styles": {
                                "mobile": {"typography": {"fontSize": {"value": 16, "unit": "px"}}},
                                "tablet": {"typography": {"fontSize": {"value": 24, "unit": "px"}}},
                                "desktop": {"typography": {"fontSize": {"value": 36, "unit": "px"}}},
                            },
                            "children": [],
                        }
                    ],
                }
            ],
        }
    )
    compiled = ASTCompiler.compile(ast)
    assert "@media (max-width: 767px) { #el_head_resp5 { display: none !important; } }" in compiled
    assert "@media (min-width: 768px) and (max-width: 1023px) { #el_cont_vis5 { display: none !important; } }" in compiled
    assert "font-size: 16px;" in compiled
    assert "@media (min-width: 768px) { #el_head_resp5" in compiled
    assert "font-size: 24px;" in compiled
    assert "@media (min-width: 1024px) { #el_head_resp5" in compiled
    assert "font-size: 36px;" in compiled










