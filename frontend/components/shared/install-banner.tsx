"use client";

import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";
import { usePWA } from "@/lib/sw-register";
import { cn } from "@/lib/utils";

const DISMISS_KEY = "pwa-install-dismissed";

/**
 * A dismissible bottom banner that prompts the user to install the PWA.
 * Shows only when the browser supports install AND user hasn't dismissed.
 */
export function InstallBanner() {
  const { canInstall, installPrompt } = usePWA();
  const [dismissed, setDismissed] = useState(true); // default hidden to avoid flash

  useEffect(() => {
    try {
      const stored = localStorage.getItem(DISMISS_KEY);
      setDismissed(stored === "true");
    } catch {
      // localStorage unavailable — keep hidden
    }
  }, []);

  if (!canInstall || dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    try {
      localStorage.setItem(DISMISS_KEY, "true");
    } catch {
      // noop
    }
  };

  const handleInstall = async () => {
    const accepted = await installPrompt();
    if (accepted) {
      handleDismiss();
    }
  };

  return (
    <div
      className={cn(
        "fixed inset-x-0 bottom-0 z-50 border-t border-border bg-background/95 px-4 py-3 shadow-lg backdrop-blur-sm",
        "animate-in sm:mx-auto sm:mb-4 sm:max-w-md sm:rounded-xl sm:border sm:inset-x-4",
      )}
      role="banner"
      aria-label="نصب اپلیکیشن"
    >
      <div className="flex items-center gap-3">
        {/* Icon */}
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Download className="h-5 w-5" />
        </div>

        {/* Text */}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">
            نصب اپلیکیشن فروشگاه
          </p>
          <p className="text-xs text-muted-foreground">
            دسترسی سریع‌تر و تجربه بهتر
          </p>
        </div>

        {/* Actions */}
        <button
          onClick={handleInstall}
          className={cn(
            "inline-flex h-9 shrink-0 items-center justify-center rounded-md bg-primary px-4",
            "text-sm font-medium text-primary-foreground",
            "hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          )}
        >
          نصب
        </button>

        <button
          onClick={handleDismiss}
          className={cn(
            "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
            "text-muted-foreground hover:bg-accent hover:text-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          )}
          aria-label="بستن"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
