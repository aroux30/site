# Visual Page Builder Feature Inventory (.loop/BUILDER_FEATURE_INVENTORY.md)
**Date**: 2026-11-21  
**Project**: Visual Page Builder (`site`)  
**Reference**: Elementor & Elementor Pro  
**Inventory Scope**: 35 Basic & Layout Blocks, 28 Ready Patterns, Full Inspector Controls, Core Workspaces  

---

## 1. Studio Workspaces & Shell Features

| Feature Name | File Path | UI Location | Expected Behavior | Observed Behavior | Status | Evidence | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Studio Fullscreen Layout** | `builder-studio.tsx` | Full Viewport | Fixed 3-column layout (Sidebar, Canvas, Inspector) | Verified clean fullscreen with header/footer suppression | **PASS** | `builder-gym-r01.spec.ts` test 1 | P0 |
| **`?builder=1` Activation** | `[slug]/page.tsx` | URL Query | Directly activates editor studio for authenticated super admins | Fast activation with admin token | **PASS** | `builder-gym-r01.spec.ts` test 1 | P0 |
| **Chat FAB Suppression** | `builder-studio.tsx` | Global DOM | Floating chat bubble (`#n8n-w`) hidden while in builder | `#n8n-w` display: none confirmed | **PASS** | `deterministic-audit.mjs` | P0 |
| **Iframe Canvas Workspace** | `canvas-frame.tsx` | Center Canvas | Isolated iframe evaluating media queries natively | Verified 375px/768px/desktop rendering | **PASS** | `builder-gym-r05.spec.ts` test 1 | P0 |
| **Canvas Ceiling Clearance** | `canvas-frame.tsx` | Iframe Top | 48px padding provides safe headroom for floating toolbar | `rect.top >= 0` verified, zero clipping | **PASS** | `builder-gym-r01.spec.ts` test 2 | P0 |
| **Independent Overlay Layer** | `canvas-overlay-layer.tsx` | Iframe Overlay | High z-index portal rendering hover/selection/multi-select boxes | Accurately tracks element DOM rects | **PASS** | `builder-gym-r04.spec.ts` test 2 | P0 |
| **Floating Action Toolbar** | `canvas-overlay-layer.tsx` | Above Active El | Drag handle, duplicate, delete, move up/down, global component, template | Actions execute seamlessly | **PASS** | `builder-gym-r04.spec.ts` test 2 | P0 |
| **Empty Container Guide** | `canvas-element.tsx` | Empty Container | Dashed border, >=80px min-height, actionable guide button | 123px height with icon and guide text | **PASS** | `deterministic-audit.mjs` | P0 |
| **Layers Tree (Navigator)** | `layers-tree.tsx` | Left Sidebar | 24px RTL indent, guide lines, always-visible action buttons | Verified 0 opacity-0 buttons at mouse (0,0) | **PASS** | `deterministic-audit.mjs` | P0 |
| **Layers Tree Drag-and-Drop** | `layers-tree.tsx` | Left Sidebar | Native HTML5 drag handle to reorder tree hierarchy | Seamless branch reparenting | **PASS** | `EXCAVATOR_LOG.md` Round 03 | P1 |
| **Layers Tree Search & Expand** | `layers-tree.tsx` | Left Sidebar | Search query filter and global expand/collapse chevrons | Real-time filtering verified | **PASS** | `EXCAVATOR_LOG.md` Round 16 | P1 |
| **History & Time Travel Panel**| `history-panel.tsx` | Left Sidebar | List past/future mutations and 1-click step jumping | `jumpToHistoryStep` restores state | **PASS** | `EXCAVATOR_LOG.md` Round 09 | P1 |
| **Keyboard Shortcuts Modal** | `hotkeys-dialog.tsx` | Toolbar / '?' key | Comprehensive reference of shortcuts (Ctrl+C, Ctrl+V, etc.) | Modal renders properly above studio | **PASS** | `EXCAVATOR_LOG.md` Round 05 | P1 |
| **Right-Click Context Menu** | `builder-context-menu.tsx` | Canvas & Tree | Cut, Copy, Paste, Duplicate, Wrap, Delete, Inspect | Context actions execute cleanly | **PASS** | `EXCAVATOR_LOG.md` Round 01 & 07 | P1 |
| **Save Page as Template** | `save-page-template-dialog.tsx` | Toolbar | Save entire AST as page template with synced title | Successfully persists to database | **PASS** | `builder-gym-r04.spec.ts` test 3 | P1 |
| **Global Styles Dialog** | `global-styles-dialog.tsx` | Toolbar | Primary/secondary colors, typography, border radius tokens | Rendered with high z-index above studio | **PASS** | `builder-gym-r03.spec.ts` test 1 | P1 |

---

## 2. Block Patterns Inventory (28 Total)

| Slug | Category | Title | Status | Verified Features |
| :--- | :--- | :--- | :--- | :--- |
| `hero-banner` | بنر و هیرو | بنر اصلی (هیرو) | **PASS** | 2-column grid, responsive heading, action button with custom classes. |
| `text-marquee` | بنر و هیرو | متن چرخشی تبلیغاتی | **PASS** | Animated horizontal ticker text with brand background. |
| `feature-grid` | محتوا | شبکه ویژگی‌ها | **PASS** | 3-column benefit cards with icons and descriptions. |
| `image-text` | محتوا | تصویر و متن | **PASS** | 2-column alternating media and prose block. |
| `stats-counter` | محتوا | شمارنده آمار | **PASS** | 4 KPI numeric indicators with Persian labels. |
| `icon-box-grid` | محتوا | جعبه‌های مزایا و خدمات | **PASS** | Grid of value propositions with Lucide icons. |
| `author-bio` | محتوا | کارت معرفی کارشناس / نویسنده | **PASS** | Rounded author avatar, title, bio, and social badge. |
| `pull-quote` | محتوا | نقل‌قول و پیام برجسته | **PASS** | Blockquote with `border-s-4` and italic quotation style. |
| `process-steps` | محتوا | مراحل گام‌به‌گام خرید و تحویل | **PASS** | 4-step progressive workflow indicators. |
| `product-showcase-cta` | محصولات | معرفی محصولات با دکمه | **PASS** | Product banner with direct checkout CTA. |
| `star-rating-display` | محصولات | نمایش امتیاز ستاره‌ای | **PASS** | Amber stars and review count display. |
| `review-histogram` | محصولات | نمودار توزیع امتیاز | **PASS** | 5-level rating breakdown percentage bars. |
| `product-card-grid` | محصولات | گرید ویترین کالاها | **PASS** | Multi-product grid connected to product catalog. |
| `image-gallery-showcase` | محتوا | گالری تصاویر محصولات | **PASS** | Multi-image responsive thumbnail gallery. |
| `product-highlights` | محصولات | ویژگی‌های کلیدی محصول | **PASS** | Bulleted specification card. |
| `testimonials` | محتوا | نظرات مشتریان | **PASS** | Customer feedback cards with avatars. |
| `brand-logo-carousel` | محتوا | گردونه برندهای همکار | **PASS** | Partner logos grid with grayscale filter hover. |
| `faq-accordion` | محتوا | پرسش‌های متداول (آکاردئون) | **PASS** | Collapsible Q&A items with first-item open. |
| `countdown-offer` | بنر و هیرو | پیشنهاد شگفت‌انگیز زمان‌دار | **PASS** | Real-time JS countdown with Jalali format. |
| `discount-badge-banner` | بنر و هیرو | بنر تخفیف ویژه با دکمه خرید | **PASS** | High-contrast discount callout banner. |
| `alert-banner` | بنر و هیرو | نوار اطلاع‌رسانی بالای صفحه | **PASS** | Sticky or banner alert bar with close action. |
| `mega-menu-categories` | ناوبری | مگامنو دسته‌بندی کالاها | **PASS** | Multi-column navigation with category links. |
| `pricing-table` | فروشگاهی | جدول تعرفه و پلن‌های اشتراک | **PASS** | 3-tier pricing plan with featured badge and descriptions. |
| `price-list` | فروشگاهی | لیست قیمت خدمات و کالاها | **PASS** | Dotted/dashed price leader list. |
| `comparison-table` | فروشگاهی | جدول مقایسه ویژگی‌ها | **PASS** | Highlighted column with checkmark/cross matrix. |
| `support-callout` | محتوا | کادر تماس و پشتیبانی سریع | **PASS** | Quick support card with direct call/chat links. |
| `lead-capture-form` | تعاملی | فرم ثبت درخواست و مشاوره | **PASS** | Name, phone, select, textarea with backend submit handler. |
| `floating-contact-bar` | تعاملی | نوار ارتباطی سریع شناور | **PASS** | Quick contact action buttons. |

---

## 3. Inspector Controls Inventory

| Tab | Section | Controls | Behavior & Verification | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Content** | Widget Properties | Text, Heading tag, URL, Target, Images, Form inputs, List items | Two-way binding with element AST. Immediately updates canvas. | **PASS** |
| **Content** | Container Layout | Flex/Grid, Direction, Justify, Align, Columns, Gap, Boxed Width | Live preview on canvas, reflected in server compiler. | **PASS** |
| **Style** | Background | Mode (None/Color/Gradient/Image), Direction, Colors, Size | HSL normalization, live style object injection. | **PASS** |
| **Style** | Background Overlay | Mode (None/Color/Gradient), Color, Gradient, Opacity slider | Renders dedicated overlay div with z-index ordering. | **PASS** |
| **Style** | Typography | Font family, Font size, Font weight, Line height, Text align | Vazirmatn / System-UI support with responsive units. | **PASS** |
| **Style** | Border & Radius | Style (solid/dashed/dotted/double), Color, Width, Radius (4-sides) | Box border and rounded corners reflect on canvas. | **PASS** |
| **Style** | Box Shadow | Horizontal, Vertical, Blur, Spread, Shadow Color | Grouped box shadow CSS output. | **PASS** |
| **Style** | CSS Filters | Custom filter string with instant presets (blur, grayscale, sepia) | Native CSS `filter` style applied in canvas and compiler. | **PASS** |
| **Advanced** | Spacing | Margin and Padding (Top, Right, Bottom, Left, Linked toggle) | SpacingBox units accurately applied. | **PASS** |
| **Advanced** | Positioning | Display, Z-Index, Opacity slider (0.0 to 1.0) | Layer ordering and transparency verified. | **PASS** |
| **Advanced** | Responsive Visibility | Visible on Desktop, Visible on Tablet, Visible on Mobile toggles | Editor badge display and preview mode hiding. | **PASS** |
| **Advanced** | Global Components | Convert to Synced Component, Unlink / Detach | Synchronizes across all AST instances with unique IDs. | **PASS** |
| **Advanced** | Custom CSS | Custom CSS ID and Custom CSS Class | Applied to root HTML tag on canvas and server output. | **PASS** |
| **Advanced** | Motion Effects | Animation (Fade-in, Slide-up, Zoom-in), Duration, Delay | Keyframe animations active on canvas and storefront. | **PASS** |
| **Advanced** | Shape Dividers | Top & Bottom Shape Dividers (Waves, Curve, Triangle, Tilt, Color) | Scalable SVG shape dividers rendered. | **PASS** |
