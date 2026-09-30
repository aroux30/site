/**
 * Cashback rules (admin).
 *
 * Contract: backend/app/modules/cashback/api/routes.py + schemas/cashback.py
 *   GET    /cashback/admin/rules           — cashback:read
 *   GET    /cashback/admin/rules/{id}      — cashback:read
 *   POST   /cashback/admin/rules           — cashback:write
 *   PATCH  /cashback/admin/rules/{id}      — cashback:write
 *   DELETE /cashback/admin/rules/{id}      — cashback:write (soft-deactivate)
 *
 * The percentage is the one field with two spellings on this contract and it is
 * deliberate: writes take `percentage` as a percent (0 < p <= 100), while the
 * response carries the stored integer `percentage_bp` (1% = 100 bp) plus a
 * computed `percentage` for display. The form therefore converts at the call
 * site and this module never guesses which unit a bare number is in.
 *
 * `DELETE` is a soft-deactivate — it flips `is_active` off and keeps the rule
 * and its history. The admin UI presents it as "deactivate", not "delete",
 * because no row is removed.
 *
 * All amounts are integer rials.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const CASHBACK_RULES_PATH = "/cashback/admin/rules";

export const CASHBACK_RULE_TYPES = [
  "payment_method",
  "customer_segment",
  "product",
  "category",
  "campaign",
] as const;
export type CashbackRuleType = (typeof CASHBACK_RULE_TYPES)[number];

export const CASHBACK_RULE_TYPE_LABELS: Record<string, string> = {
  payment_method: "روش پرداخت",
  customer_segment: "بخش مشتریان",
  product: "کالا",
  category: "دسته‌بندی",
  campaign: "کمپین",
};

export function cashbackRuleTypeLabel(type: string): string {
  return CASHBACK_RULE_TYPE_LABELS[type] ?? type;
}

export interface CashbackRule {
  id: string;
  name: string;
  type: string;
  scopeId: string | null;
  /** Integer basis points (1% = 100 bp). */
  percentageBp: number | null;
  /** Percent view of the same value, as the backend computes it. */
  percentage: number | null;
  /** Integer rials. */
  maxAmount: number | null;
  isActive: boolean;
  startsAt: string | null;
  endsAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface CashbackRulePage {
  items: CashbackRule[];
  total: number | null;
  /** Records returned that could not be read as rules. Never silent. */
  invalidCount: number;
  /**
   * Rules the backend holds but this read did not return. Null when the total
   * was not reported.
   */
  missingCount: number | null;
}

export interface CashbackRuleCreatePayload {
  name: string;
  type: string;
  scopeId?: string | null;
  /** Percent, 0 < p <= 100. */
  percentage: number;
  maxAmount?: number | null;
  isActive: boolean;
  startsAt: string;
  endsAt: string;
}

export interface CashbackRuleUpdatePayload {
  name?: string;
  type?: string;
  scopeId?: string | null;
  percentage?: number;
  maxAmount?: number | null;
  isActive?: boolean;
  startsAt?: string;
  endsAt?: string;
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

function readNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function normalizeCashbackRule(raw: unknown): CashbackRule | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  const name = readString(r.name);
  if (!id || !name) return null;
  const percentageBp = readInt(r.percentage_bp);
  return {
    id,
    name,
    type: readString(r.type) ?? "unknown",
    scopeId: readString(r.scope_id),
    percentageBp,
    // Prefer the backend's own percent field; derive only when it is absent,
    // so a display value can never disagree with the stored basis points.
    percentage: readNumber(r.percentage) ?? (percentageBp === null ? null : percentageBp / 100),
    maxAmount: readInt(r.max_amount),
    isActive: r.is_active === true,
    startsAt: readString(r.starts_at),
    endsAt: readString(r.ends_at),
    createdAt: readString(r.created_at),
    updatedAt: readString(r.updated_at),
  };
}

export async function fetchCashbackRules(
  params: { skip?: number; limit?: number; isActive?: boolean } = {},
  client: AxiosInstance = apiClient,
): Promise<CashbackRulePage> {
  const res = await client.get<unknown>(CASHBACK_RULES_PATH, {
    params: {
      skip: params.skip ?? 0,
      limit: params.limit ?? 50,
      ...(params.isActive === undefined ? {} : { is_active: params.isActive }),
    },
  });
  const r = readRecord(res.data) ?? {};
  const records = Array.isArray(r.items) ? r.items : [];
  const items: CashbackRule[] = [];
  let invalidCount = 0;
  for (const raw of records) {
    const item = normalizeCashbackRule(raw);
    if (item) items.push(item);
    else invalidCount += 1;
  }
  const total = readInt(r.total);
  return {
    items,
    total,
    invalidCount,
    missingCount: total === null ? null : Math.max(0, total - records.length),
  };
}

export async function createCashbackRule(
  payload: CashbackRuleCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.post(CASHBACK_RULES_PATH, {
    name: payload.name,
    type: payload.type,
    scope_id: payload.scopeId ?? null,
    percentage: payload.percentage,
    max_amount: payload.maxAmount ?? null,
    is_active: payload.isActive,
    starts_at: payload.startsAt,
    ends_at: payload.endsAt,
  });
}

export async function updateCashbackRule(
  id: string,
  payload: CashbackRuleUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.type !== undefined) body.type = payload.type;
  if (payload.scopeId !== undefined) body.scope_id = payload.scopeId;
  if (payload.percentage !== undefined) body.percentage = payload.percentage;
  if (payload.maxAmount !== undefined) body.max_amount = payload.maxAmount;
  if (payload.isActive !== undefined) body.is_active = payload.isActive;
  if (payload.startsAt !== undefined) body.starts_at = payload.startsAt;
  if (payload.endsAt !== undefined) body.ends_at = payload.endsAt;
  await client.patch(`${CASHBACK_RULES_PATH}/${id}`, body);
}

/** Soft-deactivate a rule. The row is kept; only `is_active` flips. */
export async function deactivateCashbackRule(
  id: string,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.delete(`${CASHBACK_RULES_PATH}/${id}`);
}
