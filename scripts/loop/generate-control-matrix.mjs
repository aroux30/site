#!/usr/bin/env node
/**
 * Generates the deterministic 360-degree Builder Control Matrix (.loop/builder_control_matrix.json)
 * Covering:
 * - 35 Widgets (10 Base, 13 Interactive/Form, 12 Storefront)
 * - 28 Preset Block Patterns
 * - 4 UI Systems (Toolbar, Layers Tree, Global Styles, Template Dialogs)
 */

import fs from 'node:fs';
import path from 'node:path';

const ROOT_DIR = process.cwd();

const BASE_WIDGETS = [
  { id: 'container', name: 'کانتینر (Container)' },
  { id: 'section', name: 'بخش کامل (Section)' },
  { id: 'columns', name: 'چند ستونه (Columns)' },
  { id: 'heading', name: 'سربرگ و تیتر (Heading)' },
  { id: 'paragraph', name: 'پاراگراف (Paragraph)' },
  { id: 'text', name: 'متن ساده (Text)' },
  { id: 'image', name: 'تصویر (Image)' },
  { id: 'button', name: 'دکمه (Button)' },
  { id: 'spacer', name: 'فاصله‌ساز (Spacer)' },
  { id: 'divider', name: 'جداکننده (Divider)' },
];

const INTERACTIVE_WIDGETS = [
  { id: 'table', name: 'جدول اطلاعات (Table)' },
  { id: 'form_container', name: 'فرم‌ساز (Form Container)' },
  { id: 'form_input', name: 'فیلد ورودی متن (Input)' },
  { id: 'form_textarea', name: 'فیلد متنی چندخطی (Textarea)' },
  { id: 'form_select', name: 'منوی انتخابی (Select)' },
  { id: 'form_checkbox', name: 'چک‌باکس (Checkbox)' },
  { id: 'form_radio', name: 'دکمه رادیویی (Radio)' },
  { id: 'accordion', name: 'آکاردئون پرسش‌وپاسخ (Accordion)' },
  { id: 'tabs', name: 'تب‌بندی محتوا (Tabs)' },
  { id: 'countdown', name: 'شمارشگر معکوس (Countdown)' },
  { id: 'video', name: 'ویدیو (Video / Aparat)' },
  { id: 'icon_box', name: 'جعبه آیکون (Icon Box)' },
  { id: 'social_links', name: 'شبکه‌های اجتماعی (Social Links)' },
];

const STOREFRONT_WIDGETS = [
  { id: 'product_card', name: 'کارت محصول تکی (Product Card)' },
  { id: 'product_grid', name: 'شبکه محصولات (Product Grid)' },
  { id: 'image_gallery', name: 'گالری تصاویر (Image Gallery)' },
  { id: 'star_rating', name: 'امتیاز ستاره‌ای (Star Rating)' },
  { id: 'review_histogram', name: 'هیستوگرام دیدگاه‌ها (Review Histogram)' },
  { id: 'recently_viewed', name: 'مشاهده‌شده‌های اخیر (Recently Viewed)' },
  { id: 'mega_menu', name: 'مگامنو دسته‌بندی (Mega Menu)' },
  { id: 'product_price', name: 'قیمت محصول (Product Price)' },
  { id: 'product_variants', name: 'متغیرهای محصول (Product Variants)' },
  { id: 'add_to_cart', name: 'دکمه افزودن به سبد (Add to Cart)' },
  { id: 'mini_cart', name: 'مینی کارت شناور (Mini Cart)' },
  { id: 'cart_summary', name: 'خلاصه سفارش سبد (Cart Summary)' },
];

const PATTERNS = [
  'hero-banner', 'feature-grid', 'product-showcase-cta', 'testimonials',
  'faq-accordion', 'image-text', 'countdown-offer', 'star-rating-display',
  'review-histogram', 'product-card-grid', 'text-marquee', 'stats-counter',
  'image-gallery-showcase', 'discount-badge-banner', 'mega-menu-categories',
  'pricing-table', 'price-list', 'icon-box-grid', 'author-bio', 'pull-quote',
  'support-callout', 'comparison-table', 'process-steps', 'lead-capture-form',
  'alert-banner', 'floating-contact-bar', 'brand-logo-carousel', 'product-highlights'
];

const SYSTEMS = [
  { id: 'builder_toolbar', name: 'نوار ابزار اصلی (Builder Toolbar)' },
  { id: 'layers_tree', name: 'درخت ناوبری لایه‌ها (Layers Tree / Navigator)' },
  { id: 'global_styles_dialog', name: 'تنظیمات سراسری استایل (Global Styles)' },
  { id: 'template_dialogs', name: 'دیالوگ‌های ذخیره و درج قالب (Template Dialogs)' },
];

function createDefaultTabEntry(tabName, controls = []) {
  return {
    tab: tabName,
    controls,
    status: 'pending',
    signals: {
      s1_state: false,
      s2_dom: false,
      s3_computed_style: false,
      s4_pixel_diff: false,
      s5_persistence_ssr: false,
    },
    notes: '',
  };
}

const matrix = {
  version: '2.0.0',
  generated_at: new Date().toISOString(),
  target_standard: 'BUILDER_ELITE_V2_100PCT_VERIFIED',
  total_items: BASE_WIDGETS.length + INTERACTIVE_WIDGETS.length + STOREFRONT_WIDGETS.length + PATTERNS.length + SYSTEMS.length,
  stats: {
    widgets_base: BASE_WIDGETS.length,
    widgets_interactive: INTERACTIVE_WIDGETS.length,
    widgets_storefront: STOREFRONT_WIDGETS.length,
    patterns: PATTERNS.length,
    ui_systems: SYSTEMS.length,
    passed_items: 0,
    pending_items: 0,
  },
  rows: [],
};

// 1. Add Widgets
function addWidgets(list, category) {
  for (const w of list) {
    matrix.rows.push({
      id: `widget_${w.id}`,
      key: w.id,
      name: w.name,
      type: 'widget',
      category,
      overall_status: 'pending',
      tabs: {
        content: createDefaultTabEntry('content', ['main_props', 'dynamic_binding', 'alignment']),
        style: createDefaultTabEntry('style', ['typography', 'colors', 'borders', 'spacing', 'dimensions']),
        advanced: createDefaultTabEntry('advanced', [
          'margins_padding', 'z_index', 'position', 'custom_css_class',
          'custom_attributes', 'motion_effects', 'responsive_visibility', 'auth_visibility'
        ]),
      },
    });
  }
}

addWidgets(BASE_WIDGETS, 'basic');
addWidgets(INTERACTIVE_WIDGETS, 'interactive_form');
addWidgets(STOREFRONT_WIDGETS, 'storefront');

// 2. Add Patterns
for (const pSlug of PATTERNS) {
  matrix.rows.push({
    id: `pattern_${pSlug}`,
    key: pSlug,
    name: `الگوی آماده: ${pSlug}`,
    type: 'pattern',
    category: 'preset_pattern',
    overall_status: 'pending',
    tabs: {
      content: createDefaultTabEntry('content', ['pattern_insertion', 'ast_structure', 'rtl_alignment']),
      style: createDefaultTabEntry('style', ['theme_tokens', 'contrast', 'typography_inheritance']),
      advanced: createDefaultTabEntry('advanced', ['nested_containers', 'responsive_layout', 'ssr_parity']),
    },
  });
}

// 3. Add UI Systems
for (const sys of SYSTEMS) {
  matrix.rows.push({
    id: `system_${sys.id}`,
    key: sys.id,
    name: sys.name,
    type: 'system',
    category: 'ui_system',
    overall_status: 'pending',
    tabs: {
      content: createDefaultTabEntry('content', ['actions', 'keyboard_shortcuts']),
      style: createDefaultTabEntry('style', ['dark_mode', 'fullscreen_layout', 'rtl_direction']),
      advanced: createDefaultTabEntry('advanced', ['undo_redo_history', 'autosave_sync', 'dnd_kit_reorder']),
    },
  });
}

matrix.stats.pending_items = matrix.rows.length;

const outPath = path.join(ROOT_DIR, '.loop', 'builder_control_matrix.json');
fs.writeFileSync(outPath, JSON.stringify(matrix, null, 2), 'utf8');

console.log(`Generated Builder Control Matrix with ${matrix.rows.length} rows at ${outPath}`);
