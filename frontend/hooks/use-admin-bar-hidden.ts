"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

/** The per-tab "preview without the admin bar" mode.
 *
 *  The bar's «بدون نوار» link promises the page as a visitor sees it, and for
 *  a long time the promise was empty: the link opened the same page in a new
 *  tab, bar and all, and nothing anywhere read a flag that would hide it. This
 *  hook is the missing half.
 *
 *  Three decisions, each with a wrong version that looks fine:
 *
 *  - `?nobar=1` is read in an effect, not via `useSearchParams`. The bar is
 *    mounted from a server layout that wraps every storefront route; pulling
 *    `useSearchParams` into that tree would force Suspense/CSR constraints on
 *    every page for a flag that only matters after hydration anyway.
 *  - sessionStorage, not localStorage: the mode belongs to the preview tab.
 *    Navigation inside that tab stays bar-free (the URL param is gone after
 *    the first click; the storage flag is what carries it), while every other
 *    tab — and the operator's normal session — is untouched. Closing the tab
 *    ends the mode. A new tab opened from the bar inherits a copy of the
 *    opener's storage, which is exactly the "still previewing" context.
 *  - `?nobar=0` clears the flag: without an explicit exit, a pasted URL would
 *    strand a tab in preview mode with no way back.
 */
const STORAGE_KEY = "admin-bar-hidden";

function readStoredHidden(): boolean {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    // Storage blocked (private mode / disabled cookies): the URL param still
    // hides the bar for the page it was set on.
    return false;
  }
}

export function useAdminBarHidden(): boolean {
  const pathname = usePathname();
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    const param = new URLSearchParams(window.location.search).get("nobar");

    if (param === "1") {
      try {
        window.sessionStorage.setItem(STORAGE_KEY, "1");
      } catch {
        // The param alone still hides the bar on this page.
      }
      setHidden(true);
      return;
    }

    if (param === "0") {
      try {
        window.sessionStorage.removeItem(STORAGE_KEY);
      } catch {
        // Nothing to clear.
      }
      setHidden(false);
      return;
    }

    // No param on this navigation: the mode (if any) lives in the tab.
    setHidden(readStoredHidden());
  }, [pathname]);

  return hidden;
}
