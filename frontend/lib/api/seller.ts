/**
 * Selling on the marketplace, from the seller's own side.
 *
 * Contract: backend/app/modules/vendors/api/routes.py + schemas/vendor.py
 *   POST  /vendors/register       → VendorResponse  (one vendor per user)
 *   GET   /vendors/me             → VendorEarningsResponse
 *   PATCH /vendors/me/profile     → VendorResponse
 *   GET   /vendors/{slug}         → VendorPublicResponse (public storefront)
 *
 * Two things this module is deliberately careful about:
 *
 * 1. **Update is a full replace of whatever is sent.** `PATCH /vendors/me/profile`
 *    takes `VendorUpdateRequest`, where every field is optional — but a field
 *    that IS sent overwrites. So the edit form must be seeded from the current
 *    vendor first and only then sent, or a single changed field would blank the
 *    rest. `updateMyVendorProfile` sends only the keys the caller provided.
 * 2. **The IBAN is validated client-side to the same rule the server enforces**
 *    (IR + 24 digits). The server normalises and rejects otherwise, and a
 *    payout account is not a field to discover is wrong after a failed submit.
 *
 * Earnings are integer rials; `commission_rate` is basis points (1000 = 10%).
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const VENDORS_REGISTER_PATH = "/vendors/register";
export const VENDORS_ME_PATH = "/vendors/me";
export const VENDORS_ME_PROFILE_PATH = "/vendors/me/profile";

export interface SellerEarnings {
  vendorId: string;
  storeName: string;
  periodStart: string | null;
  periodEnd: string | null;
  /** All amounts integer rials. */
  totalSales: number | null;
  totalOrders: number | null;
  totalItems: number | null;
  /** Basis points: 1000 = 10%. */
  commissionRate: number | null;
  commissionAmount: number | null;
  netEarnings: number | null;
  settledAmount: number | null;
  pendingSettlement: number | null;
}

export interface SellerProfile {
  id: string;
  storeName: string;
  slug: string;
  description: string | null;
  logoUrl: string | null;
  bannerUrl: string | null;
  isVerified: boolean;
  nationalId: string | null;
  ibanNumber: string | null;
  contactPhone: string | null;
}

export interface SellerRegistration {
  storeName: string;
  slug?: string;
  description?: string | null;
  nationalId?: string | null;
  ibanNumber?: string | null;
  contactPhone?: string | null;
}

export interface SellerProfileUpdate {
  storeName?: string;
  description?: string | null;
  logoUrl?: string | null;
  bannerUrl?: string | null;
  nationalId?: string | null;
  ibanNumber?: string | null;
  contactPhone?: string | null;
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

export function normalizeSellerProfile(raw: unknown): SellerProfile | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  const storeName = readString(r.store_name);
  if (!id || !storeName) return null;
  return {
    id,
    storeName,
    slug: readString(r.slug) ?? "",
    description: readString(r.description),
    logoUrl: readString(r.logo_url),
    bannerUrl: readString(r.banner_url),
    isVerified: r.is_verified === true,
    nationalId: readString(r.national_id),
    ibanNumber: readString(r.iban_number),
    contactPhone: readString(r.contact_phone),
  };
}

export function normalizeEarnings(raw: unknown): SellerEarnings | null {
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

/**
 * Iranian IBAN rule, matching the server's validator exactly.
 * Returns null when valid, otherwise the message to show.
 */
export function validateIban(value: string): string | null {
  const cleaned = value.replace(/\s/g, "").toUpperCase();
  if (!cleaned) return null; // optional field
  const withPrefix = cleaned.startsWith("IR") ? cleaned : `IR${cleaned}`;
  if (!/^IR\d{24}$/.test(withPrefix)) {
    return "شماره شبا باید با IR و سپس ۲۴ رقم باشد (مثال: IR120120000000001234567890).";
  }
  return null;
}

/** National id rule, matching the server: 10 to 14 digits. */
export function validateNationalId(value: string): string | null {
  const cleaned = value.trim();
  if (!cleaned) return null; // optional field
  if (!/^\d{10,14}$/.test(cleaned)) {
    return "کد ملی باید بین ۱۰ تا ۱۴ رقم باشد.";
  }
  return null;
}

export async function registerAsSeller(
  payload: SellerRegistration,
  client: AxiosInstance = apiClient,
): Promise<SellerProfile | null> {
  const res = await client.post<unknown>(VENDORS_REGISTER_PATH, {
    store_name: payload.storeName,
    slug: payload.slug ?? null,
    description: payload.description ?? null,
    national_id: payload.nationalId ?? null,
    iban_number: payload.ibanNumber ?? null,
    contact_phone: payload.contactPhone ?? null,
  });
  return normalizeSellerProfile(res.data);
}

/** Vendor earnings for the signed-in seller, or null when they have no store. */
export async function fetchMyEarnings(
  client: AxiosInstance = apiClient,
): Promise<SellerEarnings | null> {
  const res = await client.get<unknown>(VENDORS_ME_PATH);
  return normalizeEarnings(res.data);
}

/**
 * True when the error is the backend's "this user has no vendor" 404.
 *
 * The endpoint answers 404 for a user who never registered, which is a normal
 * onboarding state, not a failure. Distinguishing the two matters: telling a
 * user "something went wrong" when the truth is "you have not signed up yet"
 * sends them looking for a bug instead of filling in the form.
 */
export function isNotASellerError(error: unknown): boolean {
  const e = error as { response?: { status?: number } } | null | undefined;
  return e?.response?.status === 404;
}

export async function updateMyVendorProfile(
  payload: SellerProfileUpdate,
  client: AxiosInstance = apiClient,
): Promise<SellerProfile | null> {
  // Send ONLY the keys the caller set. A field sent as null would clear it, so
  // building the body from `payload` keys (not a fixed shape) is what keeps an
  // edit of one field from wiping the others.
  const body: Record<string, unknown> = {};
  if (payload.storeName !== undefined) body.store_name = payload.storeName;
  if (payload.description !== undefined) body.description = payload.description;
  if (payload.logoUrl !== undefined) body.logo_url = payload.logoUrl;
  if (payload.bannerUrl !== undefined) body.banner_url = payload.bannerUrl;
  if (payload.nationalId !== undefined) body.national_id = payload.nationalId;
  if (payload.ibanNumber !== undefined) body.iban_number = payload.ibanNumber;
  if (payload.contactPhone !== undefined) body.contact_phone = payload.contactPhone;

  const res = await client.patch<unknown>(VENDORS_ME_PROFILE_PATH, body);
  return normalizeSellerProfile(res.data);
}

/** Basis points → percent for display (1000 bp = 10%). */
export function commissionPercent(basisPoints: number | null): number | null {
  return basisPoints === null ? null : basisPoints / 100;
}
