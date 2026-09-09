"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export interface CartItem {
  productId: string;
  title: string;
  slug: string;
  price: number;
  originalPrice?: number;
  quantity: number;
  image?: string;
  variant?: string;
  maxQuantity?: number;
}

interface CartStore {
  items: CartItem[];
  addItem: (item: Omit<CartItem, "quantity"> & { quantity?: number }) => void;
  removeItem: (productId: string) => void;
  updateQuantity: (productId: string, quantity: number) => void;
  clearCart: () => void;
  totalItems: number;
  totalPrice: number;
  totalDiscount: number;
}

export const useCartStore = create<CartStore>()(
  persist(
    (set, get) => ({
      items: [],

      addItem: (item) => {
        const { items } = get();
        const existing = items.find(
          (i) => i.productId === item.productId && i.variant === item.variant,
        );

        if (existing) {
          set({
            items: items.map((i) =>
              i.productId === item.productId && i.variant === item.variant
                ? { ...i, quantity: i.quantity + (item.quantity ?? 1) }
                : i,
            ),
          });
        } else {
          set({
            items: [...items, { ...item, quantity: item.quantity ?? 1 }],
          });
        }
      },

      removeItem: (productId) => {
        set({ items: get().items.filter((i) => i.productId !== productId) });
      },

      updateQuantity: (productId, quantity) => {
        if (quantity <= 0) {
          set({ items: get().items.filter((i) => i.productId !== productId) });
        } else {
          set({
            items: get().items.map((i) =>
              i.productId === productId ? { ...i, quantity } : i,
            ),
          });
        }
      },

      clearCart: () => {
        set({ items: [] });
      },

      get totalItems() {
        return get().items.reduce((sum, item) => sum + item.quantity, 0);
      },

      get totalPrice() {
        return get().items.reduce(
          (sum, item) => sum + item.price * item.quantity,
          0,
        );
      },

      get totalDiscount() {
        return get().items.reduce((sum, item) => {
          if (item.originalPrice && item.originalPrice > item.price) {
            return sum + (item.originalPrice - item.price) * item.quantity;
          }
          return sum;
        }, 0);
      },
    }),
    {
      name: "cart-storage",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
