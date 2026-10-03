/**
 * GDPR data-subject requests — customer surface.
 *
 * Contract: backend/app/modules/settings/api/routes.py + schemas/privacy.py
 *   POST /settings/privacy/requests          → 201 PrivacyRequestItem
 *   GET  /settings/privacy/requests          → { items: [...] }
 *   GET  /settings/privacy/requests/{id}     → PrivacyRequestItem
 *   GET  /settings/privacy/requests/{id}/result     → the export document (once)
 *   GET  /settings/privacy/requests/{id}/result.zip → the same archive as a ZIP (once)
 *   POST /settings/privacy/requests/{id}/send-email-confirmation → mail a confirm link
 *   POST /settings/privacy/requests/confirm-by-email → redeem that link (no session)
 *
 * Note what is NOT in this file: a user id. None of these endpoints accept
 * one — the backend takes the subject from the access token. A client that
 * could name the subject could name somebody else's, so the type has no
 * field to put it in.
 *
 * The admin half of the same resource lives in `privacy-admin.ts`.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const PRIVACY_REQUESTS_PATH = "/settings/privacy/requests";

export const PRIVACY_REQUEST_TYPES = ["export", "erase"] as const;
export type PrivacyRequestType = (typeof PRIVACY_REQUEST_TYPES)[number];

export const PRIVACY_REQUEST_STATUSES = [
  "pending",
  "processing",
  "completed",
  "rejected",
] as const;
export type PrivacyRequestStatus = (typeof PRIVACY_REQUEST_STATUSES)[number];

export const PRIVACY_TYPE_LABELS: Record<string, string> = {
  export: "دریافت نسخه از داده‌های من",
  erase: "حذف داده‌های من",
};

export const PRIVACY_STATUS_LABELS: Record<string, string> = {
  pending: "در انتظار بررسی",
  processing: "در حال انجام",
  completed: "انجام شد",
  // The operation ran but at least one data source did not finish. Distinct
  // from "completed" so a partial archive is not presented as the subject's
  // whole dataset.
  partial: "ناقص — بخشی از داده‌ها به دست نیامد",
  rejected: "رد شد",
};

export function privacyTypeLabel(type: string): string {
  return PRIVACY_TYPE_LABELS[type] ?? type;
}

export function privacyStatusLabel(status: string): string {
  return PRIVACY_STATUS_LABELS[status] ?? status;
}

export function privacyStatusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" | "success" | "warning" {
  if (status === "completed") return "success";
  // Warning, not success: the work happened but the result is incomplete, and
  // a green badge would tell the subject otherwise.
  if (status === "partial") return "warning";
  if (status === "rejected") return "destructive";
  if (status === "processing") return "warning";
  if (status === "pending") return "secondary";
  return "outline";
}

export interface PrivacyRequest {
  id: string;
  type: string;
  status: string;
  reason: string | null;
  verifiedAt: string | null;
  /** Set once the request was confirmed by OTP or by the emailed link. */
  confirmedAt: string | null;
  /** The operator's note, shown on rejection so the customer knows why. */
  adminNote: string | null;
  resolvedAt: string | null;
  createdAt: string;
  updatedAt: string;
  /** True only when a payload is actually collectable right now. */
  hasResult: boolean;
}

function readString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function normalizePrivacyRequest(raw: unknown): PrivacyRequest | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  if (!id) return null;
  const createdAt = readString(r.created_at);
  if (!createdAt) return null;
  return {
    id,
    type: readString(r.type) ?? "export",
    status: readString(r.status) ?? "unknown",
    reason: readString(r.reason),
    verifiedAt: readString(r.verified_at),
    confirmedAt: readString(r.confirmed_at),
    adminNote: readString(r.admin_note),
    resolvedAt: readString(r.resolved_at),
    createdAt,
    updatedAt: readString(r.updated_at) ?? createdAt,
    hasResult: r.has_result === true,
  };
}

export async function submitPrivacyRequest(
  body: { type: PrivacyRequestType; reason?: string | null; password?: string | null },
  client: AxiosInstance = apiClient,
): Promise<PrivacyRequest> {
  const res = await client.post<unknown>(PRIVACY_REQUESTS_PATH, {
    type: body.type,
    reason: body.reason ?? null,
    password: body.password ?? null,
  });
  const item = normalizePrivacyRequest(res.data);
  if (!item) {
    throw new Error("پاسخ سرور برای ثبت درخواست ناشناخته بود");
  }
  return item;
}

export async function fetchMyPrivacyRequests(
  client: AxiosInstance = apiClient,
): Promise<PrivacyRequest[]> {
  const res = await client.get<unknown>(PRIVACY_REQUESTS_PATH);
  const envelope = readRecord(res.data);
  const records = envelope && Array.isArray(envelope.items) ? envelope.items : [];
  const items: PrivacyRequest[] = [];
  for (const raw of records) {
    const item = normalizePrivacyRequest(raw);
    if (item) items.push(item);
  }
  return items;
}

/**
 * Collect the export document.
 *
 * The backend deletes the stored payload as it is read, so this is a
 * one-shot. A second call 404s by design, and the UI says so rather than
 * leaving a button that silently does nothing.
 */
export async function fetchPrivacyExportResult(
  requestId: string,
  client: AxiosInstance = apiClient,
): Promise<Record<string, unknown>> {
  const res = await client.get<unknown>(
    `${PRIVACY_REQUESTS_PATH}/${requestId}/result`,
  );
  const record = readRecord(res.data);
  if (!record) {
    throw new Error("محتوای خروجی قابل خواندن نبود");
  }
  return record;
}

/**
 * Collect the export as a structured ZIP (index.html + one JSON per source).
 *
 * Same one-shot rule as the JSON result: reading it clears the stored copy.
 * Returned as a Blob rather than parsed, because the whole point is a file a
 * person can open — the server names it `data-export-<id>.zip`.
 */
export async function fetchPrivacyExportZip(
  requestId: string,
  client: AxiosInstance = apiClient,
): Promise<Blob> {
  const res = await client.get(
    `${PRIVACY_REQUESTS_PATH}/${requestId}/result.zip`,
    { responseType: "blob" },
  );
  return res.data as Blob;
}

/**
 * Ask the server to email a confirmation link for one of your own requests.
 *
 * The second path beside the SMS OTP: a subject whose number changed, or who
 * is travelling without their SIM, otherwise cannot confirm their own request.
 * The server reports honestly when the account has no address to mail.
 */
export async function sendPrivacyEmailConfirmation(
  requestId: string,
  client: AxiosInstance = apiClient,
): Promise<{ sent: boolean; message: string }> {
  const res = await client.post<{ sent: boolean; message: string }>(
    `${PRIVACY_REQUESTS_PATH}/${requestId}/send-email-confirmation`,
  );
  return res.data;
}

/**
 * Redeem an emailed confirmation token. Unauthenticated on the server: the
 * token was mailed to the account's own address, so possession is the proof,
 * and the click may happen on a device that is not signed in.
 */
export async function confirmPrivacyRequestByEmail(
  token: string,
  client: AxiosInstance = apiClient,
): Promise<{ id: string; status: string; confirmed_at: string | null }> {
  const res = await client.post<{ id: string; status: string; confirmed_at: string | null }>(
    `${PRIVACY_REQUESTS_PATH}/confirm-by-email`,
    { token },
  );
  return res.data;
}
