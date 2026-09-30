"use client";

import { usePWA } from "@/lib/sw-register";
import { WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * A small toast-style banner that appears when the user goes offline.
 * Auto-hides when back online. Sits above the install banner.
 */
export function OfflineIndicator() {
  const { isOnline } = usePWA();

  if (isOnline) return null;

  return (
    <div
      role="status"
      aria-live="assertive"
      className={cn(
        "fixed inset-x-0 bottom-20 z-50 mx-auto w-fit",
        "flex items-center gap-2 rounded-full border border-destructive/30 bg-destructive/10 px-4 py-2 shadow-lg backdrop-blur-sm",
        "animate-in",
      )}
    >
      <WifiOff className="h-4 w-4 text-destructive" />
      <span className="text-sm font-medium text-destructive">
        اتصال اینترنت قطع شده
      </span>
    </div>
  );
}
