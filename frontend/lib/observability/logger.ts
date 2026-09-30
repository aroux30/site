/**
 * Client Structured Logging & Sensitive Data Redaction
 * Outputs standard JSON logs with trace correlation and remote telemetry reporting.
 */

import { getActiveTraceId } from "./tracer";
import { maskPhoneNumber, maskNationalId } from "../pii-mask";
import { enqueueOfflinePayload } from "./offline-buffer";

// ponytail: in-memory log rate limiting -> skipped: persistent offline indexedDB log queue, add when offline-first sync needed.

export type LogLevel = "debug" | "info" | "warn" | "error" | "fatal";

const LOG_LEVEL_WEIGHTS: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
  fatal: 50,
};

export interface StructuredLog {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: Record<string, unknown>;
  traceId?: string;
  spanId?: string;
  requestId?: string;
  error?: {
    name: string;
    message: string;
    stack?: string;
    digest?: string;
  };
  url?: string;
  userAgent?: string;
  environment: string;
}

// Keys whose values must always be completely redacted
const SECRET_KEY_PATTERN =
  /^(password|passwd|pass|new_password|current_password|confirm_password|password_confirmation|secret|token|access_token|refresh_token|auth_token|authorization|cookie|api_?key|private_?key)$/i;

// Keys representing financial / card data
const CARD_KEY_PATTERN =
  /^(card_?number|card_?no|pan|cvv|cvv2|cvn|expiry|expiration|sheba|iban)$/i;

// Keys representing phone numbers
const PHONE_KEY_PATTERN = /^(phone|mobile|cell|phone_?number|cell_?phone)$/i;

// Keys representing national identification
const NATIONAL_ID_KEY_PATTERN =
  /^(national_?id|national_?code|melli_?code|mellicode|nationalcode)$/i;

// Regex for credit card numbers in free text (16 digits with optional spaces/dashes)
const CREDIT_CARD_REGEX = /\b(?:\d[ -]?){15}\d\b/g;

// Regex for Bearer tokens in headers / strings
const BEARER_TOKEN_REGEX = /\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b/gi;

/**
 * Masks 16-digit credit card numbers preserving the first 4 and last 4 digits.
 */
export function maskCreditCard(cardNumber: string | null | undefined): string {
  if (!cardNumber) return "";
  const clean = String(cardNumber).replace(/\D/g, "");
  if (clean.length === 16) {
    return `${clean.slice(0, 4)}-****-****-${clean.slice(-4)}`;
  }
  return "[REDACTED_CARD]";
}

/**
 * Deeply sanitizes an object, array, or primitive to mask sensitive PII and credentials.
 */
export function maskSensitiveData(
  data: unknown,
  depth = 0,
  seen = new WeakSet<object>(),
): unknown {
  if (data === null || data === undefined) return data;
  if (depth > 8) return "[MAX_DEPTH]";

  // Handle primitives
  if (typeof data === "string") {
    // Redact bearer tokens
    let sanitized = data.replace(BEARER_TOKEN_REGEX, "Bearer [REDACTED]");
    // Redact 16-digit credit card patterns
    sanitized = sanitized.replace(CREDIT_CARD_REGEX, (match) => {
      const digitsOnly = match.replace(/\D/g, "");
      if (digitsOnly.length === 16) {
        return `${digitsOnly.slice(0, 4)}-****-****-${digitsOnly.slice(-4)}`;
      }
      return match;
    });
    return sanitized;
  }

  if (typeof data !== "object") {
    return data;
  }

  // Prevent cyclical references
  if (seen.has(data)) {
    return "[CIRCULAR]";
  }
  seen.add(data);

  // Handle Arrays
  if (Array.isArray(data)) {
    return data.map((item) => maskSensitiveData(item, depth + 1, seen));
  }

  // Handle Error instances
  if (data instanceof Error) {
    return {
      name: data.name,
      message: maskSensitiveData(data.message, depth + 1, seen),
      stack: data.stack
        ? (maskSensitiveData(data.stack, depth + 1, seen) as string)
        : undefined,
    };
  }

  // Handle plain objects
  const maskedObject: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (SECRET_KEY_PATTERN.test(key)) {
      maskedObject[key] = "[REDACTED]";
    } else if (CARD_KEY_PATTERN.test(key)) {
      maskedObject[key] =
        typeof value === "string" ? maskCreditCard(value) : "[REDACTED_CARD]";
    } else if (PHONE_KEY_PATTERN.test(key)) {
      maskedObject[key] =
        typeof value === "string" ? maskPhoneNumber(value) : value;
    } else if (NATIONAL_ID_KEY_PATTERN.test(key)) {
      maskedObject[key] =
        typeof value === "string" ? maskNationalId(value) : value;
    } else {
      maskedObject[key] = maskSensitiveData(value, depth + 1, seen);
    }
  }

  return maskedObject;
}

/**
 * Logger configuration and transport
 */
class Logger {
  private minLevel: LogLevel = "info";
  private isEnabled = true;
  private telemetryEndpoint: string;
  private errorReportsCount = 0;
  private lastResetTime = Date.now();
  private readonly MAX_REPORTS_PER_MINUTE = 20;

  constructor() {
    const configuredLevel = (
      process.env.NEXT_PUBLIC_LOG_LEVEL || ""
    ).toLowerCase() as LogLevel;
    if (configuredLevel && LOG_LEVEL_WEIGHTS[configuredLevel] !== undefined) {
      this.minLevel = configuredLevel;
    } else {
      this.minLevel = process.env.NODE_ENV === "production" ? "info" : "debug";
    }

    this.isEnabled = process.env.NEXT_PUBLIC_ENABLE_OBSERVABILITY !== "false";
    this.telemetryEndpoint =
      process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT ||
      "/api/v1/observability/client-logs";
  }

  public setLevel(level: LogLevel): void {
    this.minLevel = level;
  }

  public getLevel(): LogLevel {
    return this.minLevel;
  }

  private shouldLog(level: LogLevel): boolean {
    if (!this.isEnabled) return false;
    return LOG_LEVEL_WEIGHTS[level] >= LOG_LEVEL_WEIGHTS[this.minLevel];
  }

  private buildLogEntry(
    level: LogLevel,
    message: string,
    meta?: {
      context?: Record<string, unknown>;
      error?:
        | Error
        | { name: string; message: string; stack?: string; digest?: string };
      requestId?: string;
      spanId?: string;
      traceId?: string;
    },
  ): StructuredLog {
    const isBrowser = typeof window !== "undefined";
    const maskedContext = meta?.context
      ? (maskSensitiveData(meta.context) as Record<string, unknown>)
      : undefined;

    let errorObj: StructuredLog["error"];
    if (meta?.error) {
      errorObj = {
        name: meta.error.name || "Error",
        message: String(maskSensitiveData(meta.error.message || "")),
        stack: meta.error.stack
          ? String(maskSensitiveData(meta.error.stack))
          : undefined,
        digest: "digest" in meta.error ? meta.error.digest : undefined,
      };
    }

    return {
      timestamp: new Date().toISOString(),
      level,
      message: String(maskSensitiveData(message)),
      context: maskedContext,
      traceId: meta?.traceId || getActiveTraceId(),
      spanId: meta?.spanId,
      requestId: meta?.requestId,
      error: errorObj,
      url: isBrowser ? window.location.href : undefined,
      userAgent: isBrowser ? window.navigator.userAgent : undefined,
      environment: process.env.NODE_ENV || "development",
    };
  }

  private sendToTelemetry(logEntry: StructuredLog): void {
    if (typeof window === "undefined") return;

    // Rate limiting to prevent network flood on repeated errors
    const now = Date.now();
    if (now - this.lastResetTime > 60000) {
      this.errorReportsCount = 0;
      this.lastResetTime = now;
    }

    if (this.errorReportsCount >= this.MAX_REPORTS_PER_MINUTE) {
      return;
    }
    this.errorReportsCount++;

    const payload = JSON.stringify(logEntry);

    // If offline, save directly to offline buffer
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      try {
        enqueueOfflinePayload(logEntry, this.telemetryEndpoint);
      } catch {
        // Ignore
      }
      return;
    }

    try {
      if (
        typeof navigator !== "undefined" &&
        typeof navigator.sendBeacon === "function"
      ) {
        const blob = new Blob([payload], { type: "application/json" });
        const sent = navigator.sendBeacon(this.telemetryEndpoint, blob);
        if (sent) return;
      }

      if (typeof fetch === "function") {
        fetch(this.telemetryEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
          keepalive: true,
        }).catch(() => {
          try {
            enqueueOfflinePayload(logEntry, this.telemetryEndpoint);
          } catch {
            // Ignore
          }
        });
      }
    } catch {
      try {
        enqueueOfflinePayload(logEntry, this.telemetryEndpoint);
      } catch {
        // Ignore
      }
    }
  }

  private emit(logEntry: StructuredLog): void {
    const jsonOutput = JSON.stringify(logEntry);

    switch (logEntry.level) {
      case "debug":
        console.debug(jsonOutput);
        break;
      case "info":
        console.info(jsonOutput);
        break;
      case "warn":
        console.warn(jsonOutput);
        break;
      case "error":
      case "fatal":
        console.error(jsonOutput);
        this.sendToTelemetry(logEntry);
        break;
    }
  }

  public debug(message: string, context?: Record<string, unknown>): void {
    if (!this.shouldLog("debug")) return;
    const entry = this.buildLogEntry("debug", message, { context });
    this.emit(entry);
  }

  public info(message: string, context?: Record<string, unknown>): void {
    if (!this.shouldLog("info")) return;
    const entry = this.buildLogEntry("info", message, { context });
    this.emit(entry);
  }

  public warn(message: string, context?: Record<string, unknown>): void {
    if (!this.shouldLog("warn")) return;
    const entry = this.buildLogEntry("warn", message, { context });
    this.emit(entry);
  }

  public error(
    message: string,
    errorOrContext?: Error | Record<string, unknown>,
    context?: Record<string, unknown>,
  ): void {
    if (!this.shouldLog("error")) return;
    const isErr = errorOrContext instanceof Error;
    const error = isErr ? errorOrContext : undefined;
    const combinedContext = isErr ? context : { ...errorOrContext, ...context };

    const entry = this.buildLogEntry("error", message, {
      error,
      context: combinedContext,
      requestId: combinedContext?.requestId as string | undefined,
      traceId: combinedContext?.traceId as string | undefined,
      spanId: combinedContext?.spanId as string | undefined,
    });
    this.emit(entry);
  }

  public fatal(
    message: string,
    errorOrContext?: Error | Record<string, unknown>,
    context?: Record<string, unknown>,
  ): void {
    if (!this.shouldLog("fatal")) return;
    const isErr = errorOrContext instanceof Error;
    const error = isErr ? errorOrContext : undefined;
    const combinedContext = isErr ? context : { ...errorOrContext, ...context };

    const entry = this.buildLogEntry("fatal", message, {
      error,
      context: combinedContext,
      requestId: combinedContext?.requestId as string | undefined,
      traceId: combinedContext?.traceId as string | undefined,
      spanId: combinedContext?.spanId as string | undefined,
    });
    this.emit(entry);
  }
}

export const logger = new Logger();

/**
 * Emits a structured JSON log directly with sensitive data masking.
 */
export function logStructured(payload: {
  level: LogLevel;
  event?: string;
  message?: string;
  [key: string]: unknown;
}): void {
  const { level, event, message, ...rest } = payload;
  const msg = message || event || "structured_log";
  const masked = maskSensitiveData(rest) as Record<string, unknown>;
  const entry = {
    timestamp: new Date().toISOString(),
    level,
    event,
    message: msg,
    ...masked,
  };
  const jsonOutput = JSON.stringify(entry);
  switch (level) {
    case "debug":
      console.debug(jsonOutput);
      break;
    case "info":
      console.info(jsonOutput);
      break;
    case "warn":
      console.warn(jsonOutput);
      break;
    case "error":
    case "fatal":
      console.error(jsonOutput);
      break;
  }
}

export default logger;
