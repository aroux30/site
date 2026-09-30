"use client";

import { useEffect } from "react";
import { registerServiceWorker } from "@/lib/sw-register";
import { InstallBanner } from "@/components/shared/install-banner";
import { OfflineIndicator } from "@/components/shared/offline-indicator";

/**
 * Client-side PWA shell: registers the service worker and renders the
 * install banner + offline indicator. Mounted once in the root layout
 * via <Providers>.
 *
 * Registration lives in ``lib/sw-register.ts`` and is the *only* place the
 * worker is registered; ``lib/pwa.ts`` (browser push) reads the resulting
 * registration rather than making its own. Two registrations of the same
 * worker with different options is undefined behaviour in some browsers.
 */
export function PWAProvider() {
  useEffect(() => {
    registerServiceWorker();
  }, []);

  return (
    <>
      <InstallBanner />
      <OfflineIndicator />
    </>
  );
}
