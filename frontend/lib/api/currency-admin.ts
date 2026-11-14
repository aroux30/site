/**
 * USD→Toman rate updater (admin).
 *
 * Contract: backend/app/modules/currency/api/routes.py
 *   GET  /admin/currency/config      — currency:read
 *   PUT  /admin/currency/config      — currency:write
 *   POST /admin/currency/update-now  — currency:write (the plugin's manual button)
 *   GET  /admin/currency/history     — currency:read
 *   GET  /admin/currency/history/export.csv — currency:read
 *
 * The config is one JSONB row (key `currency.usd_rate`). Money is integer
 * Rial on the wire (ADR-012); the admin UI edits the manual rate in Toman.
 * `last_*` fields are server-owned runtime state — the backend ignores them
 * on write, and the update helper strips them so a stale echo can never
 * round-trip.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const CURRENCY_CONFIG_PATH = "/admin/currency/config";
export const CURRENCY_UPDATE_NOW_PATH = "/admin/currency/update-now";
export const CURRENCY_HISTORY_PATH = "/admin/currency/history";
export const CURRENCY_HISTORY_EXPORT_PATH = "/admin/currency/history/export.csv";

export interface UsdRateConfig {
  enabled: boolean;
  api_enabled: boolean;
  /** Integer Rial (0 = unset). The UI edits it in Toman. */
  manual_rate_rial: number;
  update_interval_minutes: number;
  /** Rounding step in Toman (plugin default 100). */
  price_rounding_toman: number;
  /** History rows on/off — does NOT stop price updates. */
  log_enabled: boolean;
  // Server-owned runtime state (read-only here).
  last_rate_rial: number;
  last_source: string | null;
  last_update_at: string | null;
  last_attempt_at: string | null;
  last_status: string | null;
  last_error: string | null;
  last_updated_count: number;
}

export interface UsdRateConfigResponse {
  config: UsdRateConfig;
  /** ISO timestamp of the next automatic run (null = disabled). */
  next_run_at: string | null;
  /** How many variants currently carry a USD price. */
  managed_variants: number;
}

export interface UpdateNowResult {
  status: "success" | "failed";
  rate_rial: number | null;
  rate_source: string | null;
  updated_count: number;
  scanned: number;
  error: string | null;
}

export interface RateChangeDetail {
  variant_id: string;
  sku: string;
  product_id: string;
  product_name: string;
  usd_price: string;
  usd_sale_price: string | null;
  old_price: number;
  old_compare: number | null;
  new_price: number;
  new_compare: number | null;
}

export interface RateHistoryItem {
  id: string;
  /** Integer Rial. */
  rate_rial: number;
  rate_source: string;
  updated_count: number;
  scheduled: boolean;
  status: "success" | "failed";
  error: string | null;
  details: { scanned?: number; changed?: RateChangeDetail[] } | null;
  created_at: string | null;
}

export interface RateHistoryPage {
  items: RateHistoryItem[];
  total: number;
}

/** Server-owned keys the UI must never send back on an update. */
const SERVER_OWNED_PREFIX = "last_";

/** Fetch the full updater config + status. */
export async function fetchUsdRateConfig(
  client: AxiosInstance = apiClient,
): Promise<UsdRateConfigResponse> {
  const { data } = await client.get<UsdRateConfigResponse>(CURRENCY_CONFIG_PATH);
  return data;
}

/** Upsert the config (only non-server-owned keys are applied server-side). */
export async function updateUsdRateConfig(
  config: Partial<UsdRateConfig>,
  client: AxiosInstance = apiClient,
): Promise<UsdRateConfigResponse> {
  const payload: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(config)) {
    if (key.startsWith(SERVER_OWNED_PREFIX)) continue;
    payload[key] = value;
  }
  const { data } = await client.put<UsdRateConfigResponse>(CURRENCY_CONFIG_PATH, {
    config: payload,
  });
  return data;
}

/** Run one sweep immediately (the plugin's "update now" button). */
export async function runUsdRateUpdateNow(
  client: AxiosInstance = apiClient,
): Promise<UpdateNowResult> {
  const { data } = await client.post<UpdateNowResult>(CURRENCY_UPDATE_NOW_PATH);
  return data;
}

export interface RateHistoryFilters {
  status?: "success" | "failed" | null;
  /** Free text over the change details: SKU, product name. */
  q?: string | null;
  /** ISO date (YYYY-MM-DD), inclusive. */
  dateFrom?: string | null;
  dateTo?: string | null;
}

function _filterParams(filters: RateHistoryFilters): Record<string, string> {
  const params: Record<string, string> = {};
  if (filters.status) params.status = filters.status;
  if (filters.q?.trim()) params.q = filters.q.trim();
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  return params;
}

/** Fetch one page of sweep history (filtered), newest first. */
export async function fetchRateHistory(
  params: RateHistoryFilters & { skip?: number; limit?: number } = {},
  client: AxiosInstance = apiClient,
): Promise<RateHistoryPage> {
  const { skip = 0, limit = 25 } = params;
  const { data } = await client.get<RateHistoryPage>(CURRENCY_HISTORY_PATH, {
    params: { ..._filterParams(params), skip, limit },
  });
  return data;
}

/** Download the FILTERED history as CSV (Excel-safe, UTF-8 BOM). */
export async function exportRateHistory(
  filters: RateHistoryFilters = {},
  client: AxiosInstance = apiClient,
): Promise<Blob> {
  const { data } = await client.get<Blob>(CURRENCY_HISTORY_EXPORT_PATH, {
    params: _filterParams(filters),
    responseType: "blob",
  });
  return data;
}
