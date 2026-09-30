"use client";

import { useCallback, useEffect } from "react";
import { useCartStore, type CartItem } from "@/stores/cart-store";

export function useCart() {
  const store = useCartStore();

  // Rehydrate persisted state on mount (skipHydration: true in store config)
  useEffect(() => {
    useCartStore.persist.rehydrate();
  }, []);

  // Initial sync on mount if on client
  useEffect(() => {
    store.fetchCart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // All action wrappers below resolve the store through getState() so their
  // identities stay stable across renders. In zustand v5 every `set` produces
  // a new state object; closing over `store` gave these callbacks unstable
  // identities, and any consumer with the callback in an effect dependency
  // (checkout's initial cart sync) entered an infinite render loop.
  const addToCart = useCallback(
    (product: {
      productId: string;
      variantId?: string;
      title: string;
      slug?: string;
      customFields?: Record<string, string | number>;
      price: number;
      originalPrice?: number;
      image?: string;
      variant?: string;
      sku?: string;
      maxQuantity?: number;
      quantity?: number;
    }) => {
      return useCartStore.getState().addItem({
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
    [],
  );

  const removeFromCart = useCallback((idOrProductId: string) => {
    return useCartStore.getState().removeItem(idOrProductId);
  }, []);

  const updateItemQuantity = useCallback(
    (idOrProductId: string, quantity: number) => {
      return useCartStore.getState().updateQuantity(idOrProductId, quantity);
    },
    [],
  );

  const clearCart = useCallback(() => {
    return useCartStore.getState().clearCart();
  }, []);

  const fetchCart = useCallback(() => {
    return useCartStore.getState().fetchCart();
  }, []);

  const mergeCart = useCallback(() => {
    return useCartStore.getState().mergeCart();
  }, []);

  const applyCoupon = useCallback((code: string) => {
    return useCartStore.getState().applyCoupon(code);
  }, []);

  const removeCoupon = useCallback(() => {
    return useCartStore.getState().removeCoupon();
  }, []);

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
    // Free shipping threshold: 500,000 Tomans (seed: free_shipping_min_toman)
    const freeShippingEligible = subtotal >= 500000;
    const shipping = subtotal === 0 ? 0 : freeShippingEligible ? 0 : 50000;
    // VAT estimate matching the server formula (TaxService: 10% of
    // subtotal − discount, computed in Rials) — QA B25: tax used to be
    // invisible until the gateway charged more than the displayed total.
    const tax = Math.round((Math.max(subtotal - discount, 0) * 10 * 1000) / 10000 / 10);
    const total = Math.max(0, subtotal - discount + shipping + tax);

    return {
      itemCount,
      subtotal,
      discount,
      shipping,
      tax,
      total,
      freeShippingEligible,
      freeShippingRemaining: Math.max(0, 500000 - subtotal),
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
