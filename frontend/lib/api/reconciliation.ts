/**
 * Durable reconciliation findings API client.
 *
 * Contract: docs/architecture/clean-room-operational-capability-and-reconciliation.md
 *   GET  /api/v1/audit/admin/reconciliation/findings   — audit:read
 *   GET  /api/v1/audit/admin/reconciliation/summary    — audit:read
 *   POST /api/v1/audit/admin/reconciliation/run        — audit:write, read-only scanner
 *   PATCH .../findings/{id}/resolve | /dismiss         — audit:write, notes required
 *
 * Findings are read-only observations produced by a scanner that never mutates
 * a financial record. This module therefore exposes no way to change money,
 * orders, refunds, or provider state: the only mutations are finding lifecycle
 * transitions carrying operator notes.
 *
 * Money is integer Iranian rials. Amounts are parsed and formatted as decimal
 * strings — no float conversion, no ArithmeticValue, no client-side summation.
 * Anything that is not a plain integer literal is reported as unavailable
 * rather than coerced or rounded.
 */

import type { AxiosInstance } from "axios";
import apiClient from "@/lib/api/client";

export const RECONCILIATION_FINDINGS_PATH =
  "/audit/admin/reconciliation/findings";
export const RECONCILIATION_SUMMARY_PATH =
  "/audit/admin/reconciliation/summary";
export const RECONCILIATION_RUN_PATH = "/audit/admin/reconciliation/run";
export const LIFECYCLE_AUDIT_RUN_PATH =
  "/audit/admin/reconciliation/audit-lifecycle";

export type ReconciliationSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type ReconciliationStatus =
  "OPEN" | "INVESTIGATING" | "RESOLVED" | "DISMISSED";

export const RECONCILIATION_SEVERITIES: readonly ReconciliationSeverity[] = [
  "CRITICAL",
  "HIGH",
  "MEDIUM",
  "LOW",
];

export const RECONCILIATION_STATUSES: readonly ReconciliationStatus[] = [
  "OPEN",
  "INVESTIGATING",
  "RESOLVED",
  "DISMISSED",
];

export const RECONCILIATION_SEVERITY_LABELS: Record<
  ReconciliationSeverity,
  string
> = {
  CRITICAL: "بحرانی",
  HIGH: "شدید",
  MEDIUM: "متوسط",
  LOW: "پایین",
};

export const RECONCILIATION_STATUS_LABELS: Record<
  ReconciliationStatus,
  string
> = {
  OPEN: "در انتظار بررسی",
  INVESTIGATING: "در حال بررسی",
  RESOLVED: "حل شده",
  DISMISSED: "نادیده گرفته شده",
};

/**
 * Labels for the detectors named in the contract. An unrecognised type is not
 * hidden — the raw registry code is rendered instead, because suppressing a
 * financial finding is worse than showing an unpolished label.
 */
export const RECONCILIATION_TYPE_LABELS: Record<string, string> = {
  PAYMENT_AMOUNT_MISMATCH: "مغایرت مبلغ پرداخت با جمع سفارش",
  PAYMENT_ORDER_STATUS_MISMATCH: "پرداخت تکمیل‌شده با وضعیت ناسازگار سفارش",
  REFUND_TOTAL_EXCEEDS_PAYMENT: "جمع بازپرداخت‌ها بیش از مبلغ پرداخت",
  WEBHOOK_UNPROCESSED: "رویداد وب‌هوک پردازش‌نشده در بازه مجاز",
  ORDER_CANCELED_WITH_SHIPMENT: "سفارش لغوشده با مرسوله فعال",
  ORDER_DELIVERED_SHIPMENT_OPEN: "سفارش تحویلدشده با مرسوله ناتمام",
  ORDER_REFUNDED_UNDERREFUND: "سفارش بازپرداختشده با بازپرداخت ناقص",
};

export const ENTITY_TYPE_LABELS: Record<string, string> = {
  payment: "پرداخت",
  order: "سفارش",
  refund: "بازپرداخت",
  webhook: "وب‌هوک",
  webhook_event: "رویداد وب‌هوک",
  wallet: "کیف پول",
  transaction: "تراکنش",
};

export interface ReconciliationFinding {
  id: string;
  findingType: string;
  findingTypeLabel: string;
  severity: ReconciliationSeverity;
  status: ReconciliationStatus;
  dedupeKey: string | null;
  entityType: string | null;
  entityTypeLabel: string;
  entityId: string | null;
  /** Integer rial amount as a decimal string, or null when absent/unreadable. */
  expectedAmountIrr: string | null;
  actualAmountIrr: string | null;
  expectedAmountDisplay: string | null;
  actualAmountDisplay: string | null;
  detailSummary: string | null;
  firstDetectedAt: string | null;
  lastDetectedAt: string | null;
  occurrenceCount: number | null;
  resolutionNotes: string | null;
  resolvedAt: string | null;
}

export interface ReconciliationSummary {
  /** null means "the backend did not report this", never "zero". */
  total: number | null;
  open: number | null;
  investigating: number | null;
  resolved: number | null;
  dismissed: number | null;
  bySeverity: Partial<Record<ReconciliationSeverity, number>>;
  lastScanAt: string | null;
}

export interface ReconciliationFindingList {
  items: ReconciliationFinding[];
  /** Records returned by the backend that could not be read as findings. */
  invalidCount: number;
  /**
   * Total findings the backend reports, or null when it did not say. Compared
   * against ``items`` to detect that some findings were not delivered — a
   * table showing 20 of 38 findings without saying so hides real ones.
   */
  total: number | null;
  /**
   * Findings the backend holds but this read did not return (pagination or a
   * cap). Null when the total was not reported. Never clamped: an operator
   * must see the number that did not load.
   */
  missingCount: number | null;
}

const SEVERITY_SET: ReadonlySet<string> = new Set<string>(
  RECONCILIATION_SEVERITIES,
);
const STATUS_SET: ReadonlySet<string> = new Set<string>(
  RECONCILIATION_STATUSES,
);

const PLAIN_INTEGER = /^-?\d+$/;

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

function readCount(value: unknown): number | null {
  if (typeof value === "number" && Number.isInteger(value) && value >= 0) {
    return value;
  }
  if (typeof value === "string" && /^\d+$/.test(value)) {
    return Number(value);
  }
  return null;
}

/**
 * Normalises an integer-rial value to a decimal string without arithmetic.
 * Numbers must already be safe integers; anything else (float, NaN) is treated
 * as unavailable so a rounded or lossy amount can never be displayed.
 */
export function parseRialAmount(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return PLAIN_INTEGER.test(trimmed) ? trimmed : null;
  }
  if (typeof value === "number") {
    return Number.isSafeInteger(value) ? String(value) : null;
  }
  return null;
}

/** Groups a decimal integer string into 3-digit blocks, pure string work. */
export function groupDigits(value: string): string {
  const negative = value.startsWith("-");
  const digits = negative ? value.slice(1) : value;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return negative ? `-${grouped}` : grouped;
}

/** Renders an integer-rial amount for display, or null when unavailable. */
export function formatRialAmount(value: unknown): string | null {
  const parsed = parseRialAmount(value);
  if (parsed === null) return null;
  return `${groupDigits(parsed)} ریال`;
}

export function reconciliationTypeLabel(findingType: string): string {
  return RECONCILIATION_TYPE_LABELS[findingType] ?? findingType;
}

export function reconciliationEntityLabel(entityType: string | null): string {
  if (!entityType) return "-";
  return ENTITY_TYPE_LABELS[entityType] ?? entityType;
}

/** Summarises the safe details blob into one line, ignoring unsafe shapes. */
function summarizeDetails(
  details: Record<string, unknown> | null,
): string | null {
  if (!details) return null;
  const parts: string[] = [];
  for (const [key, value] of Object.entries(details)) {
    if (value === null || value === undefined) continue;
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (trimmed) parts.push(`${key}: ${trimmed}`);
    } else if (typeof value === "number" && Number.isFinite(value)) {
      parts.push(`${key}: ${value}`);
    } else if (typeof value === "boolean") {
      parts.push(`${key}: ${value ? "بله" : "خیر"}`);
    }
    if (parts.length >= 3) break;
  }
  return parts.length ? parts.join(" • ") : null;
}

export function normalizeFinding(raw: unknown): ReconciliationFinding | null {
  const record = readRecord(raw);
  if (!record) return null;

  const id = readString(record.id);
  const findingType =
    readString(record.finding_type) ?? readString(record.type);
  const severity = readString(record.severity);
  const status = readString(record.status);

  if (!id || !findingType || !severity || !status) return null;
  if (!SEVERITY_SET.has(severity) || !STATUS_SET.has(status)) return null;

  const entityType = readString(record.entity_type);
  // The backend serialises the DB columns as `expected_amount` /
  // `actual_amount`. This view previously read only `*_irr` spellings, so every
  // amount of every finding silently rendered as "unknown" while the value sat
  // right there in the payload. Accept both spellings: a rename on either side
  // must not blank a financial figure.
  const expectedAmountIrr = parseRialAmount(
    record.expected_amount ?? record.expected_amount_irr,
  );
  const actualAmountIrr = parseRialAmount(
    record.actual_amount ?? record.actual_amount_irr,
  );

  return {
    id,
    findingType,
    findingTypeLabel: reconciliationTypeLabel(findingType),
    severity: severity as ReconciliationSeverity,
    status: status as ReconciliationStatus,
    dedupeKey: readString(record.dedupe_key),
    entityType,
    entityTypeLabel: reconciliationEntityLabel(entityType),
    entityId: readString(record.entity_id),
    expectedAmountIrr,
    actualAmountIrr,
    // Derived from the parsed value, so the display can never disagree with
    // the amount this record reports as available.
    expectedAmountDisplay: formatRialAmount(expectedAmountIrr),
    actualAmountDisplay: formatRialAmount(actualAmountIrr),
    detailSummary: summarizeDetails(readRecord(record.details)),
    firstDetectedAt: readString(record.first_detected_at),
    lastDetectedAt: readString(record.last_detected_at),
    occurrenceCount: readCount(record.occurrence_count),
    resolutionNotes: readString(record.resolution_notes),
    resolvedAt: readString(record.resolved_at),
  };
}

function extractRecords(payload: unknown): unknown[] | null {
  if (Array.isArray(payload)) return payload;
  const record = readRecord(payload);
  if (!record) return null;
  if (Array.isArray(record.items)) return record.items;
  if (Array.isArray(record.findings)) return record.findings;
  return null;
}

export function parseFindingList(payload: unknown): ReconciliationFindingList {
  const records = extractRecords(payload);
  const envelope = readRecord(payload) ?? {};
  // The backend reports the full total alongside a page of items. Without it
  // the caller can only guess whether it received everything.
  const total = readCount(envelope.total);

  if (!records) {
    return { items: [], invalidCount: 0, total, missingCount: null };
  }

  const items: ReconciliationFinding[] = [];
  let invalidCount = 0;

  for (const raw of records) {
    const finding = normalizeFinding(raw);
    if (finding) {
      items.push(finding);
    } else {
      invalidCount += 1;
    }
  }

  // Count everything the backend returned but the caller cannot act on, both
  // unreadable records and findings still sitting behind pagination.
  const delivered = records.length;
  const missingCount = total === null ? null : Math.max(0, total - delivered);

  return { items, invalidCount, total, missingCount };
}

export function parseSummary(payload: unknown): ReconciliationSummary {
  const record = readRecord(payload) ?? {};
  const bySeverity: Partial<Record<ReconciliationSeverity, number>> = {};

  const severitySource =
    readRecord(record.by_severity) ?? readRecord(record.severity_counts);
  if (severitySource) {
    for (const severity of RECONCILIATION_SEVERITIES) {
      const count = readCount(severitySource[severity]);
      if (count !== null) bySeverity[severity] = count;
    }
  }

  return {
    total: readCount(record.total),
    open: readCount(record.open) ?? readCount(record.open_count),
    investigating:
      readCount(record.investigating) ?? readCount(record.investigating_count),
    resolved: readCount(record.resolved) ?? readCount(record.resolved_count),
    dismissed: readCount(record.dismissed) ?? readCount(record.dismissed_count),
    bySeverity,
    lastScanAt:
      readString(record.last_scan_at) ??
      readString(record.last_run_at) ??
      readString(record.generated_at),
  };
}

/** True when the API reported no findings at all — as opposed to no data. */
export function isSummaryEmpty(summary: ReconciliationSummary): boolean {
  return summary.total !== null && summary.total === 0;
}

export function filterFindings(
  findings: ReconciliationFinding[],
  filters: {
    search?: string;
    severity?: string;
    status?: string;
    type?: string;
  },
): ReconciliationFinding[] {
  const query = (filters.search ?? "").trim().toLowerCase();

  return findings.filter((finding) => {
    if (filters.severity && filters.severity !== "all") {
      if (finding.severity !== filters.severity) return false;
    }
    if (filters.status && filters.status !== "all") {
      if (finding.status !== filters.status) return false;
    }
    if (filters.type && filters.type !== "all") {
      if (finding.findingType !== filters.type) return false;
    }
    if (!query) return true;

    return [
      finding.id,
      finding.findingType,
      finding.findingTypeLabel,
      finding.dedupeKey,
      finding.entityId,
      finding.resolutionNotes,
    ].some((field) => field !== null && field.toLowerCase().includes(query));
  });
}

export function validateReconciliationNotes(notes: string): {
  isValid: boolean;
  error: string | null;
} {
  if (notes.trim().length < 5) {
    return {
      isValid: false,
      error: "ثبت یادداشت اپراتور حداقل در ۵ کاراکتر الزامی است.",
    };
  }
  return { isValid: true, error: null };
}

/** The backend rejects page_size above this; it is also the page size used. */
const FINDINGS_PAGE_SIZE = 100;
/**
 * Hard bound on paged reads. The list is a monitoring view, not a data dump:
 * beyond this many findings an operator has a systemic problem to deal with,
 * and the remainder is reported as missing rather than silently dropped.
 */
const MAX_FINDING_PAGES = 20;

export async function fetchReconciliationFindings(
  client: AxiosInstance = apiClient,
): Promise<ReconciliationFindingList> {
  const items: ReconciliationFinding[] = [];
  let invalidCount = 0;
  let total: number | null = null;
  let delivered = 0;

  for (let page = 1; page <= MAX_FINDING_PAGES; page += 1) {
    const res = await client.get<unknown>(RECONCILIATION_FINDINGS_PATH, {
      params: { page, page_size: FINDINGS_PAGE_SIZE },
    });
    const parsed = parseFindingList(res.data);
    items.push(...parsed.items);
    invalidCount += parsed.invalidCount;
    delivered += parsed.items.length + parsed.invalidCount;
    if (parsed.total !== null) total = parsed.total;

    const exhausted =
      parsed.items.length + parsed.invalidCount < FINDINGS_PAGE_SIZE;
    if (exhausted) break;
  }

  return {
    items,
    invalidCount,
    total,
    missingCount: total === null ? null : Math.max(0, total - delivered),
  };
}

export async function fetchReconciliationSummary(
  client: AxiosInstance = apiClient,
): Promise<ReconciliationSummary> {
  const res = await client.get<unknown>(RECONCILIATION_SUMMARY_PATH);
  return parseSummary(res.data);
}

/**
 * Outcome of a read-only scan/audit run, as reported by the backend. A null
 * field means "not reported", never "zero"; a null ``truncated`` means the
 * coverage question was not answered, not that everything was covered.
 */
export interface ScanRunOutcome {
  detected: number | null;
  created: number | null;
  updated: number | null;
  truncated: boolean | null;
}

/**
 * Requests a read-only scanner run. Never triggers a financial action.
 * Returns the run outcome so the caller can tell the operator whether the
 * scanned slice covered the whole ledger or hit its cap.
 */
export async function requestReconciliationScan(
  client: AxiosInstance = apiClient,
): Promise<ScanRunOutcome> {
  const res = await client.post<unknown>(RECONCILIATION_RUN_PATH);
  const record = readRecord(res.data) ?? {};
  return {
    detected: readCount(record.detected),
    created: readCount(record.created),
    updated: readCount(record.updated),
    truncated: typeof record.truncated === "boolean" ? record.truncated : null,
  };
}

/**
 * Requests a read-only order lifecycle audit. Like the payment scan it only
 * reads business records and writes findings; it never moves money or changes
 * an order, shipment or refund. Returns the run outcome so the caller can show
 * the operator what was actually covered — a silent partial audit is not an
 * honest audit.
 */
export async function requestLifecycleAudit(
  client: AxiosInstance = apiClient,
): Promise<ScanRunOutcome> {
  const res = await client.post<unknown>(LIFECYCLE_AUDIT_RUN_PATH);
  const record = readRecord(res.data) ?? {};
  return {
    detected: readCount(record.detected),
    created: readCount(record.created),
    updated: readCount(record.updated),
    truncated: typeof record.truncated === "boolean" ? record.truncated : null,
  };
}

export async function resolveReconciliationFinding(
  id: string,
  notes: string,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.patch(`${RECONCILIATION_FINDINGS_PATH}/${id}/resolve`, {
    resolution_notes: notes.trim(),
  });
}

export async function dismissReconciliationFinding(
  id: string,
  notes: string,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.patch(`${RECONCILIATION_FINDINGS_PATH}/${id}/dismiss`, {
    resolution_notes: notes.trim(),
  });
}
