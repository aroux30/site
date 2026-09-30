/**
 * Shipment Tracking State Machine & RMA Window Integration (Sprint 3 Phase 2)
 */

import { checkReturnEligibility } from "./rma";
import { toPersianDigits } from "./utils";

export type ShipmentStatus = "PENDING" | "SHIPPED" | "IN_TRANSIT" | "DELIVERED";

export const SHIPMENT_STATUS_STEPS: readonly ShipmentStatus[] = [
  "PENDING",
  "SHIPPED",
  "IN_TRANSIT",
  "DELIVERED",
] as const;

export const SHIPMENT_STATUS_LABELS: Record<ShipmentStatus, string> = {
  PENDING: "در انتظار ارسال",
  SHIPPED: "تحویل به شرکت پستی",
  IN_TRANSIT: "در مسیر توزیع",
  DELIVERED: "تحویل به گیرنده",
};

export const SHIPMENT_STATUS_DESCRIPTIONS: Record<ShipmentStatus, string> = {
  PENDING: "مرسوله بسته‌بندی شده و در انتظار جمع‌آوری توسط مامور ارسال است.",
  SHIPPED: "مرسوله تحویل باجه پستی / شرکت حمل‌ونقل گردید.",
  IN_TRANSIT: "مرسوله در مرکز تجزیه و مبادلات پستی در حال انتقال به مقصد است.",
  DELIVERED: "مرسوله با موفقیت تحویل گیرنده گردید.",
};

export interface ShipmentTrackingEvent {
  status: ShipmentStatus;
  timestamp: string;
  location?: string;
  description?: string;
}

export interface ShipmentDetails {
  orderId: string;
  trackingCode?: string | null;
  carrier?: string | null;
  status: ShipmentStatus;
  deliveredAt?: string | null;
  events?: ShipmentTrackingEvent[];
}

export interface ReturnWindowCountdown {
  isOpen: boolean;
  daysRemaining: number;
  label: string;
}

/**
 * Returns the 0-indexed step index for a shipment status.
 */
export function getShipmentStepIndex(status: string | null | undefined): number {
  if (!status) return 0;
  const upper = status.trim().toUpperCase();
  switch (upper) {
    case "PENDING":
    case "PROCESSING":
    case "CONFIRMED":
      return 0;
    case "SHIPPED":
      return 1;
    case "IN_TRANSIT":
      return 2;
    case "DELIVERED":
      return 3;
    default:
      return 0;
  }
}

/**
 * Normalizes general order status or raw shipment status to the 4-stage shipment state machine.
 *
 * Accepts both backend vocabularies, since the stepper is fed an order status
 * in one place and a shipment status in another:
 *  - OrderStatus  (orders/domain/models.py): pending, confirmed, processing,
 *    packing, shipped, delivered, completed, canceled, on_hold, returned, …
 *  - ShipmentStatus (shipping/domain/models.py): pending, processing, shipped,
 *    in_transit, delivered, returned, cancelled
 * A completed order had its parcel delivered and then closed; without this it
 * fell through to PENDING and the tracking UI told the customer the parcel was
 * still awaiting dispatch.
 */
export function resolveShipmentStatus(
  rawStatus: string | null | undefined
): ShipmentStatus {
  if (!rawStatus) return "PENDING";
  const upper = rawStatus.trim().toUpperCase();
  if (upper === "IN_TRANSIT") return "IN_TRANSIT";
  if (upper === "DELIVERED" || upper === "COMPLETED") return "DELIVERED";
  if (upper === "SHIPPED") return "SHIPPED";
  return "PENDING";
}

/**
 * Evaluates the 7-day RMA countdown window once an order reaches DELIVERED status.
 */
export function getReturnWindowCountdown(
  status: string | null | undefined,
  deliveredAt: string | Date | null | undefined,
  now: Date = new Date()
): ReturnWindowCountdown {
  const normStatus = resolveShipmentStatus(status);
  if (normStatus !== "DELIVERED") {
    return {
      isOpen: false,
      daysRemaining: 0,
      label: "سفارش هنوز تحویل داده نشده است",
    };
  }

  const eligibility = checkReturnEligibility("delivered", deliveredAt, now);
  if (eligibility.isEligible) {
    return {
      isOpen: true,
      daysRemaining: eligibility.daysRemaining,
      label: `${toPersianDigits(eligibility.daysRemaining)} روز از مهلت قانونی مرجوعی باقی مانده است`,
    };
  }

  return {
    isOpen: false,
    daysRemaining: 0,
    label: "مهلت ۷ روزه مرجوعی به پایان رسیده است",
  };
}
