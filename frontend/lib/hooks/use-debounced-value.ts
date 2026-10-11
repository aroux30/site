"use client";

import { useEffect, useState } from "react";

/**
 * Debounce a rapidly-changing value (typically a search box).
 *
 * The list view re-queries the server on every filter/search change; firing
 * one request per keystroke is what a 350ms debounce is for. The initial
 * value is returned immediately (no delay on mount), and the timer is
 * cleared on every change so only the settled value is ever observed.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
