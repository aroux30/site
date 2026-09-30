/**
 * The customer's own cashback history.
 *
 * Contract: backend/app/modules/cashback/api/routes.py + schemas/cashback.py
 *   GET /cashback/transactions?skip=&limit=    (authenticated customer)
 *   → { items: [{id, user_id, order_id, rule_id, amount, status, created_at}], total }
 *
 * The endpoint is **paginated**, so this client reports the shortfall when the
 * backend holds more rows than were loaded. A customer who cannot see older
 * cashback entries has no way to tell whether they were ever credited.
 *
 * `amount` is integer rials, as everywhere else in this codebase. Nothing here
 * sums or converts it; the page displays what the server reported.
 *
 * Note this is the CUSTOMER surface. Admin cashback rules are a different
 * resource and live in `lib/api/cashback.ts`.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const CASHBACK_TRANSACTIONS_PATH = "/cashback/transactions";

export const CASHBACK_STATUSES = ["pending", "credited", "expired"] as const;
export type CashbackStatus = (typeof CASHBACK_STATUSES)[number];

export const CASHBACK_STATUS_LABELS: Record<string, string> = {
  pending: "در انتظار اعمال",
  credited: "واریزشده",
  expired: "منقضی‌شده",
};

export function cashbackStatusLabel(status: string): string {
  return CASHBACK_STATUS_LABELS[status] ?? status;
}

export function cashbackStatusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" | "success" | "warning" {
  if (status === "credited") return "success";
  if (status === "pending") return "warning";
  if (status === "expired") return "outline";
  return "secondary";
}

export interface CashbackTransaction {
  id: string;
  orderId: string;
  ruleId: string;
  /** Integer rials, as reported. */
  amount: number | null;
  status: string;
  createdAt: string | null;
}

export interface CashbackHistory {
  items: CashbackTransaction[];
  /** Total rows the backend holds. Null when it did not report one. */
  total: number | null;
  /** Rows returned that could not be read. Never dropped silently. */
  invalidCount: number;
  /** Rows that exist but were not loaded (pagination). Null if total unknown. */
  missingCount: number | null;
  /**
   * Rows **after this page** — i.e. older entries the customer has not seen
   * yet, because the API sorts newest-first.
   *
   * This is NOT `missingCount`. On page 3 of 3 the unloaded rows are the
   * ones the customer already read on pages 1-2, so reporting them as "older
   * entries not shown" would be a false statement about their own history.
   * Derived from the offset actually requested, so it is correct on any page.
   */
  olderCount: number | null;
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

export function normalizeTransaction(raw: unknown): CashbackTransaction | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  if (!id) return null;
  return {
    id,
    orderId: readString(r.order_id) ?? "",
    ruleId: readString(r.rule_id) ?? "",
    amount: readInt(r.amount),
    status: readString(r.status) ?? "unknown",
    createdAt: readString(r.created_at),
  };
}

export async function fetchCashbackHistory(
  params: { skip?: number; limit?: number } = {},
  client: AxiosInstance = apiClient,
): Promise<CashbackHistory> {
  const skip = params.skip ?? 0;
  const limit = params.limit ?? 20;
  const res = await client.get<unknown>(CASHBACK_TRANSACTIONS_PATH, {
    params: { skip, limit },
  });
  const envelope = readRecord(res.data) ?? {};
  const records = Array.isArray(envelope.items) ? envelope.items : [];
  const items: CashbackTransaction[] = [];
  let invalidCount = 0;
  for (const raw of records) {
    const tx = normalizeTransaction(raw);
    if (tx) items.push(tx);
    else invalidCount += 1;
  }
  const total = readInt(envelope.total);
  return {
    items,
    total,
    invalidCount,
    // Compare against what was actually returned, so a page of 20 out of 45
    // is stated rather than silently presented as the whole history.
    missingCount: total === null ? null : Math.max(0, total - records.length),
    // Rows beyond this page. The API sorts newest-first, so everything after
    // the requested offset is OLDER than what is on screen. On the last page
    // this is 0 — nothing is being hidden from the customer.
    olderCount:
      total === null ? null : Math.max(0, total - (skip + records.length)),
  };
}
