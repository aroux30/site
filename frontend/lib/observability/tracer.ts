/**
 * W3C Trace Context (traceparent) Generator & Context Manager
 * Specification: https://www.w3.org/TR/trace-context/
 * Format: 00-${traceId}-${spanId}-${traceFlags}
 */

// ponytail: in-memory trace context -> skipped: distributed async storage, add when server action propagation needed.

const W3C_VERSION = "00";
const SAMPLED_FLAG = "01";
const NOT_SAMPLED_FLAG = "00";
const ZERO_TRACE_ID = "00000000000000000000000000000000";
const ZERO_SPAN_ID = "0000000000000000";

let currentActiveTraceId: string | null = null;

/**
 * Generates random hexadecimal string of given byte length.
 */
function randomHex(bytes: number): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.getRandomValues === "function"
  ) {
    const buffer = new Uint8Array(bytes);
    crypto.getRandomValues(buffer);
    return Array.from(buffer)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }
  // Fallback for environments lacking crypto.getRandomValues
  let result = "";
  while (result.length < bytes * 2) {
    result += Math.random().toString(16).substring(2);
  }
  return result.substring(0, bytes * 2);
}

/**
 * Generates standard 16-byte (32-character hex) W3C Trace ID.
 * Ensures result is non-zero.
 */
export function generateTraceId(): string {
  let traceId = randomHex(16);
  if (traceId === ZERO_TRACE_ID) {
    traceId = "1" + traceId.slice(1);
  }
  return traceId;
}

/**
 * Generates standard 8-byte (16-character hex) W3C Span ID.
 * Ensures result is non-zero.
 */
export function generateSpanId(): string {
  let spanId = randomHex(8);
  if (spanId === ZERO_SPAN_ID) {
    spanId = "1" + spanId.slice(1);
  }
  return spanId;
}

/**
 * Validates a 32-character hex Trace ID.
 */
export function isValidTraceId(traceId: string | null | undefined): boolean {
  if (!traceId || typeof traceId !== "string") return false;
  return /^[0-9a-f]{32}$/i.test(traceId) && traceId !== ZERO_TRACE_ID;
}

/**
 * Validates a 16-character hex Span ID.
 */
export function isValidSpanId(spanId: string | null | undefined): boolean {
  if (!spanId || typeof spanId !== "string") return false;
  return /^[0-9a-f]{16}$/i.test(spanId) && spanId !== ZERO_SPAN_ID;
}

export interface TraceParentInfo {
  version: string;
  traceId: string;
  spanId: string;
  sampled: boolean;
  raw: string;
}

/**
 * Generates unique Request ID for trace correlation.
 */
export function generateRequestId(): string {
  return typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : "req-" + Math.random().toString(36).substring(2, 11) + "-" + Date.now().toString(36);
}

/**
 * Creates a complete trace context bundle containing traceId, spanId, traceparent, and requestId.
 */
export function createTraceContext(
  traceId?: string,
  spanId?: string,
  sampled = true,
): {
  traceId: string;
  spanId: string;
  traceparent: string;
  requestId: string;
} {
  const tId = isValidTraceId(traceId) ? (traceId as string).toLowerCase() : generateTraceId();
  const sId = isValidSpanId(spanId) ? (spanId as string).toLowerCase() : generateSpanId();
  const traceparent = createTraceParent(tId, sId, sampled);
  const requestId = generateRequestId();

  return {
    traceId: tId,
    spanId: sId,
    traceparent,
    requestId,
  };
}

/**
 * Formats a standard W3C traceparent header string.
 */
export function createTraceParent(
  traceId?: string,
  spanId?: string,
  sampled = true,
): string {
  const validTraceId = isValidTraceId(traceId)
    ? (traceId as string).toLowerCase()
    : generateTraceId();
  const validSpanId = isValidSpanId(spanId)
    ? (spanId as string).toLowerCase()
    : generateSpanId();
  const flags = sampled ? SAMPLED_FLAG : NOT_SAMPLED_FLAG;
  return `${W3C_VERSION}-${validTraceId}-${validSpanId}-${flags}`;
}

/**
 * Parses and validates an incoming W3C traceparent header.
 */
export function parseTraceParent(
  header: string | null | undefined,
): TraceParentInfo | null {
  if (!header || typeof header !== "string") return null;

  const parts = header.trim().split("-");
  if (parts.length < 4) return null;

  const version = parts[0];
  const traceId = parts[1];
  const spanId = parts[2];
  const flags = parts[3];

  if (!version || !traceId || !spanId || !flags) return null;

  // Version ff is invalid according to W3C
  if (version === "ff" || !/^[0-9a-f]{2}$/i.test(version)) return null;

  if (!isValidTraceId(traceId) || !isValidSpanId(spanId)) return null;

  if (!/^[0-9a-f]{2}$/i.test(flags)) return null;

  const sampled = (parseInt(flags, 16) & 1) === 1;

  return {
    version,
    traceId: traceId.toLowerCase(),
    spanId: spanId.toLowerCase(),
    sampled,
    raw: header.trim(),
  };
}

/**
 * Gets or initializes the active session/interaction Trace ID.
 */
export function getActiveTraceId(): string {
  if (!currentActiveTraceId) {
    currentActiveTraceId = generateTraceId();
  }
  return currentActiveTraceId;
}

/**
 * Explicitly sets the active Trace ID for the current context.
 */
export function setActiveTraceId(traceId: string | null): void {
  currentActiveTraceId = isValidTraceId(traceId)
    ? (traceId as string).toLowerCase()
    : null;
}

export interface Span {
  name: string;
  traceId: string;
  spanId: string;
  parentSpanId?: string;
  startTime: number;
  end: () => {
    name: string;
    traceId: string;
    spanId: string;
    durationMs: number;
  };
}

/**
 * Starts a timed tracing span for measuring client-side operations.
 */
export function startSpan(name: string, parentSpanId?: string): Span {
  const traceId = getActiveTraceId();
  const spanId = generateSpanId();
  const startTime =
    typeof performance !== "undefined" ? performance.now() : Date.now();

  return {
    name,
    traceId,
    spanId,
    parentSpanId,
    startTime,
    end: () => {
      const endTime =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      const durationMs = Math.round((endTime - startTime) * 100) / 100;
      return {
        name,
        traceId,
        spanId,
        durationMs,
      };
    },
  };
}
