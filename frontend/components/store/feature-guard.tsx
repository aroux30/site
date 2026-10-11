"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useShopFeatures } from "@/hooks/use-shop-features";
import { PageLoader } from "@/components/shared/page-state";

/**
 * Redirect away from a module's own page when its switch is off.
 *
 * The entry points (header link, nav, button) are already hidden, but a deep
 * link, a bookmark or a search result can still land here. Showing the page and
 * letting its data load fail would be worse than leaving: the customer sees a
 * page that only renders an error.
 *
 * Defaults to "feature on" until the switch state arrives, so a slow read never
 * bounces a customer off a page that is in fact available — the redirect only
 * happens on an explicit `false`.
 */
export function FeatureGuard({
  feature,
  children,
}: {
  feature: "wishlist" | "compare";
  children: React.ReactNode;
}) {
  const router = useRouter();
  const features = useShopFeatures();
  const enabled = features[feature];

  const [resolved, setResolved] = useState(false);

  useEffect(() => {
    setResolved(true);
  }, []);

  useEffect(() => {
    if (resolved && !enabled) router.replace("/");
  }, [resolved, enabled, router]);

  // Hold the loader until the switch state has actually been read: rendering the
  // children first would flash the page that is about to be redirected away from.
  if (!resolved || !enabled) return <PageLoader message="در حال بررسی وضعیت…" />;

  return <>{children}</>;
}