"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import apiClient, { sessionStore } from "@/lib/api/client";

export interface CartItem {
  id?: string; // Cart item UUID in backend
  variantId?: string; // Product variant UUID
  productId: string; // Product UUID or identifier
  title: string;
  slug?: string;
  price: number; // Unit price in Toman
  originalPrice?: number; // Original price in Toman
  quantity: number;
  image?: string;
  variant?: string; // Variant description (e.g., color/size)
  sku?: string;
  maxQuantity?: number;
  isAvailable?: boolean;
}

export interface BackendCartItem {
  id: string;
  variant_id: string;
  quantity: number;
  price_snapshot: number; // in Rial
  subtotal: number; // in Rial
  product_name?: string | null;
  variant_info?: string | null;
  sku?: string | null;
  current_price?: number | null; // in Rial
  image_url?: string | null;
  is_available?: boolean | null;
  price_toman?: number;
  subtotal_toman?: number;
}

export interface BackendCartResponse {
  id: string;
  user_id?: string | null;
  session_id?: string | null;
  status: string;
  items: BackendCartItem[];
  subtotal: number; // in Rial
  item_count: number;
  subtotal_toman?: number;
}

export interface CartStore {
  cartId: string | null;
  items: CartItem[];
  isLoading: boolean;
  isSyncing: boolean;
  error: string | null;
  couponCode: string | null;
  couponDiscount: number; // In Toman

  // Computed / cached values (in Toman)
  totalItems: number;
  totalPrice: number;
  subtotal: number;
  totalDiscount: number;

  // Actions
  fetchCart: () => Promise<void>;
  addItem: (item: Omit<CartItem, "quantity"> & { quantity?: number }) => Promise<void>;
  removeItem: (idOrProductId: string) => Promise<void>;
  updateQuantity: (idOrProductId: string, quantity: number) => Promise<void>;
  clearCart: () => Promise<void>;
  mergeCart: () => Promise<void>;
  applyCoupon: (code: string) => Promise<{ success: boolean; message: string; discount?: number }>;
  removeCoupon: () => Promise<void>;
}

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isUuid(val?: string | null): boolean {
  if (!val) return false;
  return UUID_REGEX.test(val);
}

function mapBackendItemToCartItem(bItem: BackendCartItem): CartItem {
  // Backend stores prices in Rial. 1 Toman = 10 Rials.
  const priceToman =
    typeof bItem.price_toman === "number"
      ? bItem.price_toman
      : Math.round((bItem.price_snapshot || 0) / 10);

  const originalPriceToman =
    typeof bItem.current_price === "number" && bItem.current_price > bItem.price_snapshot
      ? Math.round(bItem.current_price / 10)
      : undefined;

  return {
    id: bItem.id,
    variantId: bItem.variant_id,
    productId: bItem.variant_id,
    title: bItem.product_name || "محصول انتخابی",
    // No reliable product slug comes from the backend cart payload — putting
    // the SKU here produced /products/<sku> 404 links from the cart.
    slug: undefined,
    price: priceToman,
    originalPrice: originalPriceToman,
    quantity: bItem.quantity,
    image: bItem.image_url || undefined,
    variant: bItem.variant_info || undefined,
    sku: bItem.sku || undefined,
    isAvailable: bItem.is_available ?? true,
    maxQuantity: 10,
  };
}

function computeTotals(items: CartItem[], couponDiscount: number = 0) {
  const totalItems = items.reduce((sum, item) => sum + item.quantity, 0);
  const subtotal = items.reduce(
    (sum, item) => sum + (item.price || 0) * (item.quantity || 1),
    0,
  );
  const itemDiscount = items.reduce((sum, item) => {
    if (item.originalPrice && item.originalPrice > item.price) {
      return sum + (item.originalPrice - item.price) * item.quantity;
    }
    return sum;
  }, 0);
  const totalDiscount = itemDiscount + couponDiscount;
  const totalPrice = Math.max(0, subtotal - couponDiscount);

  return {
    totalItems,
    subtotal,
    totalPrice,
    totalDiscount,
  };
}

/**
 * Zustand cart store (internal).
 *
 * For component-level cart access, prefer the `useCart()` hook from
 * `@/hooks/use-cart` which wraps this store with stable callbacks,
 * automatic hydration, and a cart-summary helper.
 *
 * Direct imports of `useCartStore` are acceptable in:
 *   - `@/hooks/use-cart.ts`   (the wrapper hook itself)
 *   - `@/hooks/use-auth.ts`   (cart merge on login)
 *   - pages that only need a single action (e.g. account page `addItem`)
 */
export const useCartStore = create<CartStore>()(
  persist(
    (set, get) => ({
      cartId: null,
      items: [],
      isLoading: false,
      isSyncing: false,
      error: null,
      couponCode: null,
      couponDiscount: 0,
      totalItems: 0,
      totalPrice: 0,
      subtotal: 0,
      totalDiscount: 0,

      fetchCart: async () => {
        try {
          set({ isLoading: true, error: null });
          const response = await apiClient.get<BackendCartResponse>("/cart");
          const backendCart = response.data;

          if (backendCart && Array.isArray(backendCart.items)) {
            const mappedItems = backendCart.items.map(mapBackendItemToCartItem);
            const totals = computeTotals(mappedItems, get().couponDiscount);

            set({
              cartId: backendCart.id,
              items: mappedItems,
              ...totals,
              isLoading: false,
              error: null,
            });
          } else {
            set({ isLoading: false });
          }
        } catch (err: unknown) {
          // If offline, keep local persisted items
          set({ isLoading: false });
        }
      },

      addItem: async (item) => {
        const { items, couponDiscount } = get();
        const addQty = item.quantity ?? 1;

        // Match existing item by variantId or (productId and variant name)
        const existingIndex = items.findIndex(
          (i) =>
            (item.variantId && i.variantId === item.variantId) ||
            (i.productId === item.productId && i.variant === item.variant),
        );

        let updatedItems: CartItem[];
        let targetVariantId = item.variantId;

        if (existingIndex > -1 && items[existingIndex]) {
          const existing = items[existingIndex]!;
          targetVariantId = targetVariantId || existing.variantId;
          const newQty = existing.quantity + addQty;
          updatedItems = items.map((i, idx) =>
            idx === existingIndex ? { ...i, quantity: newQty } : i,
          );
        } else {
          const newItem: CartItem = {
            ...item,
            quantity: addQty,
          };
          updatedItems = [...items, newItem];
        }

        // 1. Optimistic update (instant UI reaction)
        const totals = computeTotals(updatedItems, couponDiscount);
        set({
          items: updatedItems,
          ...totals,
          isSyncing: true,
          error: null,
        });

        // 2. Sync with backend API: POST /cart/items
        const effectiveVariantId = targetVariantId || (isUuid(item.productId) ? item.productId : null);

        if (effectiveVariantId && isUuid(effectiveVariantId)) {
          try {
            const response = await apiClient.post<BackendCartResponse>("/cart/items", {
              variant_id: effectiveVariantId,
              quantity: addQty,
            });

            if (response.data && Array.isArray(response.data.items)) {
              const syncedItems = response.data.items.map(mapBackendItemToCartItem);
              const syncedTotals = computeTotals(syncedItems, get().couponDiscount);
              set({
                cartId: response.data.id,
                items: syncedItems,
                ...syncedTotals,
                isSyncing: false,
              });
              return;
            }
          } catch (apiErr: unknown) {
            if (process.env.NODE_ENV === "development") {
              console.warn("Cart backend sync failed for add item, keeping optimistic update:", apiErr);
            }
          }
        }

        set({ isSyncing: false });
      },

      removeItem: async (idOrProductId) => {
        const { items, couponDiscount } = get();
        const target = items.find(
          (i) =>
            i.id === idOrProductId ||
            i.productId === idOrProductId ||
            i.variantId === idOrProductId,
        );

        const updatedItems = items.filter(
          (i) =>
            i.id !== idOrProductId &&
            i.productId !== idOrProductId &&
            i.variantId !== idOrProductId,
        );

        // 1. Optimistic update
        const totals = computeTotals(updatedItems, couponDiscount);
        set({
          items: updatedItems,
          ...totals,
          isSyncing: true,
        });

        // 2. Sync with backend API: DELETE /cart/items/{id}
        if (target?.id && isUuid(target.id)) {
          try {
            const response = await apiClient.delete<BackendCartResponse>(
              `/cart/items/${target.id}`,
            );
            if (response.data && Array.isArray(response.data.items)) {
              const syncedItems = response.data.items.map(mapBackendItemToCartItem);
              const syncedTotals = computeTotals(syncedItems, get().couponDiscount);
              set({
                cartId: response.data.id,
                items: syncedItems,
                ...syncedTotals,
                isSyncing: false,
              });
              return;
            }
          } catch (err) {
            if (process.env.NODE_ENV === "development") {
              console.warn("Cart backend sync failed for remove item:", err);
            }
          }
        }

        set({ isSyncing: false });
      },

      updateQuantity: async (idOrProductId, quantity) => {
        if (quantity <= 0) {
          await get().removeItem(idOrProductId);
          return;
        }

        const { items, couponDiscount } = get();
        const target = items.find(
          (i) =>
            i.id === idOrProductId ||
            i.productId === idOrProductId ||
            i.variantId === idOrProductId,
        );

        const updatedItems = items.map((i) =>
          i.id === idOrProductId ||
          i.productId === idOrProductId ||
          i.variantId === idOrProductId
            ? { ...i, quantity }
            : i,
        );

        // 1. Optimistic update
        const totals = computeTotals(updatedItems, couponDiscount);
        set({
          items: updatedItems,
          ...totals,
          isSyncing: true,
        });

        // 2. Sync with backend API: PATCH /cart/items/{id}
        if (target?.id && isUuid(target.id)) {
          try {
            const response = await apiClient.patch<BackendCartResponse>(
              `/cart/items/${target.id}`,
              { quantity },
            );
            if (response.data && Array.isArray(response.data.items)) {
              const syncedItems = response.data.items.map(mapBackendItemToCartItem);
              const syncedTotals = computeTotals(syncedItems, get().couponDiscount);
              set({
                cartId: response.data.id,
                items: syncedItems,
                ...syncedTotals,
                isSyncing: false,
              });
              return;
            }
          } catch (err) {
            if (process.env.NODE_ENV === "development") {
              console.warn("Cart backend sync failed for update quantity:", err);
            }
          }
        }

        set({ isSyncing: false });
      },

      clearCart: async () => {
        const { items } = get();
        // Optimistic clear
        set({
          items: [],
          couponCode: null,
          couponDiscount: 0,
          totalItems: 0,
          totalPrice: 0,
          subtotal: 0,
          totalDiscount: 0,
        });

        // Delete each item from backend if it has an id
        for (const item of items) {
          if (item.id && isUuid(item.id)) {
            try {
              await apiClient.delete(`/cart/items/${item.id}`);
            } catch {
              // ignore
            }
          }
        }
      },

      mergeCart: async () => {
        const guestSessionId = sessionStore.getSessionId();
        if (!guestSessionId) return;

        try {
          set({ isSyncing: true });
          const response = await apiClient.post<BackendCartResponse>("/cart/merge", {
            guest_session_id: guestSessionId,
          });

          if (response.data && Array.isArray(response.data.items)) {
            const syncedItems = response.data.items.map(mapBackendItemToCartItem);
            const totals = computeTotals(syncedItems, get().couponDiscount);
            set({
              cartId: response.data.id,
              items: syncedItems,
              ...totals,
              isSyncing: false,
            });
            // Clear or reset guest session ID after successful merge
            sessionStore.clearSessionId();
          } else {
            set({ isSyncing: false });
          }
        } catch (err) {
          if (process.env.NODE_ENV === "development") {
            console.warn("Merge cart failed:", err);
          }
          set({ isSyncing: false });
        }
      },

      applyCoupon: async (code: string) => {
        const trimmed = code.trim();
        if (!trimmed) {
          return { success: false, message: "کد تخفیف را وارد کنید." };
        }

        const { subtotal } = get();
        // Subtotal in Rial for backend (1 Toman = 10 Rials)
        const subtotalRials = subtotal * 10;

        try {
          // Backend endpoint: POST /discounts/coupons/apply?cart_total=...
          // (the coupons routes live on the discounts router)
          const response = await apiClient.post<{
            coupon_id: string;
            code: string;
            discount_amount: number; // in Rials
            discount_type: string;
            description: string;
          }>(`/discounts/coupons/apply?cart_total=${subtotalRials}`, {
            code: trimmed,
          });

          const discountRials = response.data.discount_amount || 0;
          const discountToman = Math.round(discountRials / 10);

          const { items } = get();
          const totals = computeTotals(items, discountToman);

          set({
            couponCode: response.data.code,
            couponDiscount: discountToman,
            ...totals,
          });

          return {
            success: true,
            message: response.data.description || "کد تخفیف با موفقیت اعمال شد.",
            discount: discountToman,
          };
        } catch (err: unknown) {
          // Check if error message is available from API
          const message =
            (err as { message?: string })?.message ||
            "کد تخفیف وارد شده نامعتبر یا منقضی شده است.";

          return {
            success: false,
            message,
          };
        }
      },

      removeCoupon: async () => {
        const { couponCode, items } = get();
        if (couponCode) {
          try {
            await apiClient.post("/discounts/coupons/remove", { code: couponCode });
          } catch {
            // ignore
          }
        }
        const totals = computeTotals(items, 0);
        set({
          couponCode: null,
          couponDiscount: 0,
          ...totals,
        });
      },
    }),
    {
      name: "cart-storage",
      skipHydration: true,
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
        cartId: state.cartId,
        items: state.items,
        couponCode: state.couponCode,
        couponDiscount: state.couponDiscount,
        totalItems: state.totalItems,
        totalPrice: state.totalPrice,
        subtotal: state.subtotal,
        totalDiscount: state.totalDiscount,
      }),
    },
  ),
);
