/**
 * Referral & bonus program (admin).
 *
 * Contract: backend/app/modules/referrals/api/routes.py
 *   GET /admin/referrals/config  — referrals:read
 *   PUT /admin/referrals/config  — referrals:write
 *   GET /admin/referrals/history — referrals:read (paid rewards, filterable)
 *
 * The config is one JSONB row (key `referrals.config`) — the whole program is
 * edited as a single object, exactly like the chat widget config. Percent
 * fields accept up to two decimals (1.25 = 1.25%), clamped 0..100 by the
 * backend; money fields are integer Rial (ADR-012). `program_started_at` is
 * the activation cut-off: refreshed on every activation (off → on), never on
 * a plain settings edit, and never sent back in an update (server-owned).
 *
 * Rewards are paid eagerly (signup gift at registration, commission at order
 * completion, recharge bonus at top-up); a periodic sweep retries anything
 * that failed. There is no manual "run sweep" action — the history tab is
 * the audit surface.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const REFERRAL_CONFIG_PATH = "/admin/referrals/config";
export const REFERRAL_HISTORY_PATH = "/admin/referrals/history";
export const REFERRAL_HISTORY_EXPORT_PATH = "/admin/referrals/history/export.csv";

export interface ReferralProgramConfig {
  enabled: boolean;
  /** Per-module switches — independent of the master `enabled`. */
  gift_enabled: boolean;
  commission_enabled: boolean;
  recharge_bonus_enabled: boolean;
  signup_gift_l1: number;
  signup_gift_l2: number;
  commission_percent_l1: number;
  commission_percent_l2: number;
  commission_max_per_event: number;
  min_order_total: number;
  notify_on_gift: boolean;
  notify_on_commission: boolean;
  recharge_bonus_percent: number;
  notify_on_recharge_bonus: boolean;
  gift_notif_text: string;
  commission_notif_text: string;
  recharge_bonus_notif_text: string;
  program_started_at: string | null;
}

export const REWARD_KINDS = ["signup_gift", "commission", "recharge_bonus"] as const;
export type RewardKind = (typeof REWARD_KINDS)[number];

export const REWARD_KIND_LABELS: Record<RewardKind, string> = {
  signup_gift: "هدیهٔ ثبت‌نام",
  commission: "پورسانت خرید",
  recharge_bonus: "بونوس شارژ",
};

export interface RewardHistoryItem {
  id: string;
  kind: RewardKind;
  /** Integer Rial. */
  amount: number;
  created_at: string | null;
  earner_id: string;
  earner_name: string;
  earner_phone: string | null;
  level: number | null;
  /** signup_gift: who joined with the earner's link. */
  invited_user_name: string | null;
  /** commission: which order caused the payout. */
  order_number: string | null;
  /** commission: the order total; recharge_bonus: the top-up amount. */
  payment_amount: number | null;
}

export interface RewardHistoryPage {
  items: RewardHistoryItem[];
  total: number;
}

/** Fetch the full program config. */
export async function fetchReferralConfig(
  client: AxiosInstance = apiClient,
): Promise<ReferralProgramConfig> {
  const { data } = await client.get<{ config: ReferralProgramConfig }>(REFERRAL_CONFIG_PATH);
  return data.config;
}

/** Upsert the program config (only known keys are applied server-side). */
export async function updateReferralConfig(
  config: Partial<ReferralProgramConfig>,
  client: AxiosInstance = apiClient,
): Promise<ReferralProgramConfig> {
  // Never send program_started_at back — the backend owns that stamp.
  const { program_started_at: _ignored, ...payload } = config;
  void _ignored;
  const { data } = await client.put<{ config: ReferralProgramConfig }>(
    REFERRAL_CONFIG_PATH,
    { config: payload },
  );
  return data.config;
}

export interface RewardHistoryFilters {
  kind?: RewardKind | null;
  /** Free-text search: earner name/phone, order number, invited user. */
  q?: string | null;
  /** ISO date (YYYY-MM-DD), inclusive. */
  dateFrom?: string | null;
  /** ISO date (YYYY-MM-DD), inclusive. */
  dateTo?: string | null;
}

function _filterParams(filters: RewardHistoryFilters): Record<string, string> {
  const params: Record<string, string> = {};
  if (filters.kind) params.kind = filters.kind;
  if (filters.q?.trim()) params.q = filters.q.trim();
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  return params;
}

/** Fetch one page of paid reward history (filtered). */
export async function fetchRewardHistory(
  params: RewardHistoryFilters & { skip?: number; limit?: number } = {},
  client: AxiosInstance = apiClient,
): Promise<RewardHistoryPage> {
  const { skip = 0, limit = 25 } = params;
  const { data } = await client.get<RewardHistoryPage>(REFERRAL_HISTORY_PATH, {
    params: { ..._filterParams(params), skip, limit },
  });
  return data;
}

/** Download the FILTERED history as CSV (Excel-safe, UTF-8 BOM). */
export async function exportRewardHistory(
  filters: RewardHistoryFilters = {},
  client: AxiosInstance = apiClient,
): Promise<Blob> {
  const { data } = await client.get<Blob>(REFERRAL_HISTORY_EXPORT_PATH, {
    params: _filterParams(filters),
    responseType: "blob",
  });
  return data;
}
