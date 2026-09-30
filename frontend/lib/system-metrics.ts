/**
 * System Performance Metrics & Health Monitoring Domain Module (Sprint 6)
 */

import { toPersianDigits } from "./utils";

export type ServiceStatus = "HEALTHY" | "DEGRADED" | "DOWN";

/**
 * ``UNMEASURED`` is not a fourth kind of unhealthy — it is the absence of a
 * measurement. The reports page used to start from a hard-coded block claiming
 * PostgreSQL, Redis, MinIO and Kavenegar were all "عادی و پایدار" with invented
 * latencies, so a 404 on the health probe rendered as a green all-clear. An
 * unmeasured component must never be displayed as a healthy one.
 */
export type ServiceState = ServiceStatus | "UNMEASURED";

export interface ComponentHealth {
  name: string;
  status: ServiceState;
  /** null when no latency was measured — never 0, which reads as "instant". */
  latencyMs: number | null;
  message?: string;
}

/**
 * Every numeric field is nullable, and null means "the backend did not report
 * this", never zero. Fabricating 99.96% uptime is worse than showing nothing:
 * it tells an operator the system is fine when nobody looked.
 */
export interface SystemPerformanceMetrics {
  avgResponseTimeMs: number | null;
  p95ResponseTimeMs: number | null;
  uptimePercent: number | null;
  errorRatePercent: number | null;
  requestsPerSecond: number | null;
  services: ComponentHealth[];
  /**
   * Whether the readiness probe actually answered. False means the whole
   * block is unknown, and that must be stated rather than implied.
   */
  measured: boolean;
  lastUpdated: string | null;
}

export const SERVICE_STATUS_LABELS: Record<ServiceState, string> = {
  HEALTHY: "عادی و پایدار",
  DEGRADED: "کاهش سرعت و تاخیر",
  DOWN: "خارج از دسترس",
  UNMEASURED: "نامشخص",
};

/** The labels the backend's readiness probe uses for each dependency. */
export const SERVICE_KEY_LABELS: Record<string, string> = {
  database: "پایگاه داده اصلی (PostgreSQL)",
  redis: "کلاستر حافظه کش (Redis)",
  elasticsearch: "موتور جستجو (Elasticsearch)",
  storage: "ذخیره‌ساز ابری اشیاء (S3/MinIO)",
};

/**
 * Maps a readiness-probe value onto a display state.
 *
 * The probe reports ``ok`` or ``unavailable``. Anything else — including a
 * value this version does not know — is reported as degraded rather than
 * quietly rounded up to healthy.
 */
export function serviceStateFromCheck(value: unknown): ServiceStatus {
  const normalised = String(value ?? "")
    .trim()
    .toLowerCase();
  if (normalised === "ok") return "HEALTHY";
  if (normalised === "degraded") return "DEGRADED";
  if (normalised === "unavailable" || normalised === "down") return "DOWN";
  return "DEGRADED";
}

export interface ReadinessProbe {
  status: string;
  checks: Record<string, string>;
  measured: boolean;
  checkedAt: string | null;
}

/**
 * Parses a readiness-probe response.
 *
 * ``unavailable``/``ok`` per dependency is the whole payload; there is no
 * latency or uptime in it, so those stay null. A failed probe yields
 * ``measured: false`` and an empty service list rather than a default set.
 */
export function parseReadinessProbe(payload: unknown): ReadinessProbe {
  const record =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : null;
  const rawChecks = record?.checks;

  const checks: Record<string, string> = {};
  if (rawChecks && typeof rawChecks === "object" && !Array.isArray(rawChecks)) {
    for (const [key, value] of Object.entries(
      rawChecks as Record<string, unknown>,
    )) {
      if (typeof value === "string") checks[key] = value;
    }
  }

  return {
    status: typeof record?.status === "string" ? record.status : "unknown",
    checks,
    measured: Object.keys(checks).length > 0,
    checkedAt:
      typeof record?.checked_at === "string" ? record.checked_at : null,
  };
}

/**
 * Builds the displayed component list from a probe result.
 *
 * When the probe did not answer, every dependency is listed as UNMEASURED —
 * visible but explicitly unknown — instead of being omitted or assumed fine.
 */
export function componentsFromProbe(probe: ReadinessProbe): ComponentHealth[] {
  const keys = Object.keys(SERVICE_KEY_LABELS);
  const label = (key: string): string => SERVICE_KEY_LABELS[key] ?? key;

  if (!probe.measured) {
    return keys.map((key) => ({
      name: label(key),
      status: "UNMEASURED" as const,
      latencyMs: null,
    }));
  }

  // Report the probe's own keys, then any expected key it omitted.
  const reported: ComponentHealth[] = Object.keys(probe.checks).map((key) => ({
    name: label(key),
    status: serviceStateFromCheck(probe.checks[key]),
    latencyMs: null,
    message: probe.checks[key],
  }));

  const missing: ComponentHealth[] = keys
    .filter((key) => !(key in probe.checks))
    .map((key) => ({
      name: label(key),
      status: "UNMEASURED" as const,
      latencyMs: null,
    }));

  return [...reported, ...missing];
}

/**
 * Classifies latency into health levels:
 * - < 150ms: optimal
 * - 150ms - 499ms: acceptable
 * - >= 500ms: degraded / slow
 */
export function getLatencySeverity(
  latencyMs: number,
): "optimal" | "acceptable" | "degraded" {
  if (latencyMs < 150) return "optimal";
  if (latencyMs < 500) return "acceptable";
  return "degraded";
}

/**
 * Formats response time latency in Persian digits with unit.
 *
 * A null latency renders as the explicit "unavailable" marker. Returning "0"
 * or "—" would let an unmeasured figure pass for a measurement.
 */
export function formatLatency(latencyMs: number | null): string {
  if (latencyMs === null || !Number.isFinite(latencyMs) || latencyMs < 0) {
    return "نامشخص";
  }
  return `${toPersianDigits(Math.round(latencyMs))} میلی‌ثانیه`;
}

/**
 * Computes an aggregate health score (0-100).
 *
 * Returns null when nothing was measured. An unmeasured system has no score;
 * computing 100 from default values is the bug this function used to enable.
 */
export function calculateHealthScore(
  metrics: SystemPerformanceMetrics,
): number | null {
  const services = metrics.services ?? [];
  const hasAnyMeasurement =
    metrics.measured ||
    services.some((s) => s.status !== "UNMEASURED") ||
    metrics.avgResponseTimeMs !== null ||
    metrics.errorRatePercent !== null ||
    metrics.uptimePercent !== null;

  if (!hasAnyMeasurement) return null;

  let score = 100;

  // Unknown components are not counted as healthy and not as failing: they
  // reduce confidence, which is what a reduced score expresses.
  for (const s of services) {
    if (s.status === "DOWN") score -= 20;
    else if (s.status === "DEGRADED") score -= 8;
    else if (s.status === "UNMEASURED") score -= 5;
  }

  // Penalty for response time, only when it was actually measured.
  if (metrics.avgResponseTimeMs !== null) {
    if (metrics.avgResponseTimeMs > 500) score -= 25;
    else if (metrics.avgResponseTimeMs > 200) score -= 10;
  }

  // Penalty for error rate, only when it was actually measured.
  if (metrics.errorRatePercent !== null) {
    if (metrics.errorRatePercent > 5) score -= 40;
    else if (metrics.errorRatePercent > 1) score -= 15;
  }

  return Math.max(0, Math.min(100, Math.round(score)));
}

/**
 * Evaluates production SLO compliance.
 *
 * A metric that was not measured cannot be compliant or violating, so it is
 * reported as unverifiable instead of silently passing. The previous version
 * compared the hard-coded defaults and announced full compliance on a system
 * whose readiness probe was returning 503.
 */
export function checkSloCompliance(metrics: SystemPerformanceMetrics): {
  isCompliant: boolean;
  violations: string[];
  unverified: string[];
} {
  const violations: string[] = [];
  const unverified: string[] = [];

  if (metrics.avgResponseTimeMs === null) {
    unverified.push("میانگین زمان پاسخ‌دهی اندازه‌گیری نشده است.");
  } else if (metrics.avgResponseTimeMs > 300) {
    violations.push(
      `میانگین زمان پاسخ‌دهی (${formatLatency(metrics.avgResponseTimeMs)}) بیش از سقف استاندارد (۳۰۰ میلی‌ثانیه) است.`,
    );
  }

  if (metrics.errorRatePercent === null) {
    unverified.push("نرخ خطای درخواست‌ها اندازه‌گیری نشده است.");
  } else if (metrics.errorRatePercent > 1.0) {
    violations.push(
      `نرخ خطای سامانه (${toPersianDigits(metrics.errorRatePercent)}٪) بیش از حد مجاز ۱٪ است.`,
    );
  }

  if (metrics.uptimePercent === null) {
    unverified.push("درصد آپ‌تایم اندازه‌گیری نشده است.");
  } else if (metrics.uptimePercent < 99.5) {
    violations.push(
      `درصد آپ‌تایم سامانه (${toPersianDigits(metrics.uptimePercent)}٪) کمتر از تارگت ۹۹.۵٪ است.`,
    );
  }

  // A dependency that is down breaches availability regardless of the
  // latency numbers, so it is a violation rather than a mere unknown.
  for (const service of metrics.services ?? []) {
    if (service.status === "DOWN") {
      violations.push(`${service.name} در دسترس نیست.`);
    } else if (service.status === "UNMEASURED") {
      unverified.push(`وضعیت ${service.name} اندازه‌گیری نشده است.`);
    }
  }

  return {
    isCompliant: violations.length === 0 && unverified.length === 0,
    violations,
    unverified,
  };
}
