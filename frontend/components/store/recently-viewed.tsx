"use client";

import { useEffect, useState, useCallback } from "react";
import { ProductCard } from "@/components/store/product-card";
import { cn } from "@/lib/utils";
import type { ApiProduct } from "@/lib/api/services";

/* ─────────────────────────────────────────────────────────────────────
 * RecentlyViewed — tracks and displays recently viewed products
 *
 * Two exports:
 *   trackProductView(product)  — call from PDP to save a view
 *   <RecentlyViewed />         — renders the horizontal rail
 *
 * Storage: localStorage, max 12 items, newest first.
 * ────────────────────────────────────────────────────────────────── */

const STORAGE_KEY = "recently_viewed";
const MAX_ITEMS = 12;

interface StoredProduct {
  id: string;
  name: string;
  slug: string;
  min_price: number | null;
  max_price: number | null;
  primary_image_url: string | null;
  is_featured: boolean;
  variant_count: number;
  rating_average?: number;
  review_count?: number;
  viewedAt: number;
}

function getStoredProducts(): StoredProduct[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
    return [];
  }
}

function saveProducts(products: StoredProduct[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(products));
  } catch {
    // storage full — silently ignore
  }
}

/** Clear recently viewed products from storage (e.g. on logout or user request) */
export function clearRecentlyViewed() {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

/** Call from PDP to track a product view */
export function trackProductView(
  product: ApiProduct & {
    rating_average?: number;
    review_count?: number;
  }
) {
  const stored = getStoredProducts().filter((p) => p.id !== product.id);
  stored.unshift({
    id: product.id,
    name: product.name,
    slug: product.slug,
    min_price: product.min_price ?? null,
    max_price: product.max_price ?? null,
    primary_image_url: product.primary_image_url ?? null,
    is_featured: product.is_featured,
    variant_count: product.variant_count,
    rating_average: product.rating_average,
    review_count: product.review_count,
    viewedAt: Date.now(),
  });
  saveProducts(stored.slice(0, MAX_ITEMS));
}

interface RecentlyViewedProps {
  /** Exclude this product ID (e.g. the current PDP) */
  excludeId?: string;
  /** Max products to show */
  limit?: number;
  className?: string;
}

export function RecentlyViewed({
  excludeId,
  limit = 6,
  className,
}: RecentlyViewedProps) {
  const [products, setProducts] = useState<StoredProduct[]>([]);

  useEffect(() => {
    const stored = getStoredProducts()
      .filter((p) => p.id !== excludeId)
      .slice(0, limit);
    setProducts(stored);
  }, [excludeId, limit]);

  if (products.length === 0) return null;

  // Convert StoredProduct to ApiProduct shape for ProductCard
  const asApiProducts = products.map(
    (p) =>
      ({
        ...p,
        category_id: "",
        is_active: true,
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
      className={cn("space-y-4", className)}
    >
      <h2
        id="recently-viewed-heading"
        className="text-lg font-bold text-foreground"
      >
        بازدید‌های اخیر شما
      </h2>
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
