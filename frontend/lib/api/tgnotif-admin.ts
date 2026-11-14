/**
 * Telegram order-notification admin API client (tgnotif module).
 *
 * Contract: backend/app/modules/tgnotif/api/routes.py
 *   GET  /admin/telegram-notify            — get config (bot_token masked)
 *   PUT  /admin/telegram-notify            — update config
 *   POST /admin/telegram-notify/test       — send test message
 *   POST /admin/telegram-notify/register-webhook — register webhook with Telegram
 */

import apiClient from "@/lib/api/client";
import type { AxiosInstance } from "axios";

const CONFIG_PATH = "/admin/telegram-notify";
const TEST_PATH = "/admin/telegram-notify/test";
const WEBHOOK_PATH = "/admin/telegram-notify/register-webhook";

export interface TgNotifConfig {
  bot_token: string;
  enabled: boolean;

  // Per-status routing
  chat_id_pending: string;
  chat_id_processing: string;
  chat_id_doing_verified: string;
  chat_id_completed: string;
  chat_id_canceled: string;
  topic_id_pending: string;
  topic_id_processing: string;
  topic_id_doing_verified: string;
  topic_id_completed: string;
  topic_id_canceled: string;

  // Webhook secret
  webhook_secret: string;

  // Field toggles
  show_order_id: boolean;
  show_status: boolean;
  show_items: boolean;
  show_variant_info: boolean;
  show_sku: boolean;
  show_total: boolean;
  show_subtotal: boolean;
  show_shipping: boolean;
  show_tax: boolean;
  show_payment_method: boolean;
  show_payment_status: boolean;
  show_payment_ref: boolean;
  show_coupon: boolean;
  show_order_link: boolean;
  show_date: boolean;
  show_customer_name: boolean;
  show_phone: boolean;
  show_national_code: boolean;
  show_verified: boolean;
  show_ip: boolean;
  show_address: boolean;
  show_notes: boolean;
  show_custom_fields: boolean;
}

export interface TgNotifConfigResponse {
  config: TgNotifConfig;
}

export interface TgNotifTestResult {
  ok: boolean;
  message?: string;
  error?: string;
}

export interface TgNotifWebhookResult {
  ok: boolean;
  webhook_url?: string;
  error?: string;
  telegram_response?: Record<string, unknown>;
}

export async function fetchTgNotifConfig(
  client: AxiosInstance = apiClient,
): Promise<TgNotifConfigResponse> {
  const { data } = await client.get<TgNotifConfigResponse>(CONFIG_PATH);
  return data;
}

export async function updateTgNotifConfig(
  config: Partial<TgNotifConfig>,
  client: AxiosInstance = apiClient,
): Promise<TgNotifConfigResponse> {
  const { data } = await client.put<TgNotifConfigResponse>(CONFIG_PATH, config);
  return data;
}

export async function sendTgNotifTest(
  client: AxiosInstance = apiClient,
): Promise<TgNotifTestResult> {
  const { data } = await client.post<TgNotifTestResult>(TEST_PATH);
  return data;
}

export async function registerTgNotifWebhook(
  client: AxiosInstance = apiClient,
): Promise<TgNotifWebhookResult> {
  const { data } = await client.post<TgNotifWebhookResult>(WEBHOOK_PATH);
  return data;
}
