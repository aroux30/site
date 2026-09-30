"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { getActiveTraceId } from "./tracer";
import { logger } from "./logger";
import { metrics } from "./metrics";

// ponytail: in-memory route history buffer -> skipped: persistent navigation breadcrumb database, add when session replay export needed.

export const SLOW_ROUTE_THRESHOLD_MS = 1000;

export interface RouteTransitionRecord {
  from: string;
  to: string;
  durationMs: number;
  timestamp: number;
  traceId: string;
  isSlow: boolean;
}

const MAX_ROUTE_HISTORY = 100;
const routeHistory: RouteTransitionRecord[] = [];

let activeTransition: {
  from: string;
  to: string;
  startTime: number;
} | null = null;

/**
 * Manually marks the start of a route transition.
 */
export function startRouteTransition(toPath: string, fromPath?: string): void {
  const currentPath =
    fromPath ||
    (typeof window !== "undefined" ? window.location.pathname : "/");
  const startTime =
    typeof performance !== "undefined" ? performance.now() : Date.now();

  activeTransition = {
    from: currentPath,
    to: toPath,
    startTime,
  };
}

/**
 * Completes an active route transition, computes latency, records metrics, and logs warnings for slow routes.
 */
export function completeRouteTransition(
  toPath: string,
  startTimeOverride?: number,
): RouteTransitionRecord | null {
  const now =
    typeof performance !== "undefined" ? performance.now() : Date.now();
  const startTime =
    startTimeOverride ?? activeTransition?.startTime ?? now - 10;
  const fromPath = activeTransition?.from || "/";
  const durationMs = Math.max(0, Math.round((now - startTime) * 100) / 100);
  const traceId = getActiveTraceId();
  const isSlow = durationMs >= SLOW_ROUTE_THRESHOLD_MS;

  const record: RouteTransitionRecord = {
    from: fromPath,
    to: toPath,
    durationMs,
    timestamp: Date.now(),
    traceId,
    isSlow,
  };

  routeHistory.push(record);
  if (routeHistory.length > MAX_ROUTE_HISTORY) {
    routeHistory.shift();
  }

  // Record in metrics collector
  metrics.recordPageNavigation(toPath, durationMs);

  // Log transition status
  if (isSlow) {
    logger.warn(
      `slow_route_transition: Navigation to ${toPath} took ${durationMs}ms`,
      {
        event: "slow_route_transition",
        from: fromPath,
        to: toPath,
        durationMs,
        traceId,
      },
    );
  } else {
    logger.debug(
      `Route transition: ${fromPath} -> ${toPath} (${durationMs}ms)`,
      {
        from: fromPath,
        to: toPath,
        durationMs,
        traceId,
      },
    );
  }

  activeTransition = null;
  return record;
}

/**
 * Returns list of recorded route transitions.
 */
export function getRecentRouteTransitions(): RouteTransitionRecord[] {
  return [...routeHistory];
}

/**
 * Clears transition history (useful for testing).
 */
export function clearRouteTransitions(): void {
  routeHistory.length = 0;
  activeTransition = null;
}

/**
 * React hook that monitors pathname changes and tracks transition duration.
 */
export function useRouteTiming(): {
  currentPath: string;
  transitionCount: number;
} {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const prevPathRef = useRef<string | null>(null);
  const startTimeRef = useRef<number>(
    typeof performance !== "undefined" ? performance.now() : Date.now(),
  );
  const [transitionCount, setTransitionCount] = useState(0);

  const fullPath =
    pathname + (searchParams?.toString() ? `?${searchParams.toString()}` : "");

  useEffect(() => {
    if (prevPathRef.current !== null && prevPathRef.current !== fullPath) {
      completeRouteTransition(fullPath, startTimeRef.current);
      setTransitionCount((c) => c + 1);
    }

    prevPathRef.current = fullPath;
    startTimeRef.current =
      typeof performance !== "undefined" ? performance.now() : Date.now();
  }, [fullPath]);

  return { currentPath: fullPath, transitionCount };
}

/**
 * Self-contained client watcher component for monitoring route changes.
 */
export function RouteTimingWatcher() {
  useRouteTiming();
  return null;
}
