/**
 * A single order, as its owner sees it.
 *
 * Contract: backend/app/modules/orders/api/routes.py
 *   GET  /orders/{id}                → OrderResponse (includes items + timeline)
 *   GET  /orders/{id}/timeline       → OrderTimelineResponse
 *   GET  /orders/{id}/price-snapshot → PriceSnapshotResponse (has hash_valid)
 *   GET  /orders/{id}/returns        → list of RMAs for this order
 *   POST /orders/{id}/cancel         → OrderResponse (body: {reason, min 3 chars})
 *
 * Two contract facts this module is explicit about:
 *
 * 1. `shipping_address_snapshot` is **masked by the server** before it reaches
 *    the client (see the `mask_shipping_address` validator). This client does
 *    not unmask or reconstruct it; what the backend sends is what is shown.
 * 2. The price snapshot carries a `hash_valid` flag computed server-side
 *    against the stored SHA-256. A `false` value means the stored pricing no
 *    longer matches its own hash — a tamper signal that must be surfaced to the
 *    customer, never hidden. This module preserves `null` (not reported) as
 *    distinct from `false` (reported and failed).
 *
 * Every amount is integer rials.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const ORDERS_PATH = "/orders";

export interface OrderItem {
  id: string;
  variantId: string;
  productName: string;
  variantInfo: string | null;
  sku: string;
  quantity: number | null;
  /** Integer rials. */
  unitPrice: number | null;
  /** Integer rials. */
  totalPrice: number | null;
}

export interface OrderEvent {
  id: string;
  fromStatus: string | null;
  toStatus: string;
  reason: string | null;
  createdAt: string | null;
}

export interface OrderDetail {
  id: string;
  orderNumber: string;
  status: string;
  /** All amounts integer rials. */
  subtotal: number | null;
  shippingCost: number | null;
  tax: number | null;
  discountAmount: number | null;
  total: number | null;
  shippingAddressMasked: Record<string, unknown> | null;
  notes: string | null;
  items: OrderItem[];
  timeline: OrderEvent[];
  createdAt: string | null;
  updatedAt: string | null;
}

export interface PriceSnapshotLine {
  variantId: string;
  productName: string;
  quantity: number | null;
  unitPriceRial: number | null;
  lineTotalRial: number | null;
  discountAmountRial: number | null;
  discountCode: string | null;
  taxAmountRial: number | null;
  taxRatePercent: number | null;
}

export interface PriceSnapshot {
  id: string;
  currency: string;
  lines: PriceSnapshotLine[];
  subtotalRial: number | null;
  totalDiscountRial: number | null;
  totalTaxRial: number | null;
  shippingRial: number | null;
  grandTotalRial: number | null;
  snapshotHash: string | null;
  /** true = verified, false = mismatch (tamper signal), null = not reported. */
  hashValid: boolean | null;
  createdAt: string | null;
}

export interface OrderRma {
  id: string;
  rmaNumber: string | null;
  status: string;
  refundAmount: number | null;
  createdAt: string | null;
  adminNotes: string | null;
}

// NOTE: normalizeRma is intentionally RETAINED (unused) rather than deleted.
// The RMA card on the order page was removed because no backend endpoint
// lists an order's returns. When such an endpoint exists, the normalizer is
// the piece that parses it — and these lines are the reminder that its
// response shape is INFERRED, not yet verified against a live server.

function readString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function readInt(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === "string" && /^-?\d+$/.test(value.trim())) {
    return Number.parseInt(value.trim(), 10);
  }
  return null;
}

function readBool(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function normalizeItem(raw: unknown): OrderItem | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  if (!id) return null;
  return {
    id,
    variantId: readString(r.variant_id) ?? "",
    productName: readString(r.product_name) ?? "",
    variantInfo: readString(r.variant_info),
    sku: readString(r.sku) ?? "",
    quantity: readInt(r.quantity),
    unitPrice: readInt(r.unit_price),
    totalPrice: readInt(r.total_price),
  };
}

function normalizeEvent(raw: unknown): OrderEvent | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  const toStatus = readString(r.to_status);
  if (!id || !toStatus) return null;
  return {
    id,
    fromStatus: readString(r.from_status),
    toStatus,
    reason: readString(r.reason),
    createdAt: readString(r.created_at),
  };
}

export function normalizeOrder(raw: unknown): OrderDetail | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  if (!id) return null;

  const items: OrderItem[] = [];
  for (const rawItem of Array.isArray(r.items) ? r.items : []) {
    const item = normalizeItem(rawItem);
    if (item) items.push(item);
  }
  const timeline: OrderEvent[] = [];
  for (const rawEvent of Array.isArray(r.timeline) ? r.timeline : []) {
    const event = normalizeEvent(rawEvent);
    if (event) timeline.push(event);
  }

  return {
    id,
    orderNumber: readString(r.order_number) ?? "",
    status: readString(r.status) ?? "unknown",
    subtotal: readInt(r.subtotal),
    shippingCost: readInt(r.shipping_cost),
    tax: readInt(r.tax),
    discountAmount: readInt(r.discount_amount),
    total: readInt(r.total),
    shippingAddressMasked: readRecord(r.shipping_address_snapshot),
    notes: readString(r.notes),
    items,
    timeline,
    createdAt: readString(r.created_at),
    updatedAt: readString(r.updated_at),
  };
}

export function normalizeSnapshot(raw: unknown): PriceSnapshot | null {
  const r = readRecord(raw);
  if (!r) return null;
  const lines: PriceSnapshotLine[] = [];
  for (const rawLine of Array.isArray(r.lines) ? r.lines : []) {
    const l = readRecord(rawLine);
    if (!l) continue;
    lines.push({
      variantId: readString(l.variant_id) ?? "",
      productName: readString(l.product_name) ?? "",
      quantity: readInt(l.quantity),
      unitPriceRial: readInt(l.unit_price_rial),
      lineTotalRial: readInt(l.line_total_rial),
      discountAmountRial: readInt(l.discount_amount_rial),
      discountCode: readString(l.discount_code),
      taxAmountRial: readInt(l.tax_amount_rial),
      taxRatePercent: readInt(l.tax_rate_percent),
    });
  }
  return {
    id: readString(r.id) ?? "",
    currency: readString(r.currency) ?? "IRR",
    lines,
    subtotalRial: readInt(r.subtotal_rial),
    totalDiscountRial: readInt(r.total_discount_rial),
    totalTaxRial: readInt(r.total_tax_rial),
    shippingRial: readInt(r.shipping_rial),
    grandTotalRial: readInt(r.grand_total_rial),
    snapshotHash: readString(r.snapshot_hash),
    hashValid: readBool(r.hash_valid),
    createdAt: readString(r.created_at),
  };
}

export function normalizeRma(raw: unknown): OrderRma | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  if (!id) return null;
  return {
    id,
    rmaNumber: readString(r.rma_number),
    status: readString(r.status) ?? "unknown",
    refundAmount: readInt(r.refund_amount),
    createdAt: readString(r.created_at),
    adminNotes: readString(r.admin_notes),
  };
}

export async function fetchOrderDetail(
  orderId: string,
  client: AxiosInstance = apiClient,
): Promise<OrderDetail | null> {
  const res = await client.get<unknown>(`${ORDERS_PATH}/${orderId}`);
  return normalizeOrder(res.data);
}

export async function fetchPriceSnapshot(
  orderId: string,
  client: AxiosInstance = apiClient,
): Promise<PriceSnapshot | null> {
  const res = await client.get<unknown>(`${ORDERS_PATH}/${orderId}/price-snapshot`);
  return normalizeSnapshot(res.data);
}

export async function fetchOrderReturns(
  orderId: string,
  client: AxiosInstance = apiClient,
): Promise<{ items: OrderRma[]; invalidCount: number }> {
  try {
    const res = await client.get<unknown>(`${ORDERS_PATH}/${orderId}/returns`);
    const rawList = Array.isArray(res.data) ? res.data : [];
    const items: OrderRma[] = [];
    let invalidCount = 0;
    for (const r of rawList) {
      const normalized = normalizeRma(r);
      if (normalized) {
        items.push(normalized);
      } else {
        invalidCount += 1;
      }
    }
    return { items, invalidCount };
  } catch {
    return { items: [], invalidCount: 0 };
  }
}

export async function cancelOrder(
  orderId: string,
  reason: string,
  client: AxiosInstance = apiClient,
): Promise<void> {
  // The backend requires at least 3 characters; an empty reason is rejected
  // with a 422, so the page validates before calling this.
  await client.post(`${ORDERS_PATH}/${orderId}/cancel`, { reason: reason.trim() });
}

/** Statuses an order can be cancelled from, mirroring the order state machine.
 *  Mirrors `_CUSTOMER_CANCELABLE` in backend order_service.py exactly. */
export const CANCELLABLE_STATUSES = ["pending", "confirmed"] as const;

export function isCancellable(status: string): boolean {
  return (CANCELLABLE_STATUSES as readonly string[]).includes(status);
}

// Keys mirror OrderStatus in backend/app/modules/orders/domain/models.py exactly.
// The backend serialises enum *values* (lowercase), so `canceled` — not
// `cancelled` — is the value that actually arrives; a missing key here falls
// through to orderStatusLabel and shows the raw English enum to the customer.
export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: "در انتظار پرداخت",
  confirmed: "تأییدشده",
  processing: "در حال پردازش",
  packing: "در حال بسته‌بندی",
  shipped: "ارسال‌شده",
  delivered: "تحویل‌شده",
  completed: "تکمیل‌شده",
  canceled: "لغوشده",
  on_hold: "در انتظار بررسی",
  returned: "مرجوع‌شده",
  refunded: "بازپرداخت‌شده",
  partially_refunded: "بازپرداخت جزئی",
};

export function orderStatusLabel(status: string): string {
  return ORDER_STATUS_LABELS[status] ?? status;
}
