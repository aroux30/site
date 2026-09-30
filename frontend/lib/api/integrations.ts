/**
 * Integration capability registry API client.
 *
 * Contract: docs/architecture/clean-room-operational-capability-and-reconciliation.md
 *   GET /api/v1/integrations/capabilities        — customer-safe records
 *   GET /api/v1/integrations/admin/capabilities  — settings:read, operator-safe records
 *
 * The registry is informational only. No value returned here may drive checkout
 * authorization, provider selection, payment verification, or any financial
 * behaviour, and nothing here claims runtime provider health.
 *
 * Parsing is a strict whitelist: only contract-declared fields are read, so a
 * backend response carrying credentials, merchant IDs, tokens, or raw URLs can
 * never reach a rendered view. Records with an unrecognised status are dropped
 * rather than mapped onto a status the backend did not report.
 */

import type { AxiosInstance } from "axios";
import apiClient from "@/lib/api/client";

export const CUSTOMER_CAPABILITIES_PATH = "/integrations/capabilities";
export const ADMIN_CAPABILITIES_PATH = "/integrations/admin/capabilities";

export const CAPABILITY_CATEGORIES = [
  "payment",
  "shipping",
  "messaging",
  "search",
  "storage",
  "identity",
] as const;

export type CapabilityCategory = (typeof CAPABILITY_CATEGORIES)[number];

export const CAPABILITY_STATUSES = [
  "LIVE",
  "BETA",
  "MOCK",
  "DISABLED",
  "DEGRADED",
  "MAINTENANCE",
] as const;

export type CapabilityStatus = (typeof CAPABILITY_STATUSES)[number];

export const CAPABILITY_CATEGORY_LABELS: Record<CapabilityCategory, string> = {
  payment: "پرداخت",
  shipping: "ارسال و لجستیک",
  messaging: "پیام‌رسانی",
  search: "جستجو",
  storage: "ذخیره‌سازی",
  identity: "هویت و احراز اصالت",
};

export const CAPABILITY_STATUS_LABELS: Record<CapabilityStatus, string> = {
  LIVE: "فعال (LIVE)",
  BETA: "بتا (BETA)",
  MOCK: "شبیه‌ساز (MOCK)",
  DISABLED: "غیرفعال (DISABLED)",
  DEGRADED: "با اختلال (DEGRADED)",
  MAINTENANCE: "در حال نگهداری (MAINTENANCE)",
};

export const CAPABILITY_REASON_LABELS: Record<string, string> = {
  ok: "بدون محدودیت اعلام‌شده",
  not_configured: "پیکربندی نشده است",
  feature_disabled: "ویژگی در تنظیمات غیرفعال است",
  manual_approval: "نیازمند تایید دستی اپراتور",
  runtime_unverified: "سلامت زمان اجرا تایید نشده است",
  maintenance_window: "در بازه نگهداری برنامه‌ریزی‌شده",
  provider_outage: "اختلال در سرویس‌دهنده بیرونی",
  partial_configuration: "پیکربندی ناقص است",
};

export const UNKNOWN_CATEGORY_LABEL = "دسته‌بندی نامشخص";
export const UNKNOWN_REASON_LABEL = "دلیل نامشخص";

export interface IntegrationCapability {
  id: string;
  category: CapabilityCategory | null;
  displayName: string;
  status: CapabilityStatus;
  configured: boolean;
  customerVisible: boolean;
  availableToCustomers: boolean;
  reasonCode: string | null;
  updatedAt: string | null;
}

export interface CapabilityParseResult {
  items: IntegrationCapability[];
  /** Records the backend returned that could not be read as contract records. */
  invalidCount: number;
}

const CATEGORY_SET: ReadonlySet<string> = new Set<string>(CAPABILITY_CATEGORIES);
const STATUS_SET: ReadonlySet<string> = new Set<string>(CAPABILITY_STATUSES);

/** Keeps a backend reason code renderable without trusting it blindly. */
function sanitizeReasonCode(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!/^[a-z0-9_]{1,64}$/.test(trimmed)) return null;
  return trimmed;
}

function readBoolean(value: unknown): boolean {
  return value === true;
}

function readString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function extractRecords(payload: unknown): unknown[] | null {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    if (Array.isArray(record.items)) return record.items;
    if (Array.isArray(record.capabilities)) return record.capabilities;
  }
  return null;
}

export function normalizeCapability(raw: unknown): IntegrationCapability | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;

  const id = readString(record.id);
  const displayName = readString(record.display_name);
  const status = readString(record.status);

  if (!id || !displayName || !status) return null;
  // An unknown status is never coerced: the UI must not assert a lifecycle
  // state the registry did not report.
  if (!STATUS_SET.has(status)) return null;

  const rawCategory = readString(record.category);
  const category =
    rawCategory && CATEGORY_SET.has(rawCategory)
      ? (rawCategory as CapabilityCategory)
      : null;

  const customerVisible = readBoolean(record.customer_visible);

  return {
    id,
    category,
    displayName,
    status: status as CapabilityStatus,
    configured: readBoolean(record.configured),
    customerVisible,
    availableToCustomers:
      customerVisible && readBoolean(record.available_to_customers),
    reasonCode: sanitizeReasonCode(record.reason_code),
    updatedAt: readString(record.updated_at),
  };
}

export function parseCapabilityList(payload: unknown): CapabilityParseResult {
  const records = extractRecords(payload);
  if (!records) return { items: [], invalidCount: 0 };

  const items: IntegrationCapability[] = [];
  let invalidCount = 0;

  for (const raw of records) {
    const capability = normalizeCapability(raw);
    if (capability) {
      items.push(capability);
    } else {
      invalidCount += 1;
    }
  }

  return { items, invalidCount };
}

export function capabilityCategoryLabel(
  capability: Pick<IntegrationCapability, "category">,
): string {
  return capability.category
    ? CAPABILITY_CATEGORY_LABELS[capability.category]
    : UNKNOWN_CATEGORY_LABEL;
}

export function capabilityReasonLabel(
  capability: Pick<IntegrationCapability, "reasonCode">,
): string {
  if (!capability.reasonCode) return UNKNOWN_REASON_LABEL;
  return CAPABILITY_REASON_LABELS[capability.reasonCode] ?? capability.reasonCode;
}

/** A capability with configuration absent is never treated as usable. */
export function isCapabilityUsable(capability: IntegrationCapability): boolean {
  if (!capability.configured) return false;
  return (
    capability.status !== "DISABLED" &&
    capability.status !== "MAINTENANCE" &&
    capability.status !== "MOCK"
  );
}

export async function fetchCustomerCapabilities(
  client: AxiosInstance = apiClient,
): Promise<CapabilityParseResult> {
  const res = await client.get<unknown>(CUSTOMER_CAPABILITIES_PATH);
  return parseCapabilityList(res.data);
}

export async function fetchAdminCapabilities(
  client: AxiosInstance = apiClient,
): Promise<CapabilityParseResult> {
  const res = await client.get<unknown>(ADMIN_CAPABILITIES_PATH);
  return parseCapabilityList(res.data);
}
