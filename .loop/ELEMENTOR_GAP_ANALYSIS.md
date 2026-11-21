# Elementor & Elementor Pro Gap Analysis & Architecture Comparison

**Reference Source**: `C:\Users\Administrator\Desktop\elementor` (Core 3.x & Pro 3.x)  
**Target Codebase**: `site/frontend/components/admin/builder/**`  
**Date**: 2026-11-21  

---

## 1. Architectural Model Comparison

| Dimension | Elementor Architecture (PHP/Backbone/React) | Our Visual Page Builder (Next.js/React/Zustand) | Verdict & Alignment |
|-----------|---------------------------------------------|-------------------------------------------------|---------------------|
| **State Storage** | Flat Backbone Models with hierarchical `parent_id` & `elements` tree, stored in WP Post Meta as JSON | Hierarchical typed `PageAST` in Zustand with `rootElements` recursive tree, stored in PostgreSQL JSONB | ✅ Modern React architecture; clean AST serialization |
| **Canvas Isolation** | Iframe preview loaded via `?elementor-preview=ID` with WordPress front-end scripts | Isolated `CanvasFrame` Iframe with React Portal mounts for content & overlay | ✅ True responsive isolation (`md:`, `lg:` evaluate against frame) |
| **Control System** | `Controls_Stack` with Section, Tabs (Content, Style, Advanced), Dynamic Tags | Inspector Panel with 3 tabs (Content, Style, Advanced), direct reactive bindings | ✅ 1:1 Parity with Elementor 3-tab layout |
| **Design Tokens** | Elementor Site Settings (Global Colors, Global Fonts) stored in Kit | 2-Layer Tokens: Layer 1 (Active SiteTheme API) + Layer 2 (`globalStyles` overrides) | ✅ Full live preview sync to canvas document |
| **Selection & Overlay** | Selection highlight rendered directly inside iframe document DOM | Root-level `#builder-overlay-mount` portal rendering selection boxes & floating toolbar | ✅ Zero CSS clipping from container `overflow: hidden` |

---

## 2. Feature Parity & Gap Matrix

### 2.1 Editor Workspace & Interaction
- **Floating Toolbar**: ✅ Implemented with Drag Handle, Duplicate, Delete, Reorder (Up/Down), Style Copy/Paste, and Save as Template.
- **Navigator / Layers Tree**: ✅ Implemented with Search, Expand/Collapse all, Drag-and-Drop tree reordering, inline rename, and hide/lock toggles.
- **Context Menu**: ✅ Implemented right-click menu with Wrap in Container, Unwrap, Duplicate, Copy, Paste, Delete.
- **Keyboard Shortcuts**: ✅ Implemented `Ctrl+Z`, `Ctrl+Y`, `Ctrl+C`, `Ctrl+V`, `Ctrl+D`, `Alt+Up/Down`, `Escape` (deselection), and `?` cheat sheet modal.

### 2.2 Container Layout Engine
- **Boxed vs. Full Width**: ✅ Implemented via `boxedWidth` slider / number input and max-width clamping.
- **Flexbox Controls**: ✅ Direction (row/column/reverse), Wrap, Justify-Content, Align-Items, Align-Self, Order.
- **Grid Layout**: ✅ 1 to 4 columns grid presets with configurable gap.
- **Background Overlays**: ✅ Color, opacity, and blend modes for container backgrounds.

### 2.3 Styling & Visual Polish
- **CSS Filters**: ✅ Blur, brightness, contrast, grayscale, and sepia filters with live canvas and backend AST compiler parity.
- **Shape Dividers**: ✅ Top & Bottom SVG wave, curve, and triangle dividers.
- **Box Shadow & Borders**: ✅ Full 4-corner unlinked border-radius, border styles, and box shadows.
- **Mobile-First Responsive Overrides**: ✅ Separate overrides for Desktop, Tablet (768px), and Mobile (375px).

### 2.4 Advanced & Dynamic Capabilities
- **Device Visibility**: ✅ Hide on Desktop / Tablet / Mobile with preview indicator badges.
- **Authentication Visibility**: ✅ Show to All / Authenticated / Guest users with server-side compiler enforcement.
- **CSS Motion Effects**: ✅ Fade-in, slide-up, zoom-in with custom duration and delay.
- **Global Components**: ✅ Linked components that update all instances across the page when edited.

---

## 3. High-Value Opportunities for Further Hardening
1. **Empty Container Guidance**: Ensure empty containers have an unambiguous dashed bounding box with min-height >= 80px and accessible action button. (Addressed in P0).
2. **Layers Tree RTL Indent**: Maintain clean visual hierarchy with `depth * 24px` margin-right and vertical guide line. (Addressed in P0).
3. **Selection Clearance**: Ensure floating toolbar always flips below element when approaching iframe ceiling (< 40px). (Verified in Gym R01).
