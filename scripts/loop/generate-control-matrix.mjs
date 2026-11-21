#!/usr/bin/env node
/**
 * scripts/loop/generate-control-matrix.mjs
 * Generates the deterministic 360-degree control matrix (.loop/builder_control_matrix.json)
 * covering 35 widgets, 28 block patterns, toolbar, layers tree, and studio dialogs.
 */

import fs from 'node:fs';
import path from 'node:path';

const projectRoot = process.cwd();

const WIDGETS_35 = [
  // 10 Basic
  { id: "w_container", type: "container", name: "کانتینر (Container)", category: "layout" },
  { id: "w_section", type: "section", name: "بخش کامل (Section)", category: "layout" },
  { id: "w_columns", type: "columns", name: "دو ستونه (2 Columns)", category: "layout" },
  { id: "w_heading", type: "heading", name: "سرتیتر (Heading)", category: "basic" },
  { id: "w_paragraph", type: "paragraph", name: "پاراگراف متن (Paragraph)", category: "basic" },
  { id: "w_text", type: "text", name: "ویرایشگر متن (Text Editor)", category: "basic" },
  { id: "w_image", type: "image", name: "تصویر (Image)", category: "basic" },
  { id: "w_button", type: "button", name: "دکمه (Button)", category: "basic" },
  { id: "w_spacer", type: "spacer", name: "فاصله‌ساز (Spacer)", category: "basic" },
  { id: "w_divider", type: "divider", name: "خط جداکننده (Divider)", category: "basic" },

  // 13 Interactive / Form
  { id: "w_table", type: "table", name: "جدول داده‌ها (Table)", category: "interactive" },
  { id: "w_form_container", type: "form_container", name: "فرم سازنده (Form Container)", category: "interactive" },
  { id: "w_form_input", type: "form_input", name: "فیلد ورودی متن (Input)", category: "interactive" },
  { id: "w_form_textarea", type: "form_textarea", name: "فیلد چندسطری پیام (Textarea)", category: "interactive" },
  { id: "w_form_select", type: "form_select", name: "منوی انتخابی آبشاری (Select)", category: "interactive" },
  { id: "w_form_checkbox", type: "form_checkbox", name: "چک‌باکس پذیرش (Checkbox)", category: "interactive" },
  { id: "w_form_radio", type: "form_radio", name: "گزینه‌های رادیویی (Radio Group)", category: "interactive" },
  { id: "w_accordion", type: "accordion", name: "آکاردئون / تاشو (Accordion)", category: "interactive" },
  { id: "w_tabs", type: "tabs", name: "تب‌های محتوا (Tabs)", category: "interactive" },
  { id: "w_countdown", type: "countdown", name: "شمارنده معکوس (Countdown)", category: "interactive" },
  { id: "w_video", type: "video", name: "ویدئو و رسانه (Video)", category: "interactive" },
  { id: "w_icon_box", type: "icon_box", name: "باکس آیکون و خدمات (Icon Box)", category: "interactive" },
  { id: "w_social_links", type: "social_links", name: "لینک‌های شبکه‌های اجتماعی (Social)", category: "interactive" },

  // 12 Store
  { id: "w_product_card", type: "product_card", name: "کارت محصول (Product Card)", category: "store" },
  { id: "w_product_grid", type: "product_grid", name: "ویترین محصولات (Product Grid)", category: "store" },
  { id: "w_image_gallery", type: "image_gallery", name: "گالری تصاویر کالا (Gallery)", category: "store" },
  { id: "w_star_rating", type: "star_rating", name: "امتیاز ستاره‌ای (Star Rating)", category: "store" },
  { id: "w_review_histogram", type: "review_histogram", name: "توزیع امتیاز نظرات (Review Histogram)", category: "store" },
  { id: "w_recently_viewed", type: "recently_viewed", name: "کالاهای اخیراً دیده‌شده (Recently Viewed)", category: "store" },
  { id: "w_mega_menu", type: "mega_menu", name: "مگامنوی دسته‌بندی‌ها (Mega Menu)", category: "store" },
  { id: "w_product_price", type: "product_price", name: "قیمت و تخفیف کالا (Product Price)", category: "store" },
  { id: "w_product_variants", type: "product_variants", name: "تنوع‌های رنگ و سایز (Variants)", category: "store" },
  { id: "w_add_to_cart", type: "add_to_cart", name: "دکمه افزودن به سبد (Add to Cart)", category: "store" },
  { id: "w_mini_cart", type: "mini_cart", name: "پیش‌نمایش سبد خرید (Mini Cart)", category: "store" },
  { id: "w_cart_summary", type: "cart_summary", name: "خلاصه سبد و تسویه (Cart Summary)", category: "store" },
];

const PATTERNS_28 = [
  { slug: "hero-banner", title: "بنر اصلی (هیرو)", category: "بنر و هیرو" },
  { slug: "feature-grid", title: "شبکه ویژگی‌ها", category: "محتوا" },
  { slug: "product-showcase-cta", title: "معرفی محصولات با دکمه", category: "محصولات" },
  { slug: "testimonials", title: "نظرات مشتریان", category: "محتوا" },
  { slug: "faq-accordion", title: "سوالات متداول با آکاردئون", category: "پشتیبانی" },
  { slug: "image-text", title: "تصویر و متن", category: "محتوا" },
  { slug: "countdown-offer", title: "فروش ویژه با شمارنده معکوس", category: "فروش و تخفیف" },
  { slug: "star-rating-display", title: "نمایش امتیاز ستاره‌ای", category: "محصولات" },
  { slug: "review-histogram", title: "نمودار توزیع امتیاز", category: "محصولات" },
  { slug: "product-card-grid", title: "ویترین ۳ تایی محصولات پرفروش", category: "محصولات" },
  { slug: "text-marquee", title: "متن چرخشی تبلیغاتی", category: "بنر و هیرو" },
  { slug: "stats-counter", title: "شمارنده آمار", category: "محتوا" },
  { slug: "image-gallery-showcase", title: "گالری ۴ تایی تصاویر محصول", category: "محصولات" },
  { slug: "discount-badge-banner", title: "نوار تخفیف با بَج درصد", category: "فروش و تخفیف" },
  { slug: "mega-menu-categories", title: "دسته‌بندی محصولات مگامنو", category: "ناوبری" },
  { slug: "pricing-table", title: "جدول ۳ تایی قیمت‌گذاری", category: "قیمت‌گذاری" },
  { slug: "price-list", title: "لیست قیمت خطی خدمات", category: "قیمت‌گذاری" },
  { slug: "icon-box-grid", title: "جعبه‌های مزایا و خدمات", category: "محتوا" },
  { slug: "author-bio", title: "کارت معرفی کارشناس / نویسنده", category: "محتوا" },
  { slug: "pull-quote", title: "نقل‌قول و پیام برجسته", category: "محتوا" },
  { slug: "support-callout", title: "کادر تماس و مشاوره قبل از خرید", category: "پشتیبانی" },
  { slug: "comparison-table", title: "جدول مقایسه مشخصات فنی", category: "محتوا" },
  { slug: "process-steps", title: "مراحل گام‌به‌گام خرید و تحویل", category: "محتوا" },
  { slug: "lead-capture-form", title: "فرم جذب سرنخ و مشاوره", category: "فرم‌ها" },
  { slug: "alert-banner", title: "نوار اعلان فوری و جشنواره", category: "بنر و هیرو" },
  { slug: "floating-contact-bar", title: "نوار ارتباطی چندکاناله", category: "پشتیبانی" },
  { slug: "brand-logo-carousel", title: "گرید برندها و شرکای تجاری", category: "بازاریابی" },
  { slug: "product-highlights", title: "ویژگی‌های برجسته کالا", category: "محصولات" },
];

const STUDIO_SURFACES = [
  { id: "surface_toolbar", name: "نوار ابزار اصلی استودیو (Builder Toolbar)", category: "studio" },
  { id: "surface_layers_tree", name: "درخت ناوبری لایه‌ها (Layers Tree / Navigator)", category: "studio" },
  { id: "surface_canvas_overlay", name: "لایه شناور اکشن و انتخاب بوم (Canvas Overlay)", category: "studio" },
  { id: "surface_global_styles", name: "دیالوگ تنظیمات استایل سراسری (Global Styles)", category: "dialog" },
  { id: "surface_save_template", name: "دیالوگ ذخیره قالب سکشن (Save Section Template)", category: "dialog" },
  { id: "surface_save_page_template", name: "دیالوگ ذخیره قالب برگه (Save Page Template)", category: "dialog" },
];

function buildWidgetMatrix() {
  return WIDGETS_35.map((w) => ({
    id: w.id,
    type: w.type,
    name: w.name,
    category: w.category,
    kind: "widget",
    tabs: {
      content: {
        controls: [
          "primary_text_or_data",
          "layout_or_source_config",
          "dynamic_props_repeater"
        ],
        status: "pending",
        signals: { state: false, dom: false, style: false, pixels: false, ssr: false }
      },
      style: {
        controls: [
          "typography_or_dimensions",
          "padding_margin_spacing",
          "background_color_gradient",
          "border_radius_shadow",
          "css_filters_overlay"
        ],
        status: "pending",
        signals: { state: false, dom: false, style: false, pixels: false, ssr: false }
      },
      advanced: {
        controls: [
          "entrance_animation",
          "responsive_device_visibility",
          "auth_conditional_visibility",
          "custom_css_class_id",
          "lock_hide_toggle"
        ],
        status: "pending",
        signals: { state: false, dom: false, style: false, pixels: false, ssr: false }
      }
    },
    overall_status: "pending"
  }));
}

function buildPatternsMatrix() {
  return PATTERNS_28.map((p, idx) => ({
    id: `pat_${p.slug}`,
    slug: p.slug,
    title: p.title,
    category: p.category,
    kind: "pattern",
    order: idx + 1,
    tabs: {
      content: {
        controls: ["palette_insertion", "slot_variables_replacement", "child_elements_creation"],
        status: "pending",
        signals: { state: false, dom: false, style: false, pixels: false, ssr: false }
      },
      style: {
        controls: ["responsive_tokens_render", "rtl_alignment_preservation", "contrast_and_spacing"],
        status: "pending",
        signals: { state: false, dom: false, style: false, pixels: false, ssr: false }
      },
      advanced: {
        controls: ["nested_container_navigation", "reorder_and_delete"],
        status: "pending",
        signals: { state: false, dom: false, style: false, pixels: false, ssr: false }
      }
    },
    overall_status: "pending"
  }));
}

function buildSurfacesMatrix() {
  return STUDIO_SURFACES.map((s) => ({
    id: s.id,
    name: s.name,
    category: s.category,
    kind: "surface",
    controls: ["mount_without_hydration_error", "keyboard_forwarding", "aria_and_contrast"],
    status: "pending",
    signals: { state: false, dom: false, style: false, pixels: false, ssr: false }
  }));
}

const matrix = {
  version: "2.0.0",
  lastUpdated: new Date().toISOString(),
  totalRows: WIDGETS_35.length + PATTERNS_28.length + STUDIO_SURFACES.length,
  counts: {
    widgets: WIDGETS_35.length,
    patterns: PATTERNS_28.length,
    surfaces: STUDIO_SURFACES.length,
  },
  summary: {
    passed: 0,
    pending: WIDGETS_35.length + PATTERNS_28.length + STUDIO_SURFACES.length,
    failed: 0,
  },
  widgets: buildWidgetMatrix(),
  patterns: buildPatternsMatrix(),
  surfaces: buildSurfacesMatrix(),
};

const outputPath = path.join(projectRoot, '.loop/builder_control_matrix.json');
fs.writeFileSync(outputPath, JSON.stringify(matrix, null, 2), 'utf8');

console.log(`>>> [control-matrix] Generated 360-degree control matrix at: ${outputPath}`);
console.log(`    Total tracked entries: ${matrix.totalRows} (Widgets: ${matrix.counts.widgets}, Patterns: ${matrix.counts.patterns}, Surfaces: ${matrix.counts.surfaces})`);
