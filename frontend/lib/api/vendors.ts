/**
 * Marketplace vendors (admin back-office).
 *
 * Contract: backend/app/modules/vendors/api/routes.py + schemas/vendor.py
 *   GET   /admin/vendors                    — vendors:read
 *   GET   /admin/vendors/{id}               — vendors:read
 *   PATCH /admin/vendors/{id}/verify        — vendors:write
 *   PATCH /admin/vendors/{id}               — vendors:write
 *   GET   /admin/vendors/{id}/earnings      — vendors:read
 *   GET   /admin/vendors/{id}/settlements   — vendors:read
 *   POST  /admin/vendors/{id}/settlements   — vendors:write
 *
 * Two contract facts this module encodes rather than hides:
 *
 * 1. The admin LIST returns `VendorPublicResponse` items, not the full row. The
 *    public projection deliberately omits commission rate, payout IBAN, and
 *    national id, and it does not carry `is_active` either. The list view
 *    therefore cannot show those; the detail read (`GET /admin/vendors/{id}`,
 *    which returns `VendorResponse`) is the only place they exist.
 * 2. Money is integer Iranian rials. Amounts are passed through untouched and
 *    never converted, summed, or rounded on the client.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const VENDORS_ADMIN_PATH = "/admin/vendors";

export interface VendorListItem {
  id: string;
  storeName: string;
  slug: string;
  logoUrl: string | null;
  description: string | null;
  isVerified: boolean;
  rating: number | null;
  totalSalesCount: number | null;
  createdAt: string | null;
}

/** Full vendor row — only returned by the single-vendor read. */
export interface VendorDetail extends VendorListItem {
  userId: string;
  bannerUrl: string | null;
  /** Commission in basis points (1000 = 10%). */
  commissionRate: number | null;
  isActive: boolean | null;
  nationalId: string | null;
  ibanNumber: string | null;
  contactPhone: string | null;
  updatedAt: string | null;
}

export interface VendorListPage {
  items: VendorListItem[];
  total: number | null;
  page: number;
  pageSize: number;
  totalPages: number | null;
  /**
   * Records the backend returned that could not be read as vendors. They were
   * not skipped silently — a vendor hidden by a contract drift is a payout the
   * operator cannot see.
   */
  invalidCount: number;
  /**
   * Vendors the backend holds but this read did not return (pagination or the
   * page-size cap). Null when the total was not reported. Never clamped: a
   * list showing 50 of 80 vendors without saying so reads as complete.
   */
  missingCount: number | null;
}

export interface VendorEarnings {
  vendorId: string;
  storeName: string;
  periodStart: string | null;
  periodEnd: string | null;
  /** All amounts are integer rials as reported by the backend. */
  totalSales: number | null;
  totalOrders: number | null;
  totalItems: number | null;
  commissionRate: number | null;
  commissionAmount: number | null;
  netEarnings: number | null;
  settledAmount: number | null;
  pendingSettlement: number | null;
}

export interface VendorSettlement {
  id: string;
  vendorId: string;
  /** Integer rials. */
  amount: number | null;
  periodStart: string | null;
  periodEnd: string | null;
  status: string;
  paymentReference: string | null;
  paidAt: string | null;
  createdAt: string | null;
}

export interface VendorSettlementPage {
  items: VendorSettlement[];
  total: number | null;
  page: number;
  pageSize: number;
  totalPages: number | null;
  invalidCount: number;
  missingCount: number | null;
}

export interface VendorSettlementCreatePayload {
  /** Integer rials, at least 1. */
  amount: number;
  periodStart?: string | null;
  periodEnd?: string | null;
  paymentReference?: string | null;
}

export interface VendorAdminUpdatePayload {
  storeName?: string;
  commissionRate?: number;
  isVerified?: boolean;
  isActive?: boolean;
  description?: string | null;
  contactPhone?: string | null;
  nationalId?: string | null;
  ibanNumber?: string | null;
  rating?: number;
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

function readBool(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function normalizeVendorListItem(raw: unknown): VendorListItem | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  const storeName = readString(r.store_name) ?? readString(r.storeName);
  if (!id || !storeName) return null;
  return {
    id,
    storeName,
    slug: readString(r.slug) ?? "",
    logoUrl: readString(r.logo_url),
    description: readString(r.description),
    isVerified: readBool(r.is_verified) ?? false,
    rating: readNumber(r.rating),
    totalSalesCount: readInt(r.total_sales_count),
    createdAt: readString(r.created_at),
  };
}

export function normalizeVendorDetail(raw: unknown): VendorDetail | null {
  const base = normalizeVendorListItem(raw);
  const r = readRecord(raw);
  if (!base || !r) return null;
  return {
    ...base,
    userId: readString(r.user_id) ?? "",
    bannerUrl: readString(r.banner_url),
    commissionRate: readInt(r.commission_rate),
    isActive: readBool(r.is_active),
    nationalId: readString(r.national_id),
    ibanNumber: readString(r.iban_number),
    contactPhone: readString(r.contact_phone),
    updatedAt: readString(r.updated_at),
  };
}

export function normalizeEarnings(raw: unknown): VendorEarnings | null {
  const r = readRecord(raw);
  if (!r) return null;
  const vendorId = readString(r.vendor_id);
  if (!vendorId) return null;
  return {
    vendorId,
    storeName: readString(r.store_name) ?? "",
    periodStart: readString(r.period_start),
    periodEnd: readString(r.period_end),
    totalSales: readInt(r.total_sales),
    totalOrders: readInt(r.total_orders),
    totalItems: readInt(r.total_items),
    commissionRate: readInt(r.commission_rate),
    commissionAmount: readInt(r.commission_amount),
    netEarnings: readInt(r.net_earnings),
    settledAmount: readInt(r.settled_amount),
    pendingSettlement: readInt(r.pending_settlement),
  };
}

export function normalizeSettlement(raw: unknown): VendorSettlement | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  if (!id) return null;
  return {
    id,
    vendorId: readString(r.vendor_id) ?? "",
    amount: readInt(r.amount),
    periodStart: readString(r.period_start),
    periodEnd: readString(r.period_end),
    status: readString(r.status) ?? "unknown",
    paymentReference: readString(r.payment_reference),
    paidAt: readString(r.paid_at),
    createdAt: readString(r.created_at),
  };
}

function parseVendorPage(payload: unknown): VendorListPage {
  const r = readRecord(payload) ?? {};
  const records = Array.isArray(r.items) ? r.items : [];
  const items: VendorListItem[] = [];
  let invalidCount = 0;
  for (const raw of records) {
    const item = normalizeVendorListItem(raw);
    if (item) items.push(item);
    else invalidCount += 1;
  }
  const total = readInt(r.total);
  return {
    items,
    total,
    page: readInt(r.page) ?? 1,
    pageSize: readInt(r.page_size) ?? items.length,
    totalPages: readInt(r.total_pages),
    invalidCount,
    // Count both records the caller cannot act on: unreadable ones and vendors
    // still sitting behind pagination.
    missingCount: total === null ? null : Math.max(0, total - records.length),
  };
}

export async function fetchVendorPage(
  params: { page?: number; pageSize?: number; isActive?: boolean; isVerified?: boolean },
  client: AxiosInstance = apiClient,
): Promise<VendorListPage> {
  const res = await client.get<unknown>(VENDORS_ADMIN_PATH, {
    params: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      ...(params.isActive === undefined ? {} : { is_active: params.isActive }),
      ...(params.isVerified === undefined ? {} : { is_verified: params.isVerified }),
    },
  });
  return parseVendorPage(res.data);
}

export async function fetchVendor(
  id: string,
  client: AxiosInstance = apiClient,
): Promise<VendorDetail | null> {
  const res = await client.get<unknown>(`${VENDORS_ADMIN_PATH}/${id}`);
  return normalizeVendorDetail(res.data);
}

export async function fetchVendorEarnings(
  id: string,
  params: { periodStart?: string; periodEnd?: string } = {},
  client: AxiosInstance = apiClient,
): Promise<VendorEarnings | null> {
  const res = await client.get<unknown>(`${VENDORS_ADMIN_PATH}/${id}/earnings`, {
    params: {
      ...(params.periodStart ? { period_start: params.periodStart } : {}),
      ...(params.periodEnd ? { period_end: params.periodEnd } : {}),
    },
  });
  return normalizeEarnings(res.data);
}

export async function fetchVendorSettlements(
  id: string,
  params: { page?: number; pageSize?: number } = {},
  client: AxiosInstance = apiClient,
): Promise<VendorSettlementPage> {
  const res = await client.get<unknown>(`${VENDORS_ADMIN_PATH}/${id}/settlements`, {
    params: { page: params.page ?? 1, page_size: params.pageSize ?? 20 },
  });
  const r = readRecord(res.data) ?? {};
  const records = Array.isArray(r.items) ? r.items : [];
  const items: VendorSettlement[] = [];
  let invalidCount = 0;
  for (const raw of records) {
    const item = normalizeSettlement(raw);
    if (item) items.push(item);
    else invalidCount += 1;
  }
  const total = readInt(r.total);
  return {
    items,
    total,
    page: readInt(r.page) ?? 1,
    pageSize: readInt(r.page_size) ?? items.length,
    totalPages: readInt(r.total_pages),
    invalidCount,
    missingCount: total === null ? null : Math.max(0, total - records.length),
  };
}

export async function setVendorVerification(
  id: string,
  verified: boolean,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.patch(`${VENDORS_ADMIN_PATH}/${id}/verify`, { verified });
}

export async function updateVendorAdmin(
  id: string,
  payload: VendorAdminUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  const body: Record<string, unknown> = {};
  if (payload.storeName !== undefined) body.store_name = payload.storeName;
  if (payload.commissionRate !== undefined) body.commission_rate = payload.commissionRate;
  if (payload.isVerified !== undefined) body.is_verified = payload.isVerified;
  if (payload.isActive !== undefined) body.is_active = payload.isActive;
  if (payload.description !== undefined) body.description = payload.description;
  if (payload.contactPhone !== undefined) body.contact_phone = payload.contactPhone;
  if (payload.nationalId !== undefined) body.national_id = payload.nationalId;
  if (payload.ibanNumber !== undefined) body.iban_number = payload.ibanNumber;
  if (payload.rating !== undefined) body.rating = payload.rating;
  await client.patch(`${VENDORS_ADMIN_PATH}/${id}`, body);
}

export async function createVendorSettlement(
  id: string,
  payload: VendorSettlementCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.post(`${VENDORS_ADMIN_PATH}/${id}/settlements`, {
    amount: payload.amount,
    period_start: payload.periodStart ?? null,
    period_end: payload.periodEnd ?? null,
    payment_reference: payload.paymentReference ?? null,
  });
}

export const SETTLEMENT_STATUS_LABELS: Record<string, string> = {
  pending: "در انتظار پرداخت",
  approved: "تأییدشده",
  paid: "پرداخت‌شده",
  rejected: "ردشده",
};

export function settlementStatusLabel(status: string): string {
  return SETTLEMENT_STATUS_LABELS[status] ?? status;
}

export function settlementStatusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "paid") return "default";
  if (status === "approved") return "secondary";
  if (status === "rejected") return "destructive";
  return "outline";
}

/** Basis points → percent label (1000 bp = 10%). */
export function commissionPercentLabel(basisPoints: number | null): string | null {
  if (basisPoints === null) return null;
  return `${basisPoints / 100}`;
}
