/**
 * GDPR data-subject requests — operator surface.
 *
 * Contract: backend/app/modules/settings/api/routes.py
 *   GET  /settings/admin/privacy/requests?status=&type=&skip=&limit=
 *        → { items, total, skip, limit }
 *   POST /settings/admin/privacy/requests/{id}/export
 *   POST /settings/admin/privacy/requests/{id}/erase
 *   POST /settings/admin/privacy/requests/{id}/reject
 *   POST /settings/admin/privacy/requests/purge-expired
 *
 * The export/erase act on `request.user_id` — the requester — so an operator
 * working the queue never types a UUID to aim the tool at somebody. The manual
 * UUID path (`privacyApi` in `wp-parity.ts`) is still the fallback for
 * handling a support escalation that never became a request.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";
import {
  normalizePrivacyRequest,
  type PrivacyRequestStatus,
  type PrivacyRequestType,
} from "./privacy";

export const ADMIN_PRIVACY_REQUESTS_PATH = "/settings/admin/privacy/requests";

export interface AdminPrivacyRequest {
  id: string;
  /** The requester — and the account the work runs on. */
  userId: string;
  type: string;
  status: string;
  reason: string | null;
  adminNote: string | null;
  resolvedBy: string | null;
  verifiedAt: string | null;
  confirmedAt: string | null;
  resolvedAt: string | null;
  resultExpiresAt: string | null;
  createdAt: string;
  updatedAt: string;
  hasResult: boolean;
}

export interface AdminPrivacyQueue {
  items: AdminPrivacyRequest[];
  total: number | null;
  skip: number;
  limit: number;
}

interface RawRow extends Record<string, unknown> {
  user_id?: unknown;
  resolved_by?: unknown;
  result_expires_at?: unknown;
}

export function normalizeAdminRow(raw: unknown): AdminPrivacyRequest | null {
  const base = normalizePrivacyRequest(raw);
  if (!base) return null;
  const r = raw as RawRow;
  const userId =
    typeof r.user_id === "string" && r.user_id.trim() ? r.user_id : null;
  // A queue row without a requester is un-actionable — the operator could not
  // tell whose data the row is about. Dropping it would hide work, so it is
  // reported as a null userId and the table says so.
  return {
    ...base,
    userId: userId ?? "",
    resolvedBy: typeof r.resolved_by === "string" ? r.resolved_by : null,
    resultExpiresAt:
      typeof r.result_expires_at === "string" ? r.result_expires_at : null,
  };
}

export async function fetchPrivacyQueue(
  params: {
    status?: PrivacyRequestStatus | null;
    type?: PrivacyRequestType | null;
    skip?: number;
    limit?: number;
  } = {},
  client: AxiosInstance = apiClient,
): Promise<AdminPrivacyQueue> {
  const skip = params.skip ?? 0;
  const limit = params.limit ?? 50;
  const res = await client.get<unknown>(ADMIN_PRIVACY_REQUESTS_PATH, {
    params: {
      skip,
      limit,
      ...(params.status ? { status: params.status } : {}),
      ...(params.type ? { type: params.type } : {}),
    },
  });
  const data = res.data as
    | { items?: unknown; total?: unknown }
    | null
    | undefined;
  const records =
    data && Array.isArray(data.items) ? (data.items as unknown[]) : [];
  const items: AdminPrivacyRequest[] = [];
  for (const raw of records) {
    const row = normalizeAdminRow(raw);
    if (row) items.push(row);
  }
  const total =
    typeof data?.total === "number" && Number.isFinite(data.total)
      ? data.total
      : null;
  return { items, total, skip, limit };
}

async function postAction(
  path: string,
  client: AxiosInstance,
  body?: unknown,
): Promise<AdminPrivacyRequest | null> {
  const res = await client.post<unknown>(path, body ?? null);
  return normalizeAdminRow(res.data);
}

export function runQueuedExport(
  requestId: string,
  client: AxiosInstance = apiClient,
): Promise<AdminPrivacyRequest | null> {
  return postAction(`${ADMIN_PRIVACY_REQUESTS_PATH}/${requestId}/export`, client);
}

export function runQueuedErase(
  requestId: string,
  client: AxiosInstance = apiClient,
): Promise<AdminPrivacyRequest | null> {
  return postAction(`${ADMIN_PRIVACY_REQUESTS_PATH}/${requestId}/erase`, client);
}

export function rejectQueuedRequest(
  requestId: string,
  note: string,
  client: AxiosInstance = apiClient,
): Promise<AdminPrivacyRequest | null> {
  return postAction(
    `${ADMIN_PRIVACY_REQUESTS_PATH}/${requestId}/reject`,
    client,
    { note },
  );
}

export async function purgeExpiredExports(
  client: AxiosInstance = apiClient,
): Promise<number> {
  const res = await client.post<unknown>(
    `${ADMIN_PRIVACY_REQUESTS_PATH}/purge-expired`,
    null,
  );
  const data = res.data as { purged?: unknown } | null;
  return typeof data?.purged === "number" ? data.purged : 0;
}
