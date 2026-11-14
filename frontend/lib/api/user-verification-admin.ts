/**
 * User verification (admin) — port of the WP plugin user-verification-orders.
 *
 * Contract: backend/app/modules/userverify/api/routes.py
 *   GET /admin/user-verification/config      — userverify:read
 *   PUT /admin/user-verification/config      — userverify:write
 *   GET /admin/user-verification/logs        — userverify:read
 *   GET /admin/user-verification/logs/export — userverify:read (CSV blob)
 *
 * The verified flag itself lives on the admin users API
 * (`/users/admin/users?is_verified=…`, PATCH `{is_verified}`); the order badge
 * lane is the `doing_verified` order status.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const UVERIFY_CONFIG_PATH = "/admin/user-verification/config";
export const UVERIFY_LOGS_PATH = "/admin/user-verification/logs";
export const UVERIFY_LOGS_EXPORT_PATH = "/admin/user-verification/logs/export";

export interface UserVerificationConfig {
  /** Master switch: verified buyers get the "doing_verified" order lane. */
  enabled: boolean;
  /** Send a Telegram message on every verify/unverify flip. */
  telegram_notifications: boolean;
  /** Masked ("********") when set. Blank = fall back to the chat bot. */
  telegram_bot_token: string;
  telegram_chat_id: string;
}

export interface VerificationLogItem {
  id: string;
  user_id: string;
  user_phone: string | null;
  admin_id: string;
  admin_phone: string | null;
  /** true = verified, false = unverified. */
  status: boolean;
  ip_address: string | null;
  created_at: string | null;
}

export interface VerificationLogPage {
  items: VerificationLogItem[];
  total: number;
}

export interface VerificationLogFilters {
  q?: string | null;
  date_from?: string | null;
  date_to?: string | null;
}

export async function fetchVerificationConfig(
  client: AxiosInstance = apiClient,
): Promise<UserVerificationConfig> {
  const { data } = await client.get<{ config: UserVerificationConfig }>(UVERIFY_CONFIG_PATH);
  return data.config;
}

export async function updateVerificationConfig(
  config: Partial<UserVerificationConfig>,
  client: AxiosInstance = apiClient,
): Promise<UserVerificationConfig> {
  const { data } = await client.put<{ config: UserVerificationConfig }>(
    UVERIFY_CONFIG_PATH,
    { config },
  );
  return data.config;
}

export async function fetchVerificationLogs(
  params: { skip?: number; limit?: number } & VerificationLogFilters = {},
  client: AxiosInstance = apiClient,
): Promise<VerificationLogPage> {
  const { skip = 0, limit = 50, q, date_from, date_to } = params;
  const { data } = await client.get<VerificationLogPage>(UVERIFY_LOGS_PATH, {
    params: {
      skip,
      limit,
      ...(q ? { q } : {}),
      ...(date_from ? { date_from } : {}),
      ...(date_to ? { date_to } : {}),
    },
  });
  return data;
}

export async function exportVerificationLogs(
  filters: VerificationLogFilters = {},
  client: AxiosInstance = apiClient,
): Promise<Blob> {
  const { q, date_from, date_to } = filters;
  const { data } = await client.get<Blob>(UVERIFY_LOGS_EXPORT_PATH, {
    responseType: "blob",
    params: {
      ...(q ? { q } : {}),
      ...(date_from ? { date_from } : {}),
      ...(date_to ? { date_to } : {}),
    },
  });
  return data;
}

