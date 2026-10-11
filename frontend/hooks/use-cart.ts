"use client";

import { useCallback, useEffect } from "react";
import { useCartStore, type CartItem } from "@/stores/cart-store";
import { useTaxRatePercent } from "@/lib/tax-rate";

export function useCart() {
  const store = useCartStore();
  const taxRatePercent = useTaxRatePercent();

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
    // VAT estimate matching the server formula: (amount_rial × basis_points)
    // // 10000 with basis_points = rate × 100, computed in Rials — QA B25:
    // tax used to be invisible until the gateway charged more than the
    // displayed total. The rate comes from the single admin settings field
    // (the tax engine and its hard-coded 10% were removed 2026-10-09).
    const tax = Math.round(
      (Math.max(subtotal - discount, 0) * taxRatePercent * 1000) / 10000 / 10,
    );
    // Shipping is never estimated client-side: the authoritative cost comes
    // from the server quote at checkout (province + weight + store rates).
    const total = Math.max(0, subtotal - discount + tax);

    return {
      itemCount,
      subtotal,
      discount,
      tax,
      taxRatePercent,
      total,
    };
  }, [store.totalItems, store.subtotal, store.totalPrice, store.couponDiscount, taxRatePercent]);

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
    taxRatePercent,
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
