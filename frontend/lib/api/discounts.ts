/**
 * Discount rules and coupon preview.
 *
 * Contract: backend/app/modules/discounts/api/routes.py + schemas/discount.py
 *   POST  /discounts/admin/discounts            — discounts:write
 *   GET   /discounts/admin/discounts            — discounts:read
 *   PATCH /discounts/admin/discounts/{id}       — discounts:write
 *
 * The previous version of this module was written against a contract that does
 * not exist: it read a top-level `total` where the backend returns `meta`, and
 * it used `min_order_amount` / `max_discount_amount` where the columns are
 * `min_cart_amount` / `max_discount`. Every field it exposed was therefore
 * `undefined` at runtime while the value sat in the payload.
 *
 * Two units matter here and are easy to get wrong:
 *   - `value` is rials for `fixed`, and BASIS POINTS for `percentage`
 *     (1000 = 10%). The edit form converts at the call site, never here.
 *   - All money is integer rials; no float arithmetic happens client-side.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const DISCOUNTS_ADMIN_PATH = "/discounts/admin/discounts";

export const DISCOUNT_TYPES = ["fixed", "percentage", "first_order"] as const;
export type DiscountType = (typeof DISCOUNT_TYPES)[number];

export const DISCOUNT_TYPE_LABELS: Record<string, string> = {
  fixed: "مبلغ ثابت",
  percentage: "درصدی",
  first_order: "اولین خرید",
};

export const DISCOUNT_SCOPES = ["global", "product", "category", "brand", "user"] as const;
export type DiscountScope = (typeof DISCOUNT_SCOPES)[number];

export const DISCOUNT_SCOPE_LABELS: Record<string, string> = {
  global: "سراسری",
  product: "کالا",
  category: "دسته‌بندی",
  brand: "برند",
  user: "کاربر",
};

export function discountTypeLabel(type: string): string {
  return DISCOUNT_TYPE_LABELS[type] ?? type;
}

export function discountScopeLabel(scope: string): string {
  return DISCOUNT_SCOPE_LABELS[scope] ?? scope;
}

export interface Discount {
  id: string;
  name: string;
  type: string;
  /** Rials for `fixed`, basis points for `percentage`. */
  value: number | null;
  minCartAmount: number | null;
  maxDiscount: number | null;
  scope: string;
  scopeIds: string[] | null;
  startsAt: string | null;
  endsAt: string | null;
  isActive: boolean;
  isStackable: boolean;
  usageLimit: number | null;
  usageCount: number | null;
  priority: number | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface DiscountPageMeta {
  page: number | null;
  pageSize: number | null;
  totalItems: number | null;
  totalPages: number | null;
  hasNext: boolean | null;
  hasPrev: boolean | null;
}

export interface DiscountPage {
  items: Discount[];
  meta: DiscountPageMeta;
  /** Records returned that could not be read as discounts. Never silent. */
  invalidCount: number;
  /**
   * Discounts the backend holds but this read did not return. Null when the
   * meta block did not report a total.
   */
  missingCount: number | null;
}

export interface DiscountCreatePayload {
  name: string;
  type: string;
  value: number;
  minCartAmount?: number | null;
  maxDiscount?: number | null;
  scope: string;
  scopeIds?: string[] | null;
  startsAt: string;
  endsAt: string;
  isActive: boolean;
  isStackable: boolean;
  usageLimit?: number | null;
  priority: number;
}

export interface DiscountUpdatePayload {
  name?: string;
  value?: number;
  minCartAmount?: number | null;
  maxDiscount?: number | null;
  scope?: string;
  scopeIds?: string[] | null;
  startsAt?: string;
  endsAt?: string;
  isActive?: boolean;
  isStackable?: boolean;
  usageLimit?: number | null;
  priority?: number;
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

export function normalizeDiscount(raw: unknown): Discount | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  const name = readString(r.name);
  if (!id || !name) return null;

  const scopeIdsRaw = r.scope_ids;
  const scopeIds = Array.isArray(scopeIdsRaw)
    ? scopeIdsRaw.filter((v): v is string => typeof v === "string")
    : null;

  return {
    id,
    name,
    type: readString(r.type) ?? "unknown",
    value: readInt(r.value),
    minCartAmount: readInt(r.min_cart_amount),
    maxDiscount: readInt(r.max_discount),
    scope: readString(r.scope) ?? "global",
    scopeIds: scopeIds && scopeIds.length ? scopeIds : null,
    startsAt: readString(r.starts_at),
    endsAt: readString(r.ends_at),
    isActive: r.is_active === true,
    isStackable: r.is_stackable === true,
    usageLimit: readInt(r.usage_limit),
    usageCount: readInt(r.usage_count),
    priority: readInt(r.priority),
    createdAt: readString(r.created_at),
    updatedAt: readString(r.updated_at),
  };
}

function parseMeta(raw: unknown): DiscountPageMeta {
  const r = readRecord(raw) ?? {};
  return {
    page: readInt(r.page),
    pageSize: readInt(r.page_size),
    totalItems: readInt(r.total_items),
    totalPages: readInt(r.total_pages),
    hasNext: typeof r.has_next === "boolean" ? r.has_next : null,
    hasPrev: typeof r.has_prev === "boolean" ? r.has_prev : null,
  };
}

export async function fetchDiscounts(
  params: { page?: number; pageSize?: number; includeInactive?: boolean } = {},
  client: AxiosInstance = apiClient,
): Promise<DiscountPage> {
  const res = await client.get<unknown>(DISCOUNTS_ADMIN_PATH, {
    params: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      include_inactive: params.includeInactive ?? false,
    },
  });
  const r = readRecord(res.data) ?? {};
  const records = Array.isArray(r.items) ? r.items : [];
  const items: Discount[] = [];
  let invalidCount = 0;
  for (const raw of records) {
    const item = normalizeDiscount(raw);
    if (item) items.push(item);
    else invalidCount += 1;
  }
  const meta = parseMeta(r.meta);
  return {
    items,
    meta,
    invalidCount,
    missingCount:
      meta.totalItems === null
        ? null
        : Math.max(0, meta.totalItems - records.length),
  };
}

export async function createDiscount(
  payload: DiscountCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.post(DISCOUNTS_ADMIN_PATH, {
    name: payload.name,
    type: payload.type,
    value: Math.trunc(payload.value),
    min_cart_amount: payload.minCartAmount ?? null,
    max_discount: payload.maxDiscount ?? null,
    scope: payload.scope,
    scope_ids: payload.scopeIds ?? null,
    starts_at: payload.startsAt,
    ends_at: payload.endsAt,
    is_active: payload.isActive,
    is_stackable: payload.isStackable,
    usage_limit: payload.usageLimit ?? null,
    priority: Math.trunc(payload.priority),
  });
}

export async function updateDiscount(
  id: string,
  payload: DiscountUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  // Math.trunc, never round: a percentage stored as basis points must land on
  // an integer, and rounding a money value is exactly what this contract bans.
  if (payload.value !== undefined) body.value = Math.trunc(payload.value);
  if (payload.minCartAmount !== undefined) body.min_cart_amount = payload.minCartAmount;
  if (payload.maxDiscount !== undefined) body.max_discount = payload.maxDiscount;
  if (payload.scope !== undefined) body.scope = payload.scope;
  if (payload.scopeIds !== undefined) body.scope_ids = payload.scopeIds;
  if (payload.startsAt !== undefined) body.starts_at = payload.startsAt;
  if (payload.endsAt !== undefined) body.ends_at = payload.endsAt;
  if (payload.isActive !== undefined) body.is_active = payload.isActive;
  if (payload.isStackable !== undefined) body.is_stackable = payload.isStackable;
  if (payload.usageLimit !== undefined) body.usage_limit = payload.usageLimit;
  if (payload.priority !== undefined) body.priority = Math.trunc(payload.priority);
  await client.patch(`${DISCOUNTS_ADMIN_PATH}/${id}`, body);
}

/** Basis points → percent (1000 bp = 10%). Returns null when not readable. */
export function basisPointsToPercent(bp: number | null): number | null {
  return bp === null ? null : bp / 100;
}

/** Percent → basis points, truncated to an integer. */
export function percentToBasisPoints(percent: number): number {
  return Math.trunc(percent * 100);
}
