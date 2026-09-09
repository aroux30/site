"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { Product } from "@/types/product";
import { toast } from "@/components/ui/use-toast";

export const MAX_COMPARE_PRODUCTS = 4;

export interface CompareState {
  products: Product[];
}

export interface CompareActions {
  addProduct: (product: Product) => boolean;
  removeProduct: (productId: string) => void;
  clearCompare: () => void;
  isInCompare: (productId: string) => boolean;
  toggleProduct: (product: Product) => void;
}

export type CompareStore = CompareState & CompareActions;

export const useCompareStore = create<CompareStore>()(
  persist(
    (set, get) => ({
      products: [],

      addProduct: (product: Product) => {
        const { products } = get();

        // Check for duplicates
        if (products.some((p) => p.id === product.id)) {
          toast({
            title: "محصول در لیست مقایسه وجود دارد",
            description: `«${product.title}» پیش‌تر به لیست مقایسه افزوده شده است.`,
            variant: "default",
          });
          return false;
        }

        // Limit to 4 products
        if (products.length >= MAX_COMPARE_PRODUCTS) {
          toast({
            title: "تکمیل ظرفیت مقایسه",
            description: `حداکثر ${MAX_COMPARE_PRODUCTS} کالا را می‌توانید به صورت همزمان مقایسه نمایید.`,
            variant: "destructive",
          });
          return false;
        }

        set({ products: [...products, product] });

        toast({
          title: "افزوده شد به مقایسه",
          description: `«${product.title}» به لیست مقایسه افزوده شد.`,
          variant: "success",
        });

        return true;
      },

      removeProduct: (productId: string) => {
        const productToRemove = get().products.find((p) => p.id === productId);
        set((state) => ({
          products: state.products.filter((p) => p.id !== productId),
        }));

        if (productToRemove) {
          toast({
            title: "حذف از مقایسه",
            description: `«${productToRemove.title}» از لیست مقایسه حذف شد.`,
            variant: "default",
          });
        }
      },

      clearCompare: () => {
        const count = get().products.length;
        if (count === 0) return;

        set({ products: [] });
        toast({
          title: "پاکسازی لیست مقایسه",
          description: "تمام کالاها از لیست مقایسه حذف شدند.",
          variant: "default",
        });
      },

      isInCompare: (productId: string) => {
        return get().products.some((p) => p.id === productId);
      },

      toggleProduct: (product: Product) => {
        if (get().isInCompare(product.id)) {
          get().removeProduct(product.id);
        } else {
          get().addProduct(product);
        }
      },
    }),
    {
      name: "compare-storage",
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? window.localStorage
          : {
              getItem: () => null,
              setItem: () => {},
              removeItem: () => {},
            },
      ),
      partialize: (state) => ({
        products: state.products,
      }),
    },
  ),
);
