"use client";

import { useEffect, useState } from "react";
import { fetchShopFeatures, DEFAULT_SHOP_FEATURES, type ShopFeatures } from "@/lib/api/shop-features";

/**
 * Read the storefront feature switches once and share them.
 *
 * Every consumer (header, account dashboard, product page, compare bar) needs
 * the same two booleans, and they must agree — a header link that disappears
 * while the page it points at still renders is the bug this prevents. One
 * module-level fetch backs every caller so the state cannot drift between
 * components, and so turning a switch off in the admin panel is picked up on the
 * next navigation rather than requiring a reload per component.
 *
 * Defaults to "everything on" until the response lands, matching the backend's
 * own default: briefly showing a feature beats briefly hiding the store's
 * navigation.
 */
let cached: ShopFeatures | null = null;
let inFlight: Promise<ShopFeatures> | null = null;

async function loadOnce(): Promise<ShopFeatures> {
  if (cached) return cached;
  if (!inFlight) {
    inFlight = fetchShopFeatures().then((features) => {
      cached = features;
      inFlight = null;
      return features;
    });
  }
  return inFlight;
}

/** Drop the cache so the next mount re-reads. Used after an admin toggle. */
export function invalidateShopFeatures(): void {
  cached = null;
}

export function useShopFeatures(): ShopFeatures {
  const [features, setFeatures] = useState<ShopFeatures>(
    cached ?? DEFAULT_SHOP_FEATURES,
  );

  useEffect(() => {
    let cancelled = false;
    void loadOnce().then((loaded) => {
      if (!cancelled) setFeatures(loaded);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return features;
}