"use client";

/**
 * The operator's branding, fetched once and shared by the chrome.
 *
 * The header, the footer and the contact page all wanted the store's name and
 * each was asking separately — or, worse, hardcoding a string the operator
 * could not change. One provider means one request per page load, and one
 * place where an unset name becomes the historical default.
 *
 * Deliberately forgiving: a failed fetch leaves the default in place rather
 * than blanking the brand, because a store whose header renders nothing is
 * worse than one showing the old wording.
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiClient } from "@/lib/api/client";

export interface SiteBranding {
  siteName: string;
  contactEmail: string;
}

const FALLBACK: SiteBranding = { siteName: "", contactEmail: "" };

const SiteBrandingContext = createContext<SiteBranding>(FALLBACK);

export function SiteBrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<SiteBranding>(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<{ store_name?: string; contact_email?: string }>("/settings/public/branding")
      .then((res) => {
        if (cancelled) return;
        setBranding({
          siteName: (res.data?.store_name ?? "").trim(),
          contactEmail: (res.data?.contact_email ?? "").trim(),
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // Memoised so a consumer re-rendering does not hand a new object to every
  // sibling and cascade the re-render down the tree.
  const value = useMemo(() => branding, [branding]);
  return <SiteBrandingContext.Provider value={value}>{children}</SiteBrandingContext.Provider>;
}

/** The store name, or the historical default when the operator set none. */
export function useSiteBranding(): SiteBranding {
  const branding = useContext(SiteBrandingContext);
  return {
    siteName: branding.siteName || "فروشگاه آنلاین",
    contactEmail: branding.contactEmail,
  };
}

export default SiteBrandingProvider;
