"use client";

import { useEffect, useCallback } from "react";

/**
 * Hook to manage hardware/browser back button behavior on mobile devices (Karta UX).
 *
 * Prevents accidental exit from multi-step checkouts or modal dialogs.
 * When active, pressing the phone's back button executes onBack() instead of leaving the page.
 */
export function useHardwareBackButton(
  isActive: boolean,
  onBack: () => void,
  stepKey: string = "step"
) {
  useEffect(() => {
    if (!isActive || typeof window === "undefined") return;

    // Push a synthetic history state for this step/modal
    const stateId = `sub_view_${stepKey}_${Date.now()}`;
    window.history.pushState({ modal: stateId }, "");

    const handlePopState = (event: PopStateEvent) => {
      // Intercept the back button press and trigger the callback
      onBack();
    };

    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, [isActive, onBack, stepKey]);
}

/**
 * Hook to smoothly scroll the viewport to the first validation error in long forms (Karta UX).
 *
 * Automatically finds the first invalid input element, scrolls to it, and applies focus.
 */
export function useScrollToError() {
  const scrollToFirstError = useCallback((containerSelector: string = "form") => {
    if (typeof document === "undefined") return;

    const container = document.querySelector(containerSelector) || document;

    // Look for common invalid attribute selectors
    const firstInvalid = container.querySelector(
      '[aria-invalid="true"], :invalid, .input-error, [data-error="true"]'
    ) as HTMLElement | null;

    if (firstInvalid) {
      firstInvalid.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });

      // Focus the input element if focusable
      if (typeof firstInvalid.focus === "function") {
        firstInvalid.focus({ preventScroll: true });
      }
    }
  }, []);

  return { scrollToFirstError };
}
