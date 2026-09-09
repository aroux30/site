"use client";

import { useCallback, useEffect } from "react";
import { useCartStore, type CartItem } from "@/stores/cart-store";

export function useCart() {
  const store = useCartStore();

  // Initial sync on mount if on client
  useEffect(() => {
    store.fetchCart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addToCart = useCallback(
    (product: {
      productId: string;
      variantId?: string;
      title: string;
      slug?: string;
      price: number;
      originalPrice?: number;
      image?: string;
      variant?: string;
      sku?: string;
      maxQuantity?: number;
      quantity?: number;
    }) => {
      return store.addItem({
        productId: product.productId,
        variantId: product.variantId,
        title: product.title,
        slug: product.slug,
        price: product.price,
        originalPrice: product.originalPrice,
        image: product.image,
        variant: product.variant,
        sku: product.sku,
        maxQuantity: product.maxQuantity || 10,
        quantity: product.quantity ?? 1,
      });
    },
    [store],
  );

  const removeFromCart = useCallback(
    (idOrProductId: string) => {
      return store.removeItem(idOrProductId);
    },
    [store],
  );

  const updateItemQuantity = useCallback(
    (idOrProductId: string, quantity: number) => {
      return store.updateQuantity(idOrProductId, quantity);
    },
    [store],
  );

  const clearCart = useCallback(() => {
    return store.clearCart();
  }, [store]);

  const fetchCart = useCallback(() => {
    return store.fetchCart();
  }, [store]);

  const mergeCart = useCallback(() => {
    return store.mergeCart();
  }, [store]);

  const applyCoupon = useCallback(
    (code: string) => {
      return store.applyCoupon(code);
    },
    [store],
  );

  const removeCoupon = useCallback(() => {
    return store.removeCoupon();
  }, [store]);

  const isInCart = useCallback(
    (productId: string): boolean => {
      return store.items.some(
        (item) => item.productId === productId || item.variantId === productId,
      );
    },
    [store.items],
  );

  const getItemQuantity = useCallback(
    (productId: string): number => {
      const item = store.items.find(
        (item) => item.productId === productId || item.variantId === productId,
      );
      return item?.quantity || 0;
    },
    [store.items],
  );

  const getCartSummary = useCallback(() => {
    const itemCount = store.totalItems;
    const subtotal = store.subtotal || store.totalPrice;
    const discount = store.couponDiscount || 0;
    // Free shipping threshold: 5,000,000 Tomans
    const freeShippingEligible = subtotal >= 5000000;
    const shipping = subtotal === 0 ? 0 : freeShippingEligible ? 0 : 50000;
    const total = Math.max(0, subtotal - discount + shipping);

    return {
      itemCount,
      subtotal,
      discount,
      shipping,
      total,
      freeShippingEligible,
      freeShippingRemaining: Math.max(0, 5000000 - subtotal),
    };
  }, [store.totalItems, store.subtotal, store.totalPrice, store.couponDiscount]);

  return {
    cartId: store.cartId,
    items: store.items,
    totalItems: store.totalItems,
    totalPrice: store.totalPrice,
    subtotal: store.subtotal,
    totalDiscount: store.totalDiscount,
    couponCode: store.couponCode,
    couponDiscount: store.couponDiscount,
    isLoading: store.isLoading,
    isSyncing: store.isSyncing,
    error: store.error,
    addToCart,
    removeFromCart,
    updateItemQuantity,
    clearCart,
    fetchCart,
    mergeCart,
    applyCoupon,
    removeCoupon,
    isInCart,
    getItemQuantity,
    getCartSummary,
  };
}

export type { CartItem };
