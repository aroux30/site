"use client";

import { useEffect, useState } from "react";
import { ProductCard } from "@/components/store/product-card";
import { cn } from "@/lib/utils";
import {
  useRecentlyViewedStore,
  type StoredRecentlyViewedProduct,
} from "@/stores/recently-viewed-store";
import type { ApiProduct } from "@/lib/api/services";

/* ─────────────────────────────────────────────────────────────────────
 * RecentlyViewed — tracks and displays recently viewed products
 *
 * Backed by Zustand with localStorage persistence.
 *
 * Exports:
 *   trackProductView(product)   — call from PDP or anywhere to record a view
 *   clearRecentlyViewed()       — clears history
 *   useRecentlyViewedStore      — hook to access the reactive store
 *   <RecentlyViewed />          — UI component rendering the product grid
 * ────────────────────────────────────────────────────────────────── */

export { useRecentlyViewedStore };

/** Clear recently viewed products from storage */
export function clearRecentlyViewed() {
  useRecentlyViewedStore.getState().clear();
}

/** Call from PDP or card click to track a product view */
export function trackProductView(
  product: Partial<ApiProduct> & {
    id: string;
    name: string;
    rating_average?: number;
    review_count?: number;
  }
) {
  useRecentlyViewedStore.getState().addProduct(product);
}

interface RecentlyViewedProps {
  /** Exclude this product ID (e.g. the current PDP being viewed) */
  excludeId?: string;
  /** Max products to show (default: 6) */
  limit?: number;
  className?: string;
}

export function RecentlyViewed({
  excludeId,
  limit = 6,
  className,
}: RecentlyViewedProps) {
  const [mounted, setMounted] = useState(false);
  const rawProducts = useRecentlyViewedStore((s) => s.products);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  const filtered = rawProducts
    .filter((p) => p.id !== excludeId)
    .slice(0, limit);

  if (filtered.length === 0) return null;

  // Convert StoredRecentlyViewedProduct to ApiProduct shape for ProductCard
  const asApiProducts = filtered.map(
    (p) =>
      ({
        ...p,
        category_id: "",
        is_active: true,
        is_in_stock: p.is_in_stock ?? true,
        short_description: null,
        description: null,
      }) as ApiProduct & {
        rating_average?: number;
        review_count?: number;
      }
  );

  return (
    <section
      aria-labelledby="recently-viewed-heading"
      className={cn("space-y-4 select-none", className)}
      dir="rtl"
    >
      <div className="flex items-center justify-between">
        <h2
          id="recently-viewed-heading"
          className="text-lg font-bold text-foreground"
        >
          بازدید‌های اخیر شما
        </h2>
        <button
          type="button"
          onClick={() => clearRecentlyViewed()}
          className="text-xs text-muted-foreground hover:text-destructive transition-colors"
        >
          پاک کردن تاریخچه
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
        {asApiProducts.map((product) => (
          <ProductCard
            key={product.id}
            product={product}
            variant="compact"
          />
        ))}
      </div>
    </section>
  );
}
