# Frontend Architecture

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [App Router Architecture](#app-router-architecture)
5. [Component Architecture](#component-architecture)
6. [State Management](#state-management)
7. [Data Fetching Strategy](#data-fetching-strategy)
8. [RTL and Persian Support](#rtl-and-persian-support)
9. [Styling Architecture](#styling-architecture)
10. [Authentication Flow](#authentication-flow)
11. [Performance Optimization](#performance-optimization)
12. [Testing Strategy](#testing-strategy)
13. [Build and Deployment](#build-and-deployment)

---

## 1. Overview

The frontend is built with **Next.js 14+** using the **App Router**, prioritizing **React Server Components (RSC)** for optimal performance. The application is designed as a bilingual (Persian/English), RTL-first e-commerce storefront with a responsive design that adapts across devices.

### Key Principles

- **Server Components First:** Default to Server Components; use Client Components only when interactivity or browser APIs are required.
- **Progressive Enhancement:** Core functionality works without JavaScript; interactivity enhances the experience.
- **Type Safety:** Strict TypeScript throughout with no `any` types in production code.
- **RTL-First Design:** All layouts and components designed for right-to-left rendering from the start.
- **Accessibility:** WCAG 2.1 AA compliance with full keyboard navigation and screen reader support.
- **Performance Budget:** LCP < 2.5s, FID < 100ms, CLS < 0.1.

---

## 2. Technology Stack

| Category                | Technology          | Purpose                                     |
|-------------------------|---------------------|---------------------------------------------|
| **Framework**           | Next.js 14+         | SSR, SSG, ISR, App Router, RSC              |
| **Language**            | TypeScript 5.x      | Type safety across the entire codebase      |
| **Styling**             | Tailwind CSS 3.x    | Utility-first CSS with RTL support           |
| **UI Components**       | shadcn/ui           | Accessible, customizable base components     |
| **Icons**               | Lucide React        | Consistent icon set                           |
| **Client State**        | Zustand             | Lightweight global state management          |
| **Server State**        | TanStack Query v5   | Server state caching, sync, and mutations    |
| **Forms**               | React Hook Form     | Performant form handling with validation     |
| **Validation**          | Zod                 | Schema validation (shared with API types)    |
| **Animation**           | Framer Motion       | Smooth UI transitions and animations         |
| **Charts**              | Recharts            | Admin dashboard visualizations               |
| **Date Handling**       | date-fns-jalali     | Jalali (Persian) calendar support             |
| **Internationalization**| next-intl           | Persian/English localization                  |
| **Testing**             | Vitest + Playwright | Unit, component, and E2E testing              |
| **Linting**             | ESLint + Prettier   | Code quality and formatting                   |

---

## 3. Project Structure

```
frontend/
├── public/
│   ├── fonts/                        # Self-hosted Persian fonts (Vazirmatn, etc.)
│   │   ├── vazirmatn-variable.woff2
│   │   └── inter-variable.woff2
│   ├── images/                       # Static images (logo, placeholders)
│   └── icons/                        # Favicon, PWA icons
│
├── src/
│   ├── app/                          # Next.js App Router
│   │   ├── (storefront)/             # Public storefront route group
│   │   │   ├── layout.tsx            # Storefront layout (header, footer)
│   │   │   ├── page.tsx              # Homepage
│   │   │   ├── products/
│   │   │   │   ├── page.tsx          # Product listing (with search/filter)
│   │   │   │   └── [slug]/
│   │   │   │       └── page.tsx      # Product detail page
│   │   │   ├── categories/
│   │   │   │   └── [slug]/
│   │   │   │       └── page.tsx      # Category page
│   │   │   ├── cart/
│   │   │   │   └── page.tsx          # Shopping cart
│   │   │   ├── checkout/
│   │   │   │   └── page.tsx          # Checkout flow
│   │   │   ├── search/
│   │   │   │   └── page.tsx          # Search results
│   │   │   └── pages/
│   │   │       └── [slug]/
│   │   │           └── page.tsx      # CMS static pages
│   │   │
│   │   ├── (auth)/                   # Authentication route group
│   │   │   ├── layout.tsx            # Auth layout (minimal)
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   ├── register/
│   │   │   │   └── page.tsx
│   │   │   ├── forgot-password/
│   │   │   │   └── page.tsx
│   │   │   └── verify-email/
│   │   │       └── page.tsx
│   │   │
│   │   ├── (dashboard)/              # User dashboard route group
│   │   │   ├── layout.tsx            # Dashboard layout (sidebar)
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx          # User dashboard overview
│   │   │   ├── orders/
│   │   │   │   ├── page.tsx          # Order history
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx      # Order detail
│   │   │   ├── profile/
│   │   │   │   └── page.tsx          # Profile management
│   │   │   ├── addresses/
│   │   │   │   └── page.tsx          # Address book
│   │   │   ├── wallet/
│   │   │   │   └── page.tsx          # Wallet & transactions
│   │   │   └── favorites/
│   │   │       └── page.tsx          # Wishlist
│   │   │
│   │   ├── (admin)/                  # Admin panel route group
│   │   │   ├── layout.tsx            # Admin layout (sidebar, topbar)
│   │   │   ├── admin/
│   │   │   │   ├── page.tsx          # Admin dashboard
│   │   │   │   ├── products/
│   │   │   │   ├── orders/
│   │   │   │   ├── users/
│   │   │   │   ├── categories/
│   │   │   │   ├── promotions/
│   │   │   │   ├── cms/
│   │   │   │   ├── analytics/
│   │   │   │   └── settings/
│   │   │
│   │   ├── api/                      # Next.js API routes (BFF)
│   │   │   └── health/
│   │   │       └── route.ts          # Health check endpoint
│   │   │
│   │   ├── layout.tsx                # Root layout
│   │   ├── not-found.tsx             # 404 page
│   │   ├── error.tsx                 # Error boundary
│   │   ├── loading.tsx               # Global loading state
│   │   └── globals.css               # Global styles + Tailwind imports
│   │
│   ├── components/                   # Shared components
│   │   ├── ui/                       # shadcn/ui primitives
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── select.tsx
│   │   │   ├── toast.tsx
│   │   │   ├── table.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── skeleton.tsx
│   │   │   └── ...
│   │   ├── layout/                   # Layout components
│   │   │   ├── header.tsx
│   │   │   ├── footer.tsx
│   │   │   ├── sidebar.tsx
│   │   │   ├── mobile-nav.tsx
│   │   │   └── breadcrumb.tsx
│   │   ├── product/                  # Product-specific components
│   │   │   ├── product-card.tsx
│   │   │   ├── product-gallery.tsx
│   │   │   ├── product-info.tsx
│   │   │   ├── variant-selector.tsx
│   │   │   ├── price-display.tsx
│   │   │   └── add-to-cart-button.tsx
│   │   ├── cart/                     # Cart components
│   │   │   ├── cart-item.tsx
│   │   │   ├── cart-summary.tsx
│   │   │   └── mini-cart.tsx
│   │   ├── search/                   # Search components
│   │   │   ├── search-bar.tsx
│   │   │   ├── search-filters.tsx
│   │   │   ├── search-results.tsx
│   │   │   └── autocomplete.tsx
│   │   ├── forms/                    # Reusable form components
│   │   │   ├── form-field.tsx
│   │   │   ├── persian-input.tsx
│   │   │   ├── price-input.tsx
│   │   │   └── address-form.tsx
│   │   └── shared/                   # General shared components
│   │       ├── persian-number.tsx
│   │       ├── jalali-date.tsx
│   │       ├── currency-display.tsx
│   │       ├── pagination.tsx
│   │       ├── empty-state.tsx
│   │       ├── loading-spinner.tsx
│   │       └── image-with-fallback.tsx
│   │
│   ├── lib/                          # Utility libraries
│   │   ├── api/                      # API client
│   │   │   ├── client.ts             # Axios/fetch wrapper
│   │   │   ├── endpoints.ts          # API endpoint definitions
│   │   │   └── types.ts              # API response types
│   │   ├── utils/                    # Helper functions
│   │   │   ├── cn.ts                 # Class name merger (clsx + twMerge)
│   │   │   ├── format.ts            # Number, currency, date formatting
│   │   │   ├── persian.ts           # Persian text utilities
│   │   │   └── validation.ts        # Zod schemas
│   │   ├── hooks/                    # Custom React hooks
│   │   │   ├── use-cart.ts
│   │   │   ├── use-auth.ts
│   │   │   ├── use-search.ts
│   │   │   ├── use-debounce.ts
│   │   │   ├── use-media-query.ts
│   │   │   └── use-infinite-scroll.ts
│   │   └── constants.ts             # Application constants
│   │
│   ├── stores/                       # Zustand stores
│   │   ├── auth-store.ts            # Authentication state
│   │   ├── cart-store.ts            # Cart state (optimistic)
│   │   ├── ui-store.ts             # UI state (sidebar, modals)
│   │   └── search-store.ts         # Search filters state
│   │
│   ├── queries/                      # TanStack Query definitions
│   │   ├── products.ts              # Product queries & mutations
│   │   ├── orders.ts               # Order queries & mutations
│   │   ├── cart.ts                  # Cart queries & mutations
│   │   ├── user.ts                 # User queries & mutations
│   │   ├── categories.ts           # Category queries
│   │   └── search.ts              # Search queries
│   │
│   ├── types/                        # TypeScript type definitions
│   │   ├── product.ts
│   │   ├── order.ts
│   │   ├── user.ts
│   │   ├── cart.ts
│   │   ├── category.ts
│   │   ├── payment.ts
│   │   └── api.ts                   # Generic API types
│   │
│   └── messages/                     # Internationalization
│       ├── fa.json                   # Persian translations
│       └── en.json                   # English translations
│
├── tailwind.config.ts               # Tailwind CSS configuration
├── next.config.mjs                  # Next.js configuration
├── tsconfig.json                    # TypeScript configuration
├── package.json                     # Dependencies
├── Dockerfile                       # Container build
└── .env.example                     # Environment variable template
```

---

## 4. App Router Architecture

### 4.1 Route Groups

Route groups (parenthesized directories) organize the application into logical sections without affecting URL structure:

| Route Group      | Purpose                           | Layout                          |
|------------------|-----------------------------------|---------------------------------|
| `(storefront)`   | Public shopping pages             | Header + Footer + Cart Sidebar  |
| `(auth)`         | Authentication pages              | Minimal centered layout          |
| `(dashboard)`    | User account pages                | Sidebar + Topbar                 |
| `(admin)`        | Administration panel              | Admin sidebar + Admin topbar     |

### 4.2 Rendering Strategy

| Page Type           | Strategy  | Rationale                                    |
|---------------------|-----------|----------------------------------------------|
| Homepage            | SSR + ISR | Dynamic content, revalidate every 60s        |
| Product Listing     | SSR       | Search params determine content              |
| Product Detail      | ISR       | Revalidate on product update via webhook     |
| Category Page       | ISR       | Revalidate every 5 minutes                   |
| Cart                | CSR       | Fully interactive, user-specific             |
| Checkout            | CSR       | Interactive multi-step form                  |
| Search Results      | SSR       | SEO-important, query-dependent               |
| User Dashboard      | SSR       | Authenticated, user-specific data             |
| Admin Panel         | CSR       | Highly interactive, no SEO needed             |
| CMS Pages           | SSG       | Static content, rebuilt on publish            |
| Auth Pages          | SSR       | Minimal, redirect if authenticated            |

### 4.3 Server Components vs. Client Components

```
Server Components (default):
├── Page layouts and containers
├── Data fetching and display
├── Navigation components
├── Product cards (static display)
├── Category trees
├── Footer content
├── Breadcrumbs
└── SEO metadata

Client Components ('use client'):
├── Interactive forms (login, checkout, search)
├── Add to cart button (with optimistic update)
├── Shopping cart sidebar
├── Image gallery with zoom/swipe
├── Variant selector (size, color)
├── Search autocomplete
├── Quantity selectors
├── Toast notifications
├── Modal dialogs
├── Dropdown menus
├── Mobile navigation toggle
└── Real-time price calculators
```

### 4.4 Data Fetching in Server Components

```typescript
// app/(storefront)/products/[slug]/page.tsx

import { getProduct, getRelatedProducts } from '@/lib/api/server';
import { ProductInfo } from '@/components/product/product-info';
import { ProductGallery } from '@/components/product/product-gallery';
import { RelatedProducts } from '@/components/product/related-products';
import { notFound } from 'next/navigation';

interface ProductPageProps {
  params: { slug: string };
}

export async function generateMetadata({ params }: ProductPageProps) {
  const product = await getProduct(params.slug);
  if (!product) return {};

  return {
    title: `${product.name} | فروشگاه`,
    description: product.meta_description,
    openGraph: {
      images: [product.images[0]?.url],
    },
  };
}

export default async function ProductPage({ params }: ProductPageProps) {
  const product = await getProduct(params.slug);
  if (!product) notFound();

  const relatedProducts = await getRelatedProducts(product.category_id);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <ProductGallery images={product.images} />
        <ProductInfo product={product} />
      </div>
      <RelatedProducts products={relatedProducts} />
    </div>
  );
}

export const revalidate = 300; // ISR: revalidate every 5 minutes
```

---

## 5. Component Architecture

### 5.1 Component Hierarchy

```
Layout Components (Server)
├── Header
│   ├── Logo
│   ├── SearchBar (Client - interactive)
│   ├── Navigation
│   ├── CartIcon (Client - badge count)
│   └── UserMenu (Client - auth state)
├── Main Content (Server)
│   └── Page-specific components
└── Footer (Server)
    ├── FooterLinks
    ├── SocialLinks
    └── Copyright
```

### 5.2 Component Conventions

| Convention              | Rule                                                  |
|-------------------------|-------------------------------------------------------|
| **File naming**         | `kebab-case.tsx` (e.g., `product-card.tsx`)           |
| **Component naming**    | PascalCase (e.g., `ProductCard`)                      |
| **Props interface**     | `ComponentNameProps` (e.g., `ProductCardProps`)        |
| **Default export**      | Named exports only (no default exports)                |
| **Barrel exports**      | `index.ts` per component directory                     |
| **Server Components**   | No directive (default)                                 |
| **Client Components**   | `'use client'` directive at top of file               |

### 5.3 shadcn/ui Integration

shadcn/ui provides the base component library, installed in `src/components/ui/`. Components are customized for RTL support and Persian design language:

```typescript
// src/components/ui/button.tsx (customized for RTL)

import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-lg px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);
```

---

## 6. State Management

### 6.1 State Management Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    State Management Map                       │
│                                                               │
│  ┌─────────────────┐  ┌──────────────────┐                  │
│  │  Server State    │  │   Client State    │                  │
│  │  (TanStack Query)│  │   (Zustand)       │                  │
│  │                  │  │                    │                  │
│  │  • Products      │  │  • UI state        │                  │
│  │  • Orders        │  │  • Cart (local)    │                  │
│  │  • Categories    │  │  • Auth tokens     │                  │
│  │  • User profile  │  │  • Search filters  │                  │
│  │  • Search results│  │  • Modal state     │                  │
│  │  • Reviews       │  │  • Sidebar toggle  │                  │
│  └─────────────────┘  └──────────────────┘                  │
│                                                               │
│  ┌─────────────────┐  ┌──────────────────┐                  │
│  │  URL State       │  │  Form State       │                  │
│  │  (Next.js Router)│  │  (React Hook Form) │                  │
│  │                  │  │                    │                  │
│  │  • Search query  │  │  • Login form      │                  │
│  │  • Filters       │  │  • Register form   │                  │
│  │  • Pagination    │  │  • Checkout form   │                  │
│  │  • Sort order    │  │  • Product editor  │                  │
│  └─────────────────┘  └──────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Zustand Store Examples

```typescript
// src/stores/cart-store.ts

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface CartItem {
  productId: string;
  variantId: string;
  name: string;
  price: number;
  quantity: number;
  image: string;
}

interface CartStore {
  items: CartItem[];
  isOpen: boolean;
  addItem: (item: CartItem) => void;
  removeItem: (productId: string, variantId: string) => void;
  updateQuantity: (productId: string, variantId: string, quantity: number) => void;
  clearCart: () => void;
  toggleCart: () => void;
  totalItems: () => number;
  totalPrice: () => number;
}

export const useCartStore = create<CartStore>()(
  persist(
    (set, get) => ({
      items: [],
      isOpen: false,

      addItem: (item) =>
        set((state) => {
          const existing = state.items.find(
            (i) => i.productId === item.productId && i.variantId === item.variantId
          );
          if (existing) {
            return {
              items: state.items.map((i) =>
                i.productId === item.productId && i.variantId === item.variantId
                  ? { ...i, quantity: i.quantity + item.quantity }
                  : i
              ),
            };
          }
          return { items: [...state.items, item] };
        }),

      removeItem: (productId, variantId) =>
        set((state) => ({
          items: state.items.filter(
            (i) => !(i.productId === productId && i.variantId === variantId)
          ),
        })),

      updateQuantity: (productId, variantId, quantity) =>
        set((state) => ({
          items: state.items.map((i) =>
            i.productId === productId && i.variantId === variantId
              ? { ...i, quantity }
              : i
          ),
        })),

      clearCart: () => set({ items: [] }),
      toggleCart: () => set((state) => ({ isOpen: !state.isOpen })),
      totalItems: () => get().items.reduce((sum, i) => sum + i.quantity, 0),
      totalPrice: () => get().items.reduce((sum, i) => sum + i.price * i.quantity, 0),
    }),
    {
      name: 'cart-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
```

### 6.3 TanStack Query Configuration

```typescript
// src/lib/api/query-client.ts

import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,       // 5 minutes
      gcTime: 30 * 60 * 1000,          // 30 minutes (formerly cacheTime)
      refetchOnWindowFocus: false,
      retry: 2,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
    mutations: {
      retry: 1,
    },
  },
});
```

```typescript
// src/queries/products.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import type { Product, ProductListParams, PaginatedResponse } from '@/types';

export const productKeys = {
  all: ['products'] as const,
  lists: () => [...productKeys.all, 'list'] as const,
  list: (params: ProductListParams) => [...productKeys.lists(), params] as const,
  details: () => [...productKeys.all, 'detail'] as const,
  detail: (slug: string) => [...productKeys.details(), slug] as const,
};

export function useProducts(params: ProductListParams) {
  return useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => apiClient.get<PaginatedResponse<Product>>('/products', { params }),
  });
}

export function useProduct(slug: string) {
  return useQuery({
    queryKey: productKeys.detail(slug),
    queryFn: () => apiClient.get<Product>(`/products/${slug}`),
    enabled: !!slug,
  });
}
```

---

## 7. Data Fetching Strategy

### 7.1 Server-Side Data Fetching

For Server Components, data is fetched directly using a server-side API client:

```typescript
// src/lib/api/server.ts

import { cookies } from 'next/headers';

const API_BASE_URL = process.env.API_BASE_URL || 'http://backend:8000/api/v1';

async function serverFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const cookieStore = cookies();
  const token = cookieStore.get('access_token')?.value;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  const json = await response.json();
  return json.data;
}

export async function getProducts(params?: Record<string, string>) {
  const searchParams = new URLSearchParams(params);
  return serverFetch(`/products?${searchParams}`);
}

export async function getProduct(slug: string) {
  return serverFetch(`/products/${slug}`);
}
```

### 7.2 Client-Side Data Fetching

For Client Components, TanStack Query manages all server state:

```typescript
// src/lib/api/client.ts

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async get<T>(path: string, config?: { params?: Record<string, any> }): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    if (config?.params) {
      Object.entries(config.params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.set(key, String(value));
        }
      });
    }

    const response = await fetch(url.toString(), {
      credentials: 'include',
    });

    if (!response.ok) {
      throw new ApiError(response.status, await response.json());
    }

    const json = await response.json();
    return json.data;
  }

  async post<T>(path: string, data?: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: data ? JSON.stringify(data) : undefined,
    });

    if (!response.ok) {
      throw new ApiError(response.status, await response.json());
    }

    const json = await response.json();
    return json.data;
  }

  // put, patch, delete methods follow the same pattern
}

export const apiClient = new ApiClient(API_BASE_URL);
```

---

## 8. RTL and Persian Support

### 8.1 HTML Direction Setup

```typescript
// src/app/layout.tsx

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <body className={`${vazirmatn.variable} ${inter.variable} font-sans`}>
        {children}
      </body>
    </html>
  );
}
```

### 8.2 Tailwind CSS RTL Configuration

```typescript
// tailwind.config.ts

import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-vazirmatn)', 'var(--font-inter)', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },
        // Custom colors for the Iranian market aesthetic
        brand: {
          gold: '#D4A84B',
          emerald: '#2D8B61',
          navy: '#1B2A4A',
        },
      },
      spacing: {
        // Persian numeral-friendly spacing if needed
      },
    },
  },
  plugins: [
    require('tailwindcss-rtl'),            // RTL utilities (ms-, me-, ps-, pe-)
    require('@tailwindcss/typography'),     // Prose styling for CMS content
    require('tailwindcss-animate'),         // Animation utilities for shadcn/ui
  ],
};

export default config;
```

### 8.3 RTL-Aware Utility Usage

```tsx
{/* Use logical properties instead of physical ones */}

{/* CORRECT - RTL-aware */}
<div className="ms-4 me-2 ps-6 pe-3 rounded-s-lg border-e">
  <span className="text-start">محتوای فارسی</span>
</div>

{/* INCORRECT - Will break in RTL */}
<div className="ml-4 mr-2 pl-6 pr-3 rounded-l-lg border-r">
  <span className="text-left">محتوای فارسی</span>
</div>
```

### 8.4 Persian Number Formatting

```typescript
// src/lib/utils/persian.ts

/**
 * Convert English digits to Persian digits
 */
export function toPersianDigits(value: string | number): string {
  const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
  return String(value).replace(/[0-9]/g, (d) => persianDigits[parseInt(d)]);
}

/**
 * Format price in Iranian Rial / Toman
 */
export function formatPrice(amount: number, unit: 'rial' | 'toman' = 'toman'): string {
  const value = unit === 'toman' ? Math.floor(amount / 10) : amount;
  const formatted = new Intl.NumberFormat('fa-IR').format(value);
  const suffix = unit === 'toman' ? 'تومان' : 'ریال';
  return `${formatted} ${suffix}`;
}

/**
 * Format date in Jalali calendar
 */
export function formatJalaliDate(date: Date | string): string {
  // Uses date-fns-jalali for Jalali calendar conversion
  return formatJalali(new Date(date), 'yyyy/MM/dd', { locale: faIR });
}
```

### 8.5 Persian Currency Display Component

```tsx
// src/components/shared/currency-display.tsx
'use client';

import { formatPrice } from '@/lib/utils/persian';

interface CurrencyDisplayProps {
  amount: number;
  unit?: 'rial' | 'toman';
  className?: string;
  showDiscount?: boolean;
  originalAmount?: number;
}

export function CurrencyDisplay({
  amount,
  unit = 'toman',
  className,
  showDiscount = false,
  originalAmount,
}: CurrencyDisplayProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      {showDiscount && originalAmount && (
        <span className="text-sm text-muted-foreground line-through">
          {formatPrice(originalAmount, unit)}
        </span>
      )}
      <span className="font-bold text-lg">{formatPrice(amount, unit)}</span>
    </div>
  );
}
```

---

## 9. Styling Architecture

### 9.1 CSS Layer Structure

```css
/* src/app/globals.css */

@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    /* ... dark theme variables */
  }

  /* Persian font optimization */
  body {
    font-feature-settings: 'ss01', 'ss02';
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  /* RTL-specific base styles */
  [dir="rtl"] input[type="tel"],
  [dir="rtl"] input[type="email"] {
    direction: ltr;
    text-align: right;
  }
}
```

### 9.2 Responsive Breakpoints

| Breakpoint | Min Width | Target Device            |
|------------|-----------|--------------------------|
| `sm`       | 640px     | Large phones (landscape) |
| `md`       | 768px     | Tablets                  |
| `lg`       | 1024px    | Small laptops            |
| `xl`       | 1280px    | Desktops                 |
| `2xl`      | 1536px    | Large desktops           |

---

## 10. Authentication Flow

### 10.1 Client-Side Authentication

```typescript
// src/stores/auth-store.ts

import { create } from 'zustand';
import { apiClient } from '@/lib/api/client';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (credentials) => {
    const { user } = await apiClient.post<{ user: User }>('/auth/login', credentials);
    set({ user, isAuthenticated: true });
  },

  logout: async () => {
    await apiClient.post('/auth/logout');
    set({ user: null, isAuthenticated: false });
  },

  refreshUser: async () => {
    try {
      const user = await apiClient.get<User>('/auth/me');
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
```

### 10.2 Route Protection

```typescript
// src/app/(dashboard)/layout.tsx

import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import { verifyToken } from '@/lib/api/server';

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = cookies();
  const token = cookieStore.get('access_token')?.value;

  if (!token) {
    redirect('/login');
  }

  const user = await verifyToken(token);
  if (!user) {
    redirect('/login');
  }

  return (
    <div className="flex min-h-screen" dir="rtl">
      <DashboardSidebar user={user} />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
```

---

## 11. Performance Optimization

### 11.1 Image Optimization

```typescript
// next.config.mjs

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'minio.example.com',
        pathname: '/product-images/**',
      },
    ],
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 768, 1024, 1280, 1536],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
  },
  experimental: {
    optimizePackageImports: ['lucide-react', '@radix-ui/react-icons'],
  },
};

export default nextConfig;
```

### 11.2 Bundle Optimization

- **Code Splitting:** Automatic per-route splitting via App Router.
- **Dynamic Imports:** Heavy components loaded on demand.
- **Tree Shaking:** Only import what is used from libraries.
- **Package Optimization:** `optimizePackageImports` for icon libraries.

```typescript
// Dynamic import for heavy components
const ProductGallery = dynamic(
  () => import('@/components/product/product-gallery').then((m) => m.ProductGallery),
  {
    loading: () => <Skeleton className="aspect-square w-full" />,
    ssr: false,
  }
);
```

### 11.3 Caching Strategy

| Resource             | Cache Strategy                                |
|----------------------|-----------------------------------------------|
| Static assets        | Immutable, long-term cache (via Next.js hash) |
| API responses        | TanStack Query with 5-min staleTime           |
| Product images       | CDN-cached, cache-control: max-age=86400      |
| HTML pages (ISR)     | Revalidate on-demand or time-based            |
| Font files           | Self-hosted, long-term cache                   |

---

## 12. Testing Strategy

### 12.1 Unit Tests (Vitest)

```typescript
// src/lib/utils/__tests__/persian.test.ts

import { describe, it, expect } from 'vitest';
import { toPersianDigits, formatPrice } from '../persian';

describe('toPersianDigits', () => {
  it('converts English digits to Persian', () => {
    expect(toPersianDigits('12345')).toBe('۱۲۳۴۵');
  });

  it('handles mixed content', () => {
    expect(toPersianDigits('Price: 1000')).toBe('Price: ۱۰۰۰');
  });
});

describe('formatPrice', () => {
  it('formats price in Toman', () => {
    expect(formatPrice(1500000, 'toman')).toBe('۱۵۰٬۰۰۰ تومان');
  });
});
```

### 12.2 Component Tests (Vitest + Testing Library)

```typescript
// src/components/product/__tests__/product-card.test.tsx

import { render, screen } from '@testing-library/react';
import { ProductCard } from '../product-card';

describe('ProductCard', () => {
  it('renders product name and price', () => {
    render(
      <ProductCard
        product={{
          name: 'گوشی موبایل',
          price: 15000000,
          image: '/test.jpg',
          slug: 'mobile-phone',
        }}
      />
    );

    expect(screen.getByText('گوشی موبایل')).toBeInTheDocument();
    expect(screen.getByText(/۱٬۵۰۰٬۰۰۰/)).toBeInTheDocument();
  });
});
```

### 12.3 E2E Tests (Playwright)

```typescript
// e2e/product-search.spec.ts

import { test, expect } from '@playwright/test';

test('user can search for products', async ({ page }) => {
  await page.goto('/');

  await page.getByPlaceholder('جستجو در محصولات').fill('گوشی');
  await page.getByPlaceholder('جستجو در محصولات').press('Enter');

  await expect(page).toHaveURL(/\/search\?q=/);
  await expect(page.getByTestId('search-results')).toBeVisible();
  await expect(page.getByTestId('product-card')).toHaveCount.greaterThan(0);
});
```

---

## 13. Build and Deployment

### 13.1 Dockerfile

```dockerfile
# frontend/Dockerfile

FROM node:20-alpine AS base

FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable pnpm && pnpm install --frozen-lockfile

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN corepack enable pnpm && pnpm build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT 3000
CMD ["node", "server.js"]
```

### 13.2 Environment Variables

| Variable                    | Description                              |
|-----------------------------|------------------------------------------|
| `NEXT_PUBLIC_API_URL`       | Public API base URL (client-side)        |
| `API_BASE_URL`              | Internal API URL (server-side, Docker)   |
| `NEXT_PUBLIC_SITE_URL`      | Public site URL                          |
| `NEXT_PUBLIC_MINIO_URL`     | Public MinIO URL for images              |
| `NEXTAUTH_SECRET`           | Session encryption secret                |
| `NEXTAUTH_URL`              | Canonical site URL                       |

---

*For related documentation, see:*
- *[System Architecture](./system.md)*
- *[Backend Architecture](./backend.md)*
- *[Search Architecture](./search.md)*
- *[Entity Relationship Diagram](./erd.md)*
