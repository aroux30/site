"use client";

import { useCallback } from "react";
import { useCartStore, type CartItem } from "@/stores/cart-store";

export function useCart() {
  const store = useCartStore();

  const addToCart = useCallback(
    (product: {
      productId: string;
      title: string;
      slug: string;
      price: number;
      originalPrice?: number;
      image?: string;
      variant?: string;
      maxQuantity?: number;
    }) => {
      store.addItem({
        productId: product.productId,
        title: product.title,
        slug: product.slug,
        price: product.price,
        originalPrice: product.originalPrice,
        image: product.image,
        variant: product.variant,
        maxQuantity: product.maxQuantity || 10,
      });
    },
    [store],
  );

  const removeFromCart = useCallback(
    (productId: string) => {
      store.removeItem(productId);
    },
    [store],
  );

  const updateItemQuantity = useCallback(
    (productId: string, quantity: number) => {
      store.updateQuantity(productId, quantity);
    },
    [store],
  );

  const clearCart = useCallback(() => {
    store.clearCart();
  }, [store]);

  const isInCart = useCallback(
    (productId: string): boolean => {
      return store.items.some((item) => item.productId === productId);
    },
    [store.items],
  );

  const getItemQuantity = useCallback(
    (productId: string): number => {
      const item = store.items.find((item) => item.productId === productId);
      return item?.quantity || 0;
    },
    [store.items],
  );

  const getCartSummary = useCallback(() => {
    const itemCount = store.totalItems;
    const subtotal = store.totalPrice;
    const shipping = subtotal >= 5000000 ? 0 : 50000; // Free shipping over 500k toman
    const total = subtotal + shipping;

    return {
      itemCount,
      subtotal,
      shipping,
      total,
      freeShippingEligible: subtotal >= 5000000,
      freeShippingRemaining: Math.max(0, 5000000 - subtotal),
    };
  }, [store.totalItems, store.totalPrice]);

  return {
    items: store.items,
    totalItems: store.totalItems,
    totalPrice: store.totalPrice,
    addToCart,
    removeFromCart,
    updateItemQuantity,
    clearCart,
    isInCart,
    getItemQuantity,
    getCartSummary,
  };
}

export type { CartItem };
