import fs from 'node:fs';
import path from 'node:path';

const ROOT_DIR = process.cwd();

const WIDGETS_35 = [
  // 10 Basic & Layout
  { id: "container", name: "کانتینر (Container)", category: "basic", contentControls: ["layoutKind", "direction", "justifyContent", "alignItems", "flexWrap", "gap", "boxedWidth"] },
  { id: "section", name: "بخش سرتاسری (Section)", category: "basic", contentControls: ["layoutKind", "direction", "justifyContent", "gap", "paddingPreset"] },
  { id: "columns", name: "چندستونه (Columns)", category: "basic", contentControls: ["columnCount", "columnGaps", "responsiveStacking"] },
  { id: "heading", name: "سرتیتر (Heading)", category: "basic", contentControls: ["text", "tag", "customCssClass"] },
  { id: "paragraph", name: "پاراگراف متن (Paragraph / Text Editor)", category: "basic", contentControls: ["content", "textAlignment", "lineHeight"] },
  { id: "text", name: "متن کوتاه (Text)", category: "basic", contentControls: ["text", "tag", "fontSize"] },
  { id: "image", name: "تصویر شاخص (Image)", category: "basic", contentControls: ["url", "alt", "mediaLibraryPicker", "objectFit"] },
  { id: "button", name: "دکمه اقدام (Button)", category: "basic", contentControls: ["label", "url", "newTab", "buttonSize"] },
  { id: "spacer", name: "فاصله‌ساز (Spacer)", category: "basic", contentControls: ["height", "responsiveHeight"] },
  { id: "divider", name: "خط جداکننده (Divider)", category: "basic", contentControls: ["borderStyle", "thickness", "color", "widthPercentage"] },

  // 13 Interactive / Form
  { id: "table", name: "جدول داده‌ها (Table)", category: "interactive_form", contentControls: ["headers", "rows", "bordered", "striped", "cellAlignment"] },
  { id: "form_container", name: "کانتینر فرم (Form Container)", category: "interactive_form", contentControls: ["submitUrl", "successMessage", "errorMessage", "emailNotification"] },
  { id: "form_input", name: "ورودی متنی فرم (Form Input)", category: "interactive_form", contentControls: ["label", "name", "placeholder", "inputType", "required"] },
  { id: "form_textarea", name: "متن چندخطی فرم (Form Textarea)", category: "interactive_form", contentControls: ["label", "name", "placeholder", "rows", "required"] },
  { id: "form_select", name: "منوی کشویی فرم (Form Select)", category: "interactive_form", contentControls: ["label", "name", "options", "required"] },
  { id: "form_checkbox", name: "کادر تأیید فرم (Form Checkbox)", category: "interactive_form", contentControls: ["label", "name", "checked", "required"] },
  { id: "form_radio", name: "دکمه‌های رادیویی فرم (Form Radio)", category: "interactive_form", contentControls: ["label", "name", "options", "defaultValue"] },
  { id: "accordion", name: "آکاردئون پرسش‌وپاسخ (Accordion)", category: "interactive_form", contentControls: ["items", "addItem", "removeItem", "defaultOpenFirst"] },
  { id: "tabs", name: "تب‌های چندگانه (Tabs)", category: "interactive_form", contentControls: ["tabList", "addTab", "removeTab", "activeTabIndex"] },
  { id: "countdown", name: "شمارنده معکوس (Countdown)", category: "interactive_form", contentControls: ["title", "targetDate", "expiredMessage"] },
  { id: "video", name: "ویدئو و رسانه (Video)", category: "interactive_form", contentControls: ["videoType", "url", "poster", "autoplay", "controls"] },
  { id: "icon_box", name: "باکس آیکون و خدمات (Icon Box)", category: "interactive_form", contentControls: ["icon", "title", "description", "linkUrl"] },
  { id: "social_links", name: "لینک‌های شبکه‌های اجتماعی (Social Links)", category: "interactive_form", contentControls: ["platforms", "addPlatform", "removePlatform", "iconSize"] },

  // 12 Shop / Commerce
  { id: "product_card", name: "کارت تک‌محصول (Product Card)", category: "shop", contentControls: ["name", "price", "image", "inStock", "ctaText"] },
  { id: "product_grid", name: "گرید ویترین محصولات (Product Grid)", category: "shop", contentControls: ["limit", "categoryFilter", "sortOrder", "pagination"] },
  { id: "image_gallery", name: "گالری تصاویر محصول (Image Gallery)", category: "shop", contentControls: ["images", "columns", "lightbox", "aspectRatio"] },
  { id: "star_rating", name: "امتیاز ستاره‌ای (Star Rating)", category: "shop", contentControls: ["ratingValue", "maxStars", "reviewCount", "starColor"] },
  { id: "review_histogram", name: "نمودار میله‌ای نظرات (Review Histogram)", category: "shop", contentControls: ["averageRating", "totalReviews", "distributionBars"] },
  { id: "recently_viewed", name: "بازدیدهای اخیر (Recently Viewed)", category: "shop", contentControls: ["limit", "displayTitle", "clearButton"] },
  { id: "mega_menu", name: "مگامنو دسته‌بندی‌ها (Mega Menu)", category: "shop", contentControls: ["menuLabel", "categorySource", "depth", "featuredBadge"] },
  { id: "product_price", name: "قیمت هوشمند کالا (Product Price)", category: "shop", contentControls: ["price", "compareAtPrice", "currency", "discountBadge"] },
  { id: "product_variants", name: "سلکتور تنوع‌ها (Product Variants)", category: "shop", contentControls: ["variantsList", "displayStyle", "priceUpdateSync"] },
  { id: "add_to_cart", name: "دکمه خرید مستقیم (Add to Cart)", category: "shop", contentControls: ["buttonText", "variantId", "directCheckoutRedirect"] },
  { id: "mini_cart", name: "پیش‌نمایش سریع سبد (Mini Cart)", category: "shop", contentControls: ["showCountBadge", "dropdownPreview", "iconStyle"] },
  { id: "cart_summary", name: "خلاصه سبد سفارش (Cart Summary)", category: "shop", contentControls: ["showSubtotal", "showTax", "checkoutButtonLabel"] }
];

const PATTERNS_28 = [
  { slug: "hero-banner", title: "بنر اصلی (هیرو)", category: "بنر و هیرو" },
  { slug: "feature-grid", title: "شبکه ویژگی‌ها", category: "محتوا" },
  { slug: "product-showcase-cta", title: "معرفی محصولات با دکمه", category: "محصولات" },
  { slug: "testimonials", title: "نظرات مشتریان", category: "محتوا" },
  { slug: "faq-accordion", title: "پرسش‌های متداول (آکاردئون)", category: "محتوا" },
  { slug: "image-text", title: "تصویر و متن متناوب", category: "محتوا" },
  { slug: "countdown-offer", title: "پیشنهاد شگفت‌انگیز زمان‌دار", category: "بنر و هیرو" },
  { slug: "star-rating-display", title: "نمایش امتیاز ستاره‌ای", category: "محصولات" },
  { slug: "review-histogram", title: "نمودار توزیع امتیاز", category: "محصولات" },
  { slug: "product-card-grid", title: "گرید ویترین کالاها", category: "محصولات" },
  { slug: "text-marquee", title: "متن چرخشی تبلیغاتی", category: "بنر و هیرو" },
  { slug: "stats-counter", title: "شمارنده آمار و ارقام", category: "محتوا" },
  { slug: "image-gallery-showcase", title: "گالری تصاویر محصولات", category: "محتوا" },
  { slug: "discount-badge-banner", title: "بنر تخفیف ویژه با دکمه خرید", category: "بنر و هیرو" },
  { slug: "mega-menu-categories", title: "مگامنو دسته‌بندی کالاها", category: "ناوبری" },
  { slug: "pricing-table", title: "جدول تعرفه و پلن‌های اشتراک", category: "فروشگاهی" },
  { slug: "price-list", title: "لیست قیمت خدمات و کالاها", category: "فروشگاهی" },
  { slug: "icon-box-grid", title: "جعبه‌های مزایا و خدمات", category: "محتوا" },
  { slug: "author-bio", title: "کارت معرفی کارشناس / نویسنده", category: "محتوا" },
  { slug: "pull-quote", title: "نقل‌قول و پیام برجسته", category: "محتوا" },
  { slug: "support-callout", title: "کادر تماس و پشتیبانی سریع", category: "محتوا" },
  { slug: "comparison-table", title: "جدول مقایسه ویژگی‌ها", category: "فروشگاهی" },
  { slug: "process-steps", title: "مراحل گام‌به‌گام خرید و تحویل", category: "محتوا" },
  { slug: "lead-capture-form", title: "فرم ثبت درخواست و مشاوره", category: "تعاملی" },
  { slug: "alert-banner", title: "نوار اطلاع‌رسانی بالای صفحه", category: "بنر و هیرو" },
  { slug: "floating-contact-bar", title: "نوار ارتباطی سریع شناور", category: "تعاملی" },
  { slug: "brand-logo-carousel", title: "گردونه برندهای همکار", category: "محتوا" },
  { slug: "product-highlights", title: "ویژگی‌های کلیدی محصول", category: "محصولات" }
];

const SHELL_ITEMS = [
  { id: "builder-toolbar", name: "نوار ابزار بالای استودیو (Builder Toolbar)", category: "shell", contentControls: ["saveDraft", "publish", "breakpointSwitch", "previewMode", "undoRedo", "titleEdit"] },
  { id: "layers-tree", name: "درخت لایه‌ها و ناوبر (Layers Tree Navigator)", category: "shell", contentControls: ["itemSelect", "reorderDrag", "visibilityToggle", "lockToggle", "deleteAction", "duplicateAction"] },
  { id: "blocks-palette", name: "پالت انتخاب بلوک‌ها (Blocks Palette)", category: "shell", contentControls: ["blocksSearch", "blocksFilter", "patternSelect", "dragPayload"] }
];

const DIALOG_ITEMS = [
  { id: "global-styles-dialog", name: "پنجره استایل‌های سراسری (Global Styles)", category: "dialog", contentControls: ["primaryColor", "secondaryColor", "accentColor", "fontFamily", "borderRadius", "resetToDefault"] },
  { id: "save-template-dialog", name: "ذخیره الگوی سکشن (Save Section Template)", category: "dialog", contentControls: ["templateTitle", "templateCategory", "persistSave"] },
  { id: "save-page-template-dialog", name: "ذخیره قالب کل صفحه (Save Full Page Template)", category: "dialog", contentControls: ["pageTitle", "slugSync", "persistSave"] },
  { id: "keyboard-shortcuts-dialog", name: "راهنمای کلیدهای میانبر (Keyboard Shortcuts)", category: "dialog", contentControls: ["dialogRender", "keyBindingList", "closeAction"] }
];

const COMMON_STYLE_CONTROLS = [
  "typographyFontFamily", "typographyFontSize", "typographyFontWeight", "typographyLineHeight", "typographyTextAlign", "typographyColor",
  "backgroundMode", "backgroundColor", "backgroundGradient", "backgroundImage",
  "backgroundOverlayMode", "backgroundOverlayColor", "backgroundOverlayOpacity",
  "borderStyle", "borderColor", "borderWidth", "borderRadius",
  "boxShadowPreset", "cssFilters", "opacitySlider"
];

const COMMON_ADVANCED_CONTROLS = [
  "marginSpacingBox", "paddingSpacingBox",
  "layoutPosition", "zIndex",
  "responsiveVisibilityDesktop", "responsiveVisibilityTablet", "responsiveVisibilityMobile",
  "authVisibility", "globalComponentSync",
  "customCssClass", "customCssId",
  "motionAnimation", "animationDuration", "animationDelay",
  "shapeDividerTop", "shapeDividerBottom", "shapeDividerColor"
];

function generateMatrix() {
  const rows = [];

  // 1. Widgets
  for (const w of WIDGETS_35) {
    rows.push({
      id: `WIDGET-${w.id}`,
      itemType: "widget",
      slug: w.id,
      title: w.name,
      category: w.category,
      tabs: {
        content: {
          controls: w.contentControls,
          status: "pending",
          verifiedSignals: []
        },
        style: {
          controls: COMMON_STYLE_CONTROLS,
          status: "pending",
          verifiedSignals: []
        },
        advanced: {
          controls: COMMON_ADVANCED_CONTROLS,
          status: "pending",
          verifiedSignals: []
        }
      },
      signalsRequired: ["S1_state", "S2_dom", "S3_computed_style", "S4_pixel_diff", "S5_persistence_ssr"],
      status: "pending",
      lastVerified: null
    });
  }

  // 2. Patterns
  for (const p of PATTERNS_28) {
    rows.push({
      id: `PATTERN-${p.slug}`,
      itemType: "pattern",
      slug: p.slug,
      title: p.title,
      category: p.category,
      tabs: {
        content: {
          controls: ["patternInsertion", "variableReplacement", "treeReparenting"],
          status: "pending",
          verifiedSignals: []
        },
        style: {
          controls: ["presetStylesApplied", "hslTokensAligned", "responsiveCssVariables"],
          status: "pending",
          verifiedSignals: []
        },
        advanced: {
          controls: ["containerWrapping", "wrapperAnimation", "customClasses"],
          status: "pending",
          verifiedSignals: []
        }
      },
      signalsRequired: ["S1_state", "S2_dom", "S3_computed_style", "S4_pixel_diff", "S5_persistence_ssr"],
      status: "pending",
      lastVerified: null
    });
  }

  // 3. Shell items
  for (const s of SHELL_ITEMS) {
    rows.push({
      id: `SHELL-${s.id}`,
      itemType: "shell",
      slug: s.id,
      title: s.name,
      category: s.category,
      tabs: {
        content: {
          controls: s.contentControls,
          status: "pending",
          verifiedSignals: []
        },
        style: {
          controls: ["fullscreenLayout", "zeroOverflow", "themeTokensApplied"],
          status: "pending",
          verifiedSignals: []
        },
        advanced: {
          controls: ["accessibilityAria", "keyboardShortcutsIntegration"],
          status: "pending",
          verifiedSignals: []
        }
      },
      signalsRequired: ["S1_state", "S2_dom", "S3_computed_style", "S4_pixel_diff", "S5_persistence_ssr"],
      status: "pending",
      lastVerified: null
    });
  }

  // 4. Dialogs
  for (const d of DIALOG_ITEMS) {
    rows.push({
      id: `DIALOG-${d.id}`,
      itemType: "dialog",
      slug: d.id,
      title: d.name,
      category: d.category,
      tabs: {
        content: {
          controls: d.contentControls,
          status: "pending",
          verifiedSignals: []
        },
        style: {
          controls: ["dialogOverlayHighZIndex", "colorTokensPreview", "rtlLayout"],
          status: "pending",
          verifiedSignals: []
        },
        advanced: {
          controls: ["escapeKeyDismiss", "persistPayloadToStorage"],
          status: "pending",
          verifiedSignals: []
        }
      },
      signalsRequired: ["S1_state", "S2_dom", "S3_computed_style", "S4_pixel_diff", "S5_persistence_ssr"],
      status: "pending",
      lastVerified: null
    });
  }

  const matrix = {
    version: "2.0.0",
    lastUpdated: new Date().toISOString(),
    totalRows: rows.length,
    summary: {
      widgets: WIDGETS_35.length,
      patterns: PATTERNS_28.length,
      shellItems: SHELL_ITEMS.length,
      dialogs: DIALOG_ITEMS.length,
      passedCount: 0,
      pendingCount: rows.length
    },
    verificationPolicy: {
      strictScopeLock: true,
      forbiddenForceTrue: true,
      forbiddenTestSkip: true,
      requires5Signals: true
    },
    rows
  };

  const outputPath = path.join(ROOT_DIR, '.loop/builder_control_matrix.json');
  fs.writeFileSync(outputPath, JSON.stringify(matrix, null, 2), 'utf-8');
  console.log(`>>> Written ${rows.length} control matrix rows to ${outputPath}`);
}

generateMatrix();
