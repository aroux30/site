/**
 * Operational Exceptions & Service Health Domain Module (Sprint 4)
 * Aligned with backend DTO and API specifications:
 * - GET /api/v1/audit/admin/exceptions
 * - PATCH /api/v1/audit/admin/exceptions/{id}/assign
 * - PATCH /api/v1/audit/admin/exceptions/{id}/resolve
 */

export type SystemExceptionType =
  | "PRICE_MISMATCH"
  | "INVENTORY_CONFLICT"
  | "PAYMENT_TIMEOUT"
  | "DUPLICATE_ORDER"
  | "WEBHOOK_REPLAY"
  | "GATEWAY_ERROR"
  | "PAYMENT_MISMATCH";

export type ExceptionSeverity =
  | "LOW"
  | "MEDIUM"
  | "HIGH"
  | "CRITICAL"
  | "WARNING"
  | "INFO";

export type ExceptionStatus =
  | "OPEN"
  | "INVESTIGATING"
  | "RESOLVED"
  | "IGNORED";

export const EXCEPTION_TYPE_LABELS: Record<SystemExceptionType, string> = {
  PRICE_MISMATCH: "مغایرت قیمت کالا/سفارش",
  INVENTORY_CONFLICT: "تداخل موجودی و کسری انبار",
  PAYMENT_TIMEOUT: "تایم‌اوت تراکنش پرداخت",
  DUPLICATE_ORDER: "سفارش تکراری همزمان",
  WEBHOOK_REPLAY: "تکرار نامعتبر وب‌هوک",
  GATEWAY_ERROR: "خطای ارتباط با درگاه بانکی",
  PAYMENT_MISMATCH: "مغایرت مبلغ پرداختی درگاه",
};

export const EXCEPTION_SEVERITY_LABELS: Record<ExceptionSeverity, string> = {
  CRITICAL: "بحرانی (Critical)",
  HIGH: "شدید (High)",
  MEDIUM: "متوسط (Medium)",
  LOW: "پایین (Low)",
  WARNING: "هشدار",
  INFO: "اطلاعاتی",
};

export const EXCEPTION_STATUS_LABELS: Record<ExceptionStatus, string> = {
  OPEN: "در انتظار بررسی",
  INVESTIGATING: "در حال بررسی کارشناس",
  RESOLVED: "حل شده",
  IGNORED: "نادیده گرفته شد",
};

export interface OperationalExceptionResponse {
  id: string;
  exception_type: SystemExceptionType;
  severity: ExceptionSeverity;
  status: ExceptionStatus;
  entity_type?: "order" | "payment" | "variant" | "webhook" | string;
  entity_id?: string;
  details?: Record<string, unknown> | null;
  payload?: Record<string, unknown> | null;
  owner_id?: string | null;
  resolved_at?: string | null;
  resolution_notes?: string | null;
  created_at: string;
}

/**
 * A rendered operational-exception record.
 *
 * Carries no expected/actual amount fields by design. This surface is fed only
 * by `GET /audit/admin/exceptions`, which does not report reconciliation
 * amounts; amount comparison lives exclusively in the durable reconciliation
 * findings view, where the values come from the scanner.
 */
export interface SystemException {
  id: string;
  type: SystemExceptionType;
  severity: ExceptionSeverity;
  status: ExceptionStatus;
  title: string;
  message: string;
  entityType?: "order" | "payment" | "variant" | "webhook" | string;
  entityId?: string;
  ownerId?: string | null;
  notes?: string | null;
  resolvedBy?: string | null;
  resolvedAt?: string | null;
  createdAt: string;
}

/** Reads a contract field without trusting the transport shape. */
export function readOptionalString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

/**
 * Maps a `OperationalExceptionResponse` onto the rendered record.
 *
 * Returns null only when the record has no usable identity. Anything else the
 * backend omitted is rendered as absent rather than filled in with a guess: an
 * unrecognised status becomes OPEN (still needs attention) instead of being
 * assumed handled, and the backend's DISMISSED is grouped with IGNORED.
 */
export function normalizeOperationalException(
  raw: unknown
): SystemException | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;

  const id = readOptionalString(record.id);
  if (!id) return null;

  const rawType = readOptionalString(record.exception_type);
  const type: SystemExceptionType =
    rawType && rawType in EXCEPTION_TYPE_LABELS
      ? (rawType as SystemExceptionType)
      : "GATEWAY_ERROR";

  const rawSeverity = readOptionalString(record.severity);
  const severity: ExceptionSeverity =
    rawSeverity && rawSeverity in EXCEPTION_SEVERITY_LABELS
      ? (rawSeverity as ExceptionSeverity)
      : "MEDIUM";

  const rawStatus = readOptionalString(record.status);
  const status: ExceptionStatus =
    rawStatus === "DISMISSED"
      ? "IGNORED"
      : rawStatus && rawStatus in EXCEPTION_STATUS_LABELS
        ? (rawStatus as ExceptionStatus)
        : "OPEN";

  const details =
    record.details && typeof record.details === "object"
      ? (record.details as Record<string, unknown>)
      : null;

  return {
    id,
    type,
    severity,
    status,
    title: EXCEPTION_TYPE_LABELS[type],
    message: details ? (readOptionalString(details.message) ?? "") : "",
    entityType: readOptionalString(record.entity_type) ?? undefined,
    entityId: readOptionalString(record.entity_id) ?? undefined,
    ownerId: readOptionalString(record.owner_id),
    notes: readOptionalString(record.resolution_notes),
    resolvedAt: readOptionalString(record.resolved_at),
    createdAt: readOptionalString(record.created_at) ?? "",
  };
}

export interface ExceptionResolutionPayload {
  action: "resolve" | "ignore" | "assign";
  notes?: string;
  ownerId?: string;
}

export type ProviderStatusType = "ACTIVE" | "FAILED" | "DEGRADED";

/**
 * Communications provider state.
 *
 * Deliberately has no `isHealthy` flag. A local settings value such as
 * `is_active` means the provider is *configured*, not that it is reachable —
 * and operational screens must not present the one as the other. Runtime health
 * is only ever `status`, which exists when a health signal was actually
 * returned, and `healthVerified` records whether that happened.
 */
export interface ProviderHealthStatus {
  service: "sms" | "email";
  provider: string;
  /** Present only when a backend health signal reported a runtime state. */
  status?: ProviderStatusType;
  /** True when the operator has supplied configuration for this provider. */
  isConfigured: boolean;
  /** True only when a runtime health result was actually received. */
  healthVerified: boolean;
  creditBalance?: number | null;
  lastCheckedAt?: string;
  error?: string | null;
}

export interface NotificationGuardResult {
  /** True only when a health signal explicitly reported a failure. */
  hasOutage: boolean;
  unconfiguredCount: number;
  /** Providers whose configuration exists but whose health is unverified. */
  unverifiedCount: number;
  warnings: string[];
}

/**
 * Validates resolution or assignment payload before submission.
 */
export function validateResolution(payload: ExceptionResolutionPayload): {
  isValid: boolean;
  error: string | null;
} {
  if (!payload.action || !["resolve", "ignore", "assign"].includes(payload.action)) {
    return {
      isValid: false,
      error: "عملیات انتخابی نامعتبر است.",
    };
  }

  if (payload.action === "assign") {
    if (!payload.ownerId || !payload.ownerId.trim()) {
      return {
        isValid: false,
        error: "شناسه کارشناس بررسی‌کننده الزامی است.",
      };
    }
    return { isValid: true, error: null };
  }

  const notes = (payload.notes || "").trim();
  if (!notes || notes.length < 5) {
    return {
      isValid: false,
      error: "ثبت یادداشت و علت اقدام حداقل در ۵ کاراکتر الزامی است.",
    };
  }

  return {
    isValid: true,
    error: null,
  };
}

/**
 * Filters system exceptions by search keyword, severity, and resolution status.
 */
export function filterExceptions(
  exceptions: SystemException[],
  filters: {
    search?: string;
    type?: string;
    severity?: string;
    status?: string;
  }
): SystemException[] {
  return exceptions.filter((ex) => {
    if (filters.search) {
      const q = filters.search.trim().toLowerCase();
      const matchesSearch =
        ex.id.toLowerCase().includes(q) ||
        ex.title.toLowerCase().includes(q) ||
        ex.message.toLowerCase().includes(q) ||
        (ex.entityId && ex.entityId.toLowerCase().includes(q));
      if (!matchesSearch) return false;
    }

    if (filters.type && filters.type !== "all" && ex.type !== filters.type) {
      return false;
    }

    if (filters.severity && filters.severity !== "all" && ex.severity !== filters.severity) {
      return false;
    }

    if (filters.status && filters.status !== "all" && ex.status !== filters.status) {
      return false;
    }

    return true;
  });
}

/**
 * Evaluates communications provider state (SMS & Email) conservatively.
 *
 * An alert is only raised from evidence: a runtime health signal that reported
 * a failure, or configuration that is absent. A provider that is configured but
 * has no verified health signal is surfaced as *unverified* — it must not be
 * announced as either healthy or down, because neither is known.
 */
export function checkNotificationGuard(
  providers: ProviderHealthStatus[]
): NotificationGuardResult {
  const warnings: string[] = [];
  let hasOutage = false;
  let unconfiguredCount = 0;
  let unverifiedCount = 0;

  for (const p of providers) {
    const serviceName = p.service === "sms" ? "پیامک (SMS)" : "ایمیل (Email)";

    if (!p.isConfigured) {
      unconfiguredCount++;
      warnings.push(
        `تنظیمات سرویس‌دهنده ${serviceName} در سامانه پیکربندی نشده است.`
      );
      continue;
    }

    if (!p.healthVerified) {
      unverifiedCount++;
      warnings.push(
        `سلامت زمان اجرای سرویس‌دهنده ${serviceName} (${p.provider}) تأیید نشده است؛ وجود پیکربندی به‌تنهایی به‌معنای فعال بودن سرویس نیست.`
      );
      continue;
    }

    if (p.status === "FAILED") {
      hasOutage = true;
      warnings.push(
        `اختلال بحرانی در ارتباط با پرووایدر ${serviceName} (${p.provider}): ${p.error || "سرویس از دسترس خارج شده است"} (Fail-Closed active)`
      );
    } else if (p.status === "DEGRADED") {
      warnings.push(
        `کاهش کیفیت یا تاخیر در پاسخگویی سرویس ${serviceName} (${p.provider}).`
      );
    }
  }

  return {
    hasOutage,
    unconfiguredCount,
    unverifiedCount,
    warnings,
  };
}
