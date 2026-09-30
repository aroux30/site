/**
 * Customer return requests (RMA) — admin processing.
 *
 * Contract: backend/app/modules/orders/api/routes.py +
 *           domain/returns.py (state machine) + schemas/order.py
 *   GET  /orders/admin/returns                 — orders:read
 *   POST /orders/admin/returns/{id}/transition — orders:write
 *
 * RMA is a state machine, not a free-form status field. The backend validates
 * every move against `RETURN_TRANSITIONS` and rejects an illegal one, so this
 * module mirrors that table to offer ONLY the transitions the backend will
 * accept. Offering a move the server refuses would look like a platform bug to
 * the operator, when the rule is simply that the return is not there yet.
 *
 * `refund_amount` is integer rials and only meaningful on the `refunded` move.
 * Nothing here moves money by itself; the refund is posted by the backend's
 * transition handler.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const RETURNS_ADMIN_PATH = "/orders/admin/returns";

export const RETURN_STATUSES = [
  "requested",
  "under_review",
  "approved",
  "rejected",
  "received",
  "inspected",
  "refunded",
  "replaced",
  "closed",
] as const;
export type ReturnStatus = (typeof RETURN_STATUSES)[number];

export const RETURN_STATUS_LABELS: Record<string, string> = {
  requested: "ثبت‌شده",
  under_review: "در حال بررسی",
  approved: "تأییدشده",
  rejected: "ردشده",
  received: "دریافت‌شده",
  inspected: "بازرسی‌شده",
  refunded: "بازپرداخت‌شده",
  replaced: "جایگزین‌شده",
  closed: "بسته‌شده",
};

export function returnStatusLabel(status: string): string {
  return RETURN_STATUS_LABELS[status] ?? status;
}

/**
 * Valid transitions, mirroring `RETURN_TRANSITIONS` in the backend domain.
 * Kept identical on purpose: the UI must not offer a move the server rejects.
 */
export const RETURN_TRANSITIONS: Record<string, readonly string[]> = {
  requested: ["under_review", "approved", "rejected"],
  under_review: ["approved", "rejected"],
  approved: ["received", "closed"],
  rejected: ["closed"],
  received: ["inspected"],
  inspected: ["refunded", "replaced", "rejected"],
  refunded: ["closed"],
  replaced: ["closed"],
  closed: [],
};

export function allowedReturnTransitions(status: string): string[] {
  return [...(RETURN_TRANSITIONS[status] ?? [])];
}

export const INSPECTION_OUTCOMES = [
  "passed",
  "damaged_by_customer",
  "defective_confirmed",
] as const;

export const INSPECTION_OUTCOME_LABELS: Record<string, string> = {
  passed: "سالم و قابل‌فروش",
  damaged_by_customer: "آسیب از سوی مشتری (مشمول بازپرداخت نیست)",
  defective_confirmed: "عارضه تأییدشده کارخانه",
};

export function inspectionOutcomeLabel(outcome: string): string {
  return INSPECTION_OUTCOME_LABELS[outcome] ?? outcome;
}

export interface ReturnItem {
  orderItemId: string;
  variantId: string;
  quantity: number | null;
  reason: string;
  customerNotes: string | null;
  inspectionOutcome: string | null;
}

export interface OrderReturn {
  id: string;
  rmaNumber: string | null;
  orderId: string;
  userId: string;
  status: string;
  items: ReturnItem[];
  createdAt: string | null;
  approvedAt: string | null;
  inspectedAt: string | null;
  refundedAt: string | null;
  adminNotes: string | null;
  /** Integer rials. */
  refundAmount: number | null;
}

export interface ReturnPage {
  items: OrderReturn[];
  total: number | null;
  page: number;
  pageSize: number;
  /** Records returned that could not be read as returns. Never silent. */
  invalidCount: number;
  /**
   * Returns the backend holds but this read did not return. A list showing 50
   * of 80 open returns without saying so reads as complete, and the ones it
   * hides are the promises the merchant has to honour.
   */
  missingCount: number | null;
}

export interface ReturnTransitionPayload {
  target: string;
  notes?: string | null;
  /** {order_item_id: passed | damaged_by_customer | defective_confirmed} */
  inspectionOutcomes?: Record<string, string> | null;
  /** Integer rials; only sent on the `refunded` move. */
  refundAmount?: number | null;
}

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

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function normalizeItem(raw: unknown): ReturnItem | null {
  const r = readRecord(raw);
  if (!r) return null;
  const orderItemId = readString(r.order_item_id);
  if (!orderItemId) return null;
  return {
    orderItemId,
    variantId: readString(r.variant_id) ?? "",
    quantity: readInt(r.quantity),
    reason: readString(r.reason) ?? "",
    customerNotes: readString(r.customer_notes),
    inspectionOutcome: readString(r.inspection_outcome),
  };
}

export function normalizeReturn(raw: unknown): OrderReturn | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  const orderId = readString(r.order_id);
  if (!id || !orderId) return null;

  const records = Array.isArray(r.items) ? r.items : [];
  const items: ReturnItem[] = [];
  for (const rawItem of records) {
    const item = normalizeItem(rawItem);
    if (item) items.push(item);
  }

  return {
    id,
    rmaNumber: readString(r.rma_number),
    orderId,
    userId: readString(r.user_id) ?? "",
    status: readString(r.status) ?? "requested",
    items,
    createdAt: readString(r.created_at),
    approvedAt: readString(r.approved_at),
    inspectedAt: readString(r.inspected_at),
    refundedAt: readString(r.refunded_at),
    adminNotes: readString(r.admin_notes),
    refundAmount: readInt(r.refund_amount),
  };
}

export async function fetchReturns(
  params: { page?: number; pageSize?: number; status?: string } = {},
  client: AxiosInstance = apiClient,
): Promise<ReturnPage> {
  const res = await client.get<unknown>(RETURNS_ADMIN_PATH, {
    params: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      ...(params.status && params.status !== "all" ? { status: params.status } : {}),
    },
  });
  const r = readRecord(res.data) ?? {};
  const records = Array.isArray(r.items) ? r.items : [];
  const items: OrderReturn[] = [];
  let invalidCount = 0;
  for (const raw of records) {
    const item = normalizeReturn(raw);
    if (item) items.push(item);
    else invalidCount += 1;
  }
  const total = readInt(r.total);
  return {
    items,
    total,
    page: readInt(r.page) ?? 1,
    pageSize: readInt(r.page_size) ?? items.length,
    invalidCount,
    missingCount: total === null ? null : Math.max(0, total - records.length),
  };
}

export async function transitionReturn(
  returnId: string,
  payload: ReturnTransitionPayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  const body: Record<string, unknown> = { target: payload.target };
  if (payload.notes !== undefined) body.notes = payload.notes;
  if (payload.inspectionOutcomes) body.inspection_outcomes = payload.inspectionOutcomes;
  if (payload.refundAmount !== undefined && payload.refundAmount !== null) {
    body.refund_amount = Math.trunc(payload.refundAmount);
  }
  await client.post(`${RETURNS_ADMIN_PATH}/${returnId}/transition`, body);
}
