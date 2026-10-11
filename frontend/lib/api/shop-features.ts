import apiClient from "./client";

/**
 * Storefront feature switches.
 *
 * Each feature has a master switch. When it is off the whole surface must
 * disappear — the header link, the account tab, the per-product button, the
 * floating bar, the page itself — not merely refuse the write. Rendering a
 * button whose only outcome is an error is the defect class these switches
 * exist to prevent, so every consumer below hides on `enabled` instead of
 * relying on the backend to refuse.
 *
 * The read is public and unauthenticated: the header renders these links for
 * signed-out visitors, so the client has to know the state before it knows who
 * the user is. Only booleans come back.
 */
export interface ShopFeatures {
  wishlist: boolean;
  compare: boolean;
}

interface RawShopFeatures {
  wishlist_enabled?: boolean;
  compare_enabled?: boolean;
}

export const DEFAULT_SHOP_FEATURES: ShopFeatures = {
  wishlist: true,
  compare: true,
};

/**
 * Read the current switch state. A failed read returns the defaults (every
 * feature on) rather than hiding the store's own features: a network blip must
 * not silently strip navigation from the site.
 */
export async function fetchShopFeatures(): Promise<ShopFeatures> {
  try {
    const res = await apiClient.get<RawShopFeatures>("/shop-features");
    return {
      wishlist: res.data?.wishlist_enabled ?? true,
      compare: res.data?.compare_enabled ?? true,
    };
  } catch {
    return DEFAULT_SHOP_FEATURES;
  }
}