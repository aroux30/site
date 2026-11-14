/**
 * Order Progress Tracking — Digital Store Model
 *
 * Replaced the old 4-step physical-shipment stepper (PENDING → SHIPPED →
 * IN_TRANSIT → DELIVERED) with an order-lifecycle stepper that mirrors the
 * actual backend state machine. The old stepper was designed for physical
 * parcels — meaningless for a digital store — and always got stuck on step 1
 * because it was being fed order statuses, not shipment records.
 *
 * The new model shows 5 stages matching the real order pipeline:
 *   1. ثبت سفارش (order placed — payment stage)
 *   2. تایید پرداخت (payment confirmed)
 *   3. بررسی سفارش (processing / verification)
 *   4. تکمیل سفارش (completed)
 *   5. (terminal branches: canceled / refunded shown as banners, not steps)
 *
 * Synced with: backend/app/modules/orders/domain/models.py OrderStatus
 *              frontend/lib/admin/order-domain.ts STATUS_VISUALS
 */

/** The stages a customer sees in the order progress stepper. */
export type OrderProgressStage =
  | "ORDER_PLACED"
  | "PAYMENT_CONFIRMED"
  | "PROCESSING"
  | "COMPLETED";

export const ORDER_PROGRESS_STEPS: readonly OrderProgressStage[] = [
  "ORDER_PLACED",
  "PAYMENT_CONFIRMED",
  "PROCESSING",
  "COMPLETED",
] as const;

export const ORDER_PROGRESS_LABELS: Record<OrderProgressStage, string> = {
  ORDER_PLACED: "ثبت سفارش",
  PAYMENT_CONFIRMED: "تایید پرداخت",
  PROCESSING: "بررسی و پردازش",
  COMPLETED: "تکمیل سفارش",
};

export const ORDER_PROGRESS_DESCRIPTIONS: Record<OrderProgressStage, string> = {
  ORDER_PLACED: "سفارش شما ثبت شده و در انتظار تایید پرداخت است.",
  PAYMENT_CONFIRMED: "پرداخت شما تایید شده و سفارش در صف انجام قرار گرفت.",
  PROCESSING: "سفارش شما در حال بررسی و پردازش توسط تیم ماست.",
  COMPLETED: "سفارش شما با موفقیت تکمیل شد.",
};

/**
 * Maps the real backend order status to the customer-facing progress stage.
 *
 * Every OrderStatus from the backend (8 values) maps to one of 4 progress
 * stages, or to a terminal state (canceled/refunded) handled separately.
 */
export function resolveOrderProgress(
  rawStatus: string | null | undefined,
): { stage: OrderProgressStage; isTerminal: false } | { stage: "canceled" | "refunded"; isTerminal: true } {
  if (!rawStatus) return { stage: "ORDER_PLACED", isTerminal: false };
  const lower = rawStatus.trim().toLowerCase();

  switch (lower) {
    case "waiting_payment_gateway":
    case "waiting_payment_card":
      return { stage: "ORDER_PLACED", isTerminal: false };

    case "pending":
      return { stage: "PAYMENT_CONFIRMED", isTerminal: false };

    case "doing_verified":
    case "processing":
      return { stage: "PROCESSING", isTerminal: false };

    case "completed":
      return { stage: "COMPLETED", isTerminal: false };

    case "canceled":
      return { stage: "canceled", isTerminal: true };

    case "refunded":
      return { stage: "refunded", isTerminal: true };

    default:
      return { stage: "ORDER_PLACED", isTerminal: false };
  }
}

/**
 * Returns the 0-indexed step for the progress stepper UI.
 */
export function getOrderStepIndex(stage: OrderProgressStage): number {
  return ORDER_PROGRESS_STEPS.indexOf(stage);
}

// ── Legacy re-exports (for any code still importing old names) ──────────

/** @deprecated Use OrderProgressStage instead */
export type ShipmentStatus = OrderProgressStage;
/** @deprecated Use ORDER_PROGRESS_STEPS instead */
export const SHIPMENT_STATUS_STEPS = ORDER_PROGRESS_STEPS;
/** @deprecated Use ORDER_PROGRESS_LABELS instead */
export const SHIPMENT_STATUS_LABELS = ORDER_PROGRESS_LABELS;
/** @deprecated Use ORDER_PROGRESS_DESCRIPTIONS instead */
export const SHIPMENT_STATUS_DESCRIPTIONS = ORDER_PROGRESS_DESCRIPTIONS;

/** @deprecated Use resolveOrderProgress instead */
export function resolveShipmentStatus(
  rawStatus: string | null | undefined,
): OrderProgressStage {
  const result = resolveOrderProgress(rawStatus);
  if (result.isTerminal) return "ORDER_PLACED";
  return result.stage;
}

/** @deprecated Use getOrderStepIndex instead */
export function getShipmentStepIndex(status: string | null | undefined): number {
  const result = resolveOrderProgress(status);
  if (result.isTerminal) return 0;
  return getOrderStepIndex(result.stage);
}

export interface ShipmentTrackingEvent {
  status: OrderProgressStage;
  timestamp: string;
  location?: string;
  description?: string;
}

export interface ShipmentDetails {
  orderId: string;
  trackingCode?: string | null;
  carrier?: string | null;
  status: OrderProgressStage;
  deliveredAt?: string | null;
  events?: ShipmentTrackingEvent[];
}
