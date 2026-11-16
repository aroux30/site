"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { ApiProduct } from "@/lib/api/services";

export const MAX_RECENTLY_VIEWED = 12;

export interface StoredRecentlyViewedProduct {
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
  is_in_stock?: boolean;
  viewedAt: number;
}

export interface RecentlyViewedState {
  products: StoredRecentlyViewedProduct[];
}

export interface RecentlyViewedActions {
  addProduct: (product: Partial<ApiProduct> & { id: string; name: string }) => void;
  removeProduct: (productId: string) => void;
  clear: () => void;
}

export type RecentlyViewedStore = RecentlyViewedState & RecentlyViewedActions;

export const useRecentlyViewedStore = create<RecentlyViewedStore>()(
  persist(
    (set, get) => ({
      products: [],

      addProduct: (product) => {
        const current = get().products.filter((p) => p.id !== product.id);
        const item: StoredRecentlyViewedProduct = {
          id: product.id,
          name: product.name,
          slug: product.slug || product.id,
          min_price: product.min_price ?? null,
          max_price: product.max_price ?? null,
          primary_image_url: product.primary_image_url ?? null,
          is_featured: Boolean(product.is_featured),
          variant_count: product.variant_count ?? 1,
          rating_average: (product as any).rating_average,
          review_count: (product as any).review_count,
          is_in_stock: (product as any).is_in_stock ?? true,
          viewedAt: Date.now(),
        };

        const updated = [item, ...current].slice(0, MAX_RECENTLY_VIEWED);
        set({ products: updated });
      },

      removeProduct: (productId) => {
        set({ products: get().products.filter((p) => p.id !== productId) });
      },

      clear: () => {
        set({ products: [] });
      },
    }),
    {
      name: "recently_viewed_store",
      storage: createJSONStorage(() => localStorage),
    }
  )
);
