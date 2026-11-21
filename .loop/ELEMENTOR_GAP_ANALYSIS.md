# Elementor Architecture & Feature Gap Analysis (.loop/ELEMENTOR_GAP_ANALYSIS.md)
**Source Reference**: `C:\Users\Administrator\Desktop\elementor` (Elementor Core & Elementor Pro)  
**Target System**: Proprietary React/Next.js/Tailwind/FastAPI Visual Page Builder  
**Date**: 2026-11-21  

---

## 1. Architectural Model Comparison

| Dimension | Elementor / Elementor Pro | Our Visual Page Builder | Gap Evaluation & Direction |
| :--- | :--- | :--- | :--- |
| **Runtime Architecture** | PHP Server-Side Render + Backbone/Marionette JS Editor + jQuery UI DnD | Next.js 15 App Router + React 18 + Zustand Store + Native HTML5 DnD | **Target Advantage**: Modern React 18, type-safe TypeScript AST, sub-second Turbopack compilation. No PHP/WP baggage. |
| **Canvas Isolation** | `iframe` with `elementor-preview` CSS and dynamic script injection | `iframe[title="Visual Builder Canvas"]` with `createPortal` and two-layer token inheritance | **Parity Status: High**. Both use isolated iframe to evaluate responsive breakpoints natively. |
| **Overlay & Selection** | `.elementor-element-overlay` with floating action handles (`.elementor-editor-element-settings`) | `CanvasOverlayLayer` portal at iframe root with calculated DOM rects and zero-collision ceiling clearance | **Parity Status: Achieved**. Independent overlay eliminates DOM clipping and transform bugs. |
| **Layout Model** | Flexbox Container + CSS Grid (`e-con`, `e-flexbox-base`, `e-div-block-base`) | Flexible Flexbox + Grid Containers (`kind: "flex" \| "grid"`) with gap, boxed width and direction | **Parity Status: High**. Boxed vs full width and 6 preset layouts supported. |
| **Component Hierarchy** | Page -> Section/Container -> Column/Inner Container -> Widget | PageAST -> Root Container Elements -> Nested Containers -> Widget Elements | **Parity Status: Full 1:1 Match**. Both represent a recursive tree with typed children. |
| **History & Time Travel** | Elementor Revision History panel (`$e.modules.editor.history`) | `HistoryPanel` with `history.past` and `history.future` and `jumpToHistoryStep` | **Parity Status: High**. Undo/Redo (Ctrl+Z, Ctrl+Y) and 1-click step jumping supported. |
| **Shortcuts Engine** | Hotkeys Manager with modal dialog (Ctrl+C, Ctrl+V, Ctrl+D, Ctrl+S, ?, Escape) | Keydown forwarder across iframe boundary + `KeyboardShortcutsDialog` + `hotkeys-dialog` | **Parity Status: Achieved**. Full shortcut parity including iframe event forwarding. |

---

## 2. Core Widget Inventory Comparison

| Elementor Core/Pro Widget | Project Native Block / Pattern | Parity Status | Implementation Note |
| :--- | :--- | :--- | :--- |
| **Container / Section** | `container` / `section` | **PASS (100%)** | Flex/Grid, boxed width, background overlay, shape dividers. |
| **Heading** | `heading` (H1-H6) | **PASS (100%)** | Responsive typography, colors, custom IDs/classes. |
| **Text Editor / Paragraph** | `text_editor` | **PASS (100%)** | Rich text, clean HTML sanitization, prose typography. |
| **Image** | `image` | **PASS (100%)** | Object-fit, border radius, alt tag, media library picker. |
| **Button** | `button` | **PASS (100%)** | Target url, new tab, custom CSS class, inline editing. |
| **Spacer & Divider** | `spacer` & `divider` | **PASS (100%)** | Dynamic height, border styles (solid/dashed/dotted/double). |
| **Accordion & Toggle** | `accordion` | **PASS (100%)** | Multi-item CRUD in inspector, first-item default open. |
| **Tabs** | `tabs` | **PASS (100%)** | Multi-tab CRUD, active tab styling, responsive layout. |
| **Table** | `table` | **PASS (100%)** | Thead/Tbody editing, striped rows, column highlight. |
| **Form Builder** | `form_container` + input/textarea/select/checkbox/radio | **PASS (100%)** | Connected to backend endpoint `/api/v1/content/forms/submit` with honeypot spam protection. |
| **Countdown Timer** | `countdown` | **PASS (100%)** | Dynamic JS countdown calculation with Jalali/Persian two-digit formatter. |
| **Icon Box** | `icon_box` | **PASS (100%)** | Icon, title, description with brand styling. |
| **Social Links** | `social_links` | **PASS (100%)** | Configurable platforms (Instagram, Telegram, LinkedIn, etc.). |
| **Image Gallery** | `image_gallery` | **PASS (100%)** | Grid display, lightbox preview, responsive columns. |
| **Star Rating & Histogram** | `star_rating` & `review_histogram` | **PASS (100%)** | E-commerce grade rating display and 5-star distribution bar chart. |
| **WooCommerce Product Card/Grid** | `product_card` & `product_grid` | **PASS (100%)** | Dynamic filtering (all/featured/best_sellers), live price, pagination. |
| **Product Variants & Pricing** | `product_variants` & `product_price` | **PASS (100%)** | Live variant switcher, discount badges, Toman currency formatting. |
| **Cart & Checkout Widgets** | `add_to_cart`, `mini_cart`, `cart_summary` | **PASS (100%)** | Connected to live Zustand `useCartStore` with toast feedback. |
| **Mega Menu & Recently Viewed** | `mega_menu` & `recently_viewed` | **PASS (100%)** | Desktop/mobile navigation, browsing history tracker. |

---

## 3. Advanced Features & Inspector Parity

### Content Tab Parity
- **Text & Tag Controls**: H1-H6 selection, links with new-tab toggle.
- **Media Selector**: Integrated `MediaPicker` and direct manual URL input.
- **Dynamic List Editors**: Accordion items, Tabs items, Form options, Social links, Table rows/columns.

### Style Tab Parity
- **Backgrounds**: 4-mode switcher (None, Color, Gradient, Image) with direction and size controls.
- **Background Overlay**: Color, Gradient, and Opacity controls.
- **Typography**: Font family (Vazirmatn / System-UI), font size, font weight, line height, text align.
- **Borders & Radii**: Solid, dashed, dotted, double; independent or linked 4-side radius.
- **Box Shadow**: Grouped shadow controls (X, Y, blur, spread, color).
- **CSS Filters**: Custom filter string with instant presets (Blur, Grayscale, Contrast, Sepia).
- **Flex Items & Order**: `alignSelf` (start/center/end/stretch), `order` (integer).

### Advanced Tab Parity
- **Margin & Padding**: 4-side spacing box with linked/unlinked values.
- **Z-Index & Opacity**: 0.0 - 1.0 opacity slider and numerical z-index.
- **Custom CSS ID & Class**: Anchors reflected in canvas DOM and backend server compiler.
- **Responsive Visibility**: Per-device visibility toggles (Desktop, Tablet, Mobile) with visual badges in editor.
- **Global Components**: 1-click sync across page instances, detach/unlink with undo support.
- **Motion Effects**: Fade-in, Slide-up, Zoom-in animations with duration and delay.
- **Shape Dividers**: Waves, Curve, Triangle, Tilt (top and bottom) with custom color fills.

---

## 4. Prioritized Architectural Recommendations

1. **Keep Strict Isolation**: Maintain canvas iframe and portal-based overlay layer. Never revert to in-DOM floating toolbar that suffers from overflow clipping.
2. **Double-layer Design Token Pipeline**: Preserve Layer 1 (SiteTheme backend tokens) and Layer 2 (Page-level globalStyles override) with HSL channel normalization.
3. **Backend AST Validation & Sanitization**: Maintain zero-drift schema parity between TypeScript `PageAST` and Python Pydantic `BuilderAST` models.
4. **WYSIWYG Parity Assurance**: Ensure every style attribute in `DeviceStyle` has an exact match in `ast_compiler.py` so the rendered storefront output is visually indistinguishable from the canvas.
