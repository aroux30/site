/**
 * Client Business Funnels & Domain Event Tracking
 * Dispatches business events (product.viewed, cart.item_added, checkout.started)
 * correlated with W3C Trace IDs.
 */

import { getActiveTraceId } from "./tracer";
import { logger } from "./logger";

// ponytail: in-memory business events buffer -> skipped: persistent analytics warehouse sync, add when client-side BI warehouse needed.

export interface BusinessEvent {
  event: string;
  traceId: string;
  timestamp: string;
  properties: Record<string, unknown>;
  url?: string;
}

const MAX_EVENT_HISTORY = 200;
const eventHistory: BusinessEvent[] = [];

/**
 * Tracks a business event with trace context correlation.
 */
export function trackEvent(
  eventName: string,
  properties: Record<string, unknown> = {},
): BusinessEvent {
  const traceId = getActiveTraceId();
  const event: BusinessEvent = {
    event: eventName,
    traceId,
    timestamp: new Date().toISOString(),
    properties,
    url: typeof window !== "undefined" ? window.location.href : undefined,
  };

  eventHistory.push(event);
  if (eventHistory.length > MAX_EVENT_HISTORY) {
    eventHistory.shift();
  }

  // Structured logging for business funnel observability
  logger.info(`[Funnel] ${eventName}`, {
    funnelEvent: eventName,
    traceId,
    ...properties,
  });

  // Browser-level event dispatch for external listeners (e.g. tag managers)
  if (
    typeof window !== "undefined" &&
    typeof window.dispatchEvent === "function"
  ) {
    try {
      window.dispatchEvent(
        new CustomEvent("karta:event", {
          detail: event,
        }),
      );
    } catch {
      // Ignore errors in custom event dispatching
    }
  }

  return event;
}

/**
 * Helper to track product page views
 */
export function trackProductViewed(product: {
  id: string;
  title: string;
  price?: number;
  category?: string;
  slug?: string;
}): BusinessEvent {
  return trackEvent("product.viewed", {
    productId: product.id,
    title: product.title,
    price: product.price,
    category: product.category,
    slug: product.slug,
  });
}

/**
 * Helper to track adding items to cart
 */
export function trackCartItemAdded(item: {
  productId: string;
  variantId?: string;
  quantity: number;
  price?: number;
  title?: string;
}): BusinessEvent {
  return trackEvent("cart.item_added", {
    productId: item.productId,
    variantId: item.variantId,
    quantity: item.quantity,
    price: item.price,
    title: item.title,
  });
}

/**
 * Helper to track initiating the checkout process
 */
export function trackCheckoutStarted(checkout: {
  cartId?: string | null;
  totalItems: number;
  totalPrice: number;
}): BusinessEvent {
  return trackEvent("checkout.started", {
    cartId: checkout.cartId,
    totalItems: checkout.totalItems,
    totalPrice: checkout.totalPrice,
  });
}

/**
 * Returns recent event history
 */
export function getRecentEvents(): BusinessEvent[] {
  return [...eventHistory];
}

/**
 * Clears event history (useful for test isolation)
 */
export function clearEvents(): void {
  eventHistory.length = 0;
}
