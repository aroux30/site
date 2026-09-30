/**
 * Checkout Step Interaction Timing & Funnel Analytics
 * Tracks duration spent on each step of the checkout flow (address, shipping, payment, review),
 * correlated with W3C Trace IDs.
 */

import { getActiveTraceId } from "./tracer";
import { logger } from "./logger";
import { trackEvent } from "./events";

// ponytail: in-memory funnel step accumulator -> skipped: session drop-off machine learning predictor, add when checkout abandon predictions needed.

export type CheckoutStepName =
  | "address"
  | "shipping"
  | "payment"
  | "review"
  | "confirmation"
  | (string & {});

export interface CheckoutStepRecord {
  step: CheckoutStepName;
  durationMs: number;
  timestamp: number;
  traceId: string;
  cartId?: string | null;
  meta?: Record<string, unknown>;
}

export interface CheckoutFunnelSummary {
  totalDurationMs: number;
  stepDurations: Record<string, number>;
  completedSteps: string[];
}

const MAX_STEP_HISTORY = 50;
const stepHistory: CheckoutStepRecord[] = [];

let currentStepState: {
  step: CheckoutStepName;
  startTime: number;
  cartId?: string | null;
} | null = null;

/**
 * Starts measuring interaction time for a specific checkout step.
 */
export function startCheckoutStep(
  step: CheckoutStepName,
  cartId?: string | null,
): void {
  const now =
    typeof performance !== "undefined" ? performance.now() : Date.now();

  currentStepState = {
    step,
    startTime: now,
    cartId,
  };
}

/**
 * Completes the active checkout step, calculates elapsed duration, logs metrics, and emits funnel events.
 */
export function completeCheckoutStep(
  step?: CheckoutStepName,
  meta?: Record<string, unknown>,
  startTimeOverride?: number,
): CheckoutStepRecord | null {
  const now =
    typeof performance !== "undefined" ? performance.now() : Date.now();
  const effectiveStep = step || currentStepState?.step || "unknown";
  const startTime =
    startTimeOverride ?? currentStepState?.startTime ?? now - 50;
  const durationMs = Math.max(0, Math.round((now - startTime) * 100) / 100);
  const traceId = getActiveTraceId();
  const cartId = currentStepState?.cartId;

  const record: CheckoutStepRecord = {
    step: effectiveStep,
    durationMs,
    timestamp: Date.now(),
    traceId,
    cartId,
    meta,
  };

  stepHistory.push(record);
  if (stepHistory.length > MAX_STEP_HISTORY) {
    stepHistory.shift();
  }

  // Structured log for checkout funnel observability
  logger.info(
    `[Checkout Funnel] Step completed: ${effectiveStep} (${durationMs}ms)`,
    {
      checkoutStep: effectiveStep,
      durationMs,
      traceId,
      cartId,
      ...meta,
    },
  );

  // Dispatch business funnel event
  trackEvent(`checkout.step_${effectiveStep}_completed`, {
    step: effectiveStep,
    durationMs,
    cartId,
    ...meta,
  });

  currentStepState = null;
  return record;
}

/**
 * Calculates aggregate summary of checkout steps duration.
 */
export function getCheckoutFunnelSummary(): CheckoutFunnelSummary {
  const stepDurations: Record<string, number> = {};
  let totalDurationMs = 0;
  const completedSteps: string[] = [];

  for (const record of stepHistory) {
    stepDurations[record.step] =
      (stepDurations[record.step] || 0) + record.durationMs;
    totalDurationMs += record.durationMs;
    if (!completedSteps.includes(record.step)) {
      completedSteps.push(record.step);
    }
  }

  return {
    totalDurationMs: Math.round(totalDurationMs * 100) / 100,
    stepDurations,
    completedSteps,
  };
}

/**
 * Returns list of recorded checkout step interactions.
 */
export function getCheckoutStepHistory(): CheckoutStepRecord[] {
  return [...stepHistory];
}

/**
 * Clears checkout history (useful for test isolation).
 */
export function clearCheckoutStepHistory(): void {
  stepHistory.length = 0;
  currentStepState = null;
}
