import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "../..");

const WIDGETS_35 = [
  // 10 Basic Layout & Content
  { id: "container", name: "کانتینر (Container)", category: "layout" },
  { id: "section", name: "بخش سرتاسری (Section)", category: "layout" },
  { id: "columns", name: "دو ستونه (2 Columns)", category: "layout" },
  { id: "heading", name: "سرتیتر (Heading)", category: "basic" },
  { id: "paragraph", name: "پاراگراف متن (Paragraph)", category: "basic" },
  { id: "text", name: "متن آزاد (Text)", category: "basic" },
  { id: "image", name: "تصویر (Image)", category: "basic" },
  { id: "button", name: "دکمه اقدام (Button)", category: "basic" },
  { id: "spacer", name: "فاصله‌ساز (Spacer)", category: "basic" },
  { id: "divider", name: "خط جداکننده (Divider)", category: "basic" },

  // 13 Interactive & Form
  { id: "table", name: "جدول داده (Table)", category: "interactive" },
  { id: "form_container", name: "فرم سازنده (Form Container)", category: "form" },
  { id: "form_input", name: "فیلد ورودی متن (Input)", category: "form" },
  { id: "form_textarea", name: "متن چندخطی (Textarea)", category: "form" },
  { id: "form_select", name: "منوی کشویی (Select)", category: "form" },
  { id: "form_checkbox", name: "چک‌باکس فرم (Checkbox)", category: "form" },
  { id: "form_radio", name: "دکمه رادیویی (Radio Group)", category: "form" },
  { id: "accordion", name: "آکاردئون (Accordion)", category: "interactive" },
  { id: "tabs", name: "تب‌های محتوا (Tabs)", category: "interactive" },
  { id: "countdown", name: "شمارنده معکوس (Countdown)", category: "interactive" },
  { id: "video", name: "پخش‌کننده ویدئو (Video)", category: "interactive" },
  { id: "icon_box", name: "باکس آیکون و ویژگی (Icon Box)", category: "interactive" },
  { id: "social_links", name: "شبکه‌های اجتماعی (Social Links)", category: "interactive" },

  // 12 Store & Ecommerce
  { id: "product_card", name: "کارت محصول (Product Card)", category: "ecommerce" },
  { id: "product_grid", name: "ویترین محصولات (Product Grid)", category: "ecommerce" },
  { id: "image_gallery", name: "گالری تصاویر (Image Gallery)", category: "ecommerce" },
  { id: "star_rating", name: "امتیاز ستاره‌ای (Star Rating)", category: "ecommerce" },
  { id: "review_histogram", name: "نمودار نظرات (Review Histogram)", category: "ecommerce" },
  { id: "recently_viewed", name: "بازدیدهای اخیر (Recently Viewed)", category: "ecommerce" },
  { id: "mega_menu", name: "مگامنو (Mega Menu)", category: "ecommerce" },
  { id: "product_price", name: "قیمت محصول (Product Price)", category: "ecommerce" },
  { id: "product_variants", name: "تنوع محصول (Product Variants)", category: "ecommerce" },
  { id: "add_to_cart", name: "دکمه خرید (Add to Cart)", category: "ecommerce" },
  { id: "mini_cart", name: "مینی کارت (Mini Cart)", category: "ecommerce" },
  { id: "cart_summary", name: "خلاصه سبد خرید (Cart Summary)", category: "ecommerce" }
];

const PATTERNS_28 = [
  "hero-banner", "feature-grid", "product-showcase-cta", "testimonials", "faq-accordion",
  "image-text", "countdown-offer", "star-rating-display", "review-histogram", "product-card-grid",
  "text-marquee", "stats-counter", "image-gallery-showcase", "discount-badge-banner", "mega-menu-categories",
  "pricing-table", "price-list", "icon-box-grid", "author-bio", "pull-quote",
  "support-callout", "comparison-table", "process-steps", "lead-capture-form", "alert-banner",
  "floating-contact-bar", "brand-logo-carousel", "product-highlights"
];

const STUDIO_SURFACES = [
  { id: "builder_toolbar", name: "نوار ابزار بالای استودیو", category: "studio" },
  { id: "layers_tree", name: "درخت لایه‌ها و نویگیتور", category: "studio" },
  { id: "global_styles_dialog", name: "دیالوگ تنظیمات استایل سراسری", category: "dialog" },
  { id: "save_template_dialog", name: "دیالوگ ذخیره قالب سکشن", category: "dialog" },
  { id: "save_page_template_dialog", name: "دیالوگ ذخیره قالب برگه", category: "dialog" },
  { id: "keyboard_shortcuts_dialog", name: "دیالوگ راهنمای میانبرها", category: "dialog" }
];

const matrix = {
  version: "2.0.0",
  lastUpdated: new Date().toISOString(),
  totalRows: WIDGETS_35.length + PATTERNS_28.length + STUDIO_SURFACES.length,
  stats: {
    widgetsTotal: WIDGETS_35.length,
    patternsTotal: PATTERNS_28.length,
    surfacesTotal: STUDIO_SURFACES.length,
    passedCount: 0,
    failingCount: 0,
    pendingProbeCount: 0,
  },
  widgets: WIDGETS_35.map((w, index) => ({
    seq: index + 1,
    id: w.id,
    name: w.name,
    category: w.category,
    tabs: {
      content: {
        hasControls: true,
        testedSignals: { state: false, dom: false, style: false, pixels: false, ssr: false },
        status: "pending_probe"
      },
      style: {
        hasControls: true,
        testedSignals: { state: false, dom: false, style: false, pixels: false, ssr: false },
        status: "pending_probe"
      },
      advanced: {
        hasControls: true,
        testedSignals: { state: false, dom: false, style: false, pixels: false, ssr: false },
        status: "pending_probe"
      }
    },
    overallStatus: "pending_probe"
  })),
  patterns: PATTERNS_28.map((slug, index) => ({
    seq: index + 1,
    slug,
    name: `الگوی آماده: ${slug}`,
    signals: {
      insertion: false,
      canvasRender: false,
      ssrRender: false,
      wysiwygParity: false,
      rtlCheck: false
    },
    status: "pending_probe"
  })),
  studioSurfaces: STUDIO_SURFACES.map((s, index) => ({
    seq: index + 1,
    id: s.id,
    name: s.name,
    category: s.category,
    signals: {
      interactive: false,
      hotkeys: false,
      dialogState: false,
      responsive: false
    },
    status: "pending_probe"
  }))
};

matrix.stats.pendingProbeCount = matrix.totalRows;

const outputPath = path.join(ROOT_DIR, ".loop/builder_control_matrix.json");
fs.writeFileSync(outputPath, JSON.stringify(matrix, null, 2), "utf8");
console.log(`Generated builder control matrix: ${outputPath}`);
console.log(`Included ${matrix.widgets.length} widgets, ${matrix.patterns.length} patterns, and ${matrix.studioSurfaces.length} studio surfaces.`);
