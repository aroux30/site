# 🎨 Enterprise UI/UX Design System & Frontend Architecture

> **Authoritative Specification & Guidelines**  
> **Role:** Principal Frontend Architect & UI/UX Director  
> **Target Sessions:** `sess_9da42dc9-aee7-42d1-a27b-a367cbb2472d` & Primary Engineering Sessions  
> **Framework:** Next.js 15 (App Router) + React 19 + TypeScript + Tailwind CSS + Radix UI + Framer Motion  

---

## 🏛️ 1. Design System Foundations & Architecture Benchmarks

This design system is curated from the world's leading design systems and component libraries:

| Tier / Category | Reference Systems | Architectural Role in Project |
|---|---|---|
| **Tier S (Core Primitives)** | `shadcn/ui` + `Radix UI` | Accessible, unstyled primitives styled with Tailwind CSS & CSS variables. Zero runtime bloat. |
| **Motion & Micro-interactions** | `Magic UI` + `Aceternity UI` + `Framer Motion` | Fluid transitions, spring physics, dynamic badges, marquee promos, shimmering buttons, subtle glow effects. |
| **E-Commerce & Merchant UX** | `Shopify Polaris` | Best-in-class product cards, order status timelines, filter ribbons, checkout steppers, and cart drawers. |
| **Analytics & Admin UI** | `Tremor` + `IBM Carbon` | Clean data tables, KPI metric cards, delta indicators, sparklines, and dense administrative forms. |
| **Persian / RTL System Design** | `Vazirmatn` + Custom CSS Tokens | Native RTL-first layout, optical kerning for Farsi, tabular Persian numerals (`tabular-nums`), logical CSS properties. |

---

## 🎨 2. Color Palette & Semantic Design Tokens

All colors are expressed as HSL CSS variables in `globals.css` and mapped via `tailwind.config.ts`.
This ensures seamless dark mode transition without flash of unstyled content (FOUC).

### 2.1 Brand & Functional Scales

- **Primary (Emerald & Persian Jade):**
  - Light mode: `hsl(160, 84%, 39%)` (`#059669` / Tailwind Emerald-600)
  - Dark mode: `hsl(160, 84%, 45%)` (`#10b981` / Tailwind Emerald-500)
  - Significance: Trust, freshness, prosperity in Persian e-commerce.
- **Secondary (Teal / Turquoise):**
  - Light mode: `hsl(174, 62%, 47%)` (`#0d9488`)
  - Accentuation: Supplementary actions, discounts, informational badges.
- **Surface & Backgrounds:**
  - Light: Pure background `hsl(0, 0%, 100%)`, Muted container `hsl(150, 10%, 96%)`, Card surface `hsl(0, 0%, 100%)`
  - Dark: Deep background `hsl(150, 10%, 5%)`, Muted container `hsl(150, 10%, 15%)`, Card surface `hsl(150, 10%, 8%)`
- **Feedback & Semantics:**
  - **Success:** Green-600 (`#16a34a`) — Payment verified, order delivered, in-stock badge.
  - **Warning:** Amber-500 (`#f59e0b`) — Pending payment, low stock alert, OTP countdown warning.
  - **Destructive:** Rose-600 (`#e11d48`) — Order cancelled, payment failed, form errors.
  - **Info:** Blue-600 (`#2563eb`) — Shipping tracker, system announcements.

---

## ✍️ 3. Persian Typography & Numeral Rules (RTL-First)

1. **Typeface:** **Vazirmatn Variable** (`--font-vazirmatn`) loaded locally via `next/font/local` (`public/fonts/Vazirmatn-Variable.woff2`).
2. **Directionality:** Root HTML must enforce `dir="rtl"` and `lang="fa"`.
3. **Persian Numbers Rule:**
   - All prices, counts, dates, and discounts **MUST** pass through `toPersianDigits()` or `formatPrice()`.
   - Prices must include the currency suffix: `تومان`.
   - Numerals in tables, counters, and prices must have `font-variant-numeric: tabular-nums` (class `.num-fa`) to avoid horizontal jitter.
4. **Logical CSS Properties:**
   - Always prefer `start` and `end` over `left` and `right`:
     - `ps-4` instead of `pl-4`
     - `pe-4` instead of `pr-4`
     - `ms-auto` instead of `ml-auto`
     - `text-start` instead of `text-left`
     - `border-s` instead of `border-l`
   - For icons with direction (e.g. Chevron, Arrow):
     - Forward navigation in RTL points **Left** (`ChevronLeft`).
     - Back navigation in RTL points **Right** (`ChevronRight`).

---

## 🧩 4. Component Inventory & Standards

### 4.1 UI Core Components (`components/ui/`)
All 22 core components are strictly typed and adhere to the `cva` (class-variance-authority) pattern:
- `Button`: Primary, Secondary, Outline, Ghost, Link, Destructive. Sizes: sm, default, lg, icon. Full keyboard accessibility.
- `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`: High-contrast, clean borders, subtle hover elevation.
- `Badge`: Variants: `default`, `secondary`, `destructive`, `outline`, `success`, `warning`, `info`.
- `Dialog`, `DropdownMenu`, `Select`, `Tabs`, `Accordion`, `Tooltip`: Built on Radix primitives, handles focus trap, outside click, ESC key, and ARIA attributes.
- `Input`, `Textarea`, `Checkbox`, `Switch`, `Slider`: Fully accessible form controls with unified ring focus indicators.
- `Toast`, `Toaster`: Stackable notifications sliding in from screen-start (RTL appropriate).

### 4.2 Layout Components (`components/layout/`)
- **Header:**
  - Sticky with scroll detection and subtle glassmorphism border.
  - Quick top banner (contact info + free shipping threshold).
  - Expandable smart search bar with live suggestion slots.
  - Mega-menu category trigger + quick links.
  - User avatar/menu, Wishlist counter, Cart badge indicator with pulse effect.
- **Footer:**
  - 4-column Polaris-inspired architecture (About & Trust, Quick Links, Customer Service, Legal & Contact).
  - 4 Trust Badges (Fast Shipping, Authenticity Guarantee, 7-Day Return, 24/7 Support).
  - Persian copyright with dynamic Jalali year.

---

## ✨ 5. Animation & Motion Guidelines (Framer Motion & Magic UI)

1. **Philosophy:** Motion must be functional, purposeful, and never disorienting.
2. **Reduced Motion:** Always respect `prefers-reduced-motion`. In Tailwind: `motion-safe:` or `motion-reduce:`.
3. **Key Animation Archetypes:**
   - **Page / Section Transitions:** Subtle fade & translateY (`opacity: 0, y: 12` → `opacity: 1, y: 0`), duration `0.25s` to `0.35s`, ease `easeInOut`.
   - **Micro-interactions:**
     - Button active scale: `whileTap={{ scale: 0.98 }}`.
     - Cart item quantity update: spring bounce on badge counter.
     - Product Card hover: `y: -4px` with gentle shadow expansion.
   - **Shimmer / Skeleton:** Fluid loading states using CSS linear gradients instead of blocking loaders.

---

## 🛡️ 6. Frontend Quality & Accessibility (QA Checklist)

- [x] **Zero TypeScript Errors:** Strict mode enabled, zero `any`, all models typed in `types/`.
- [x] **Zero Hydration Mismatches:** LocalStorage and date/time components protected against SSR/CSR mismatches.
- [x] **Keyboard Navigation:** Full tab-order navigation across all interactive dialogs, menus, and forms.
- [x] **Contrast Ratio:** Minimum 4.5:1 for normal text and 3:1 for large text across light and dark modes.
- [x] **Mobile Responsiveness:** Tested from 360px viewport (mobile) up to 2560px ultra-wide screens.
- [x] **Clean Production Build:** `next build` generates 15 optimized static & dynamic routes.

---

## 🔄 7. Inter-Session Sync & Protocol

- This specification is shared between the **UI/UX Director session** and **Engineering session (`sess_9da42dc9-aee7-42d1-a27b-a367cbb2472d`)**.
- Any architectural change to tokens, layout structures, or shared components must be updated here first.
- The UI/UX Director continuously monitors code quality, accessibility, design fidelity, and build health across the repository.
