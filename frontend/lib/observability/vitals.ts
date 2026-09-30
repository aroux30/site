/**
 * Core Web Vitals Monitoring
 * Measures LCP, CLS, FID, INP, TTFB, and FCP using native browser PerformanceObserver API.
 * Correlates performance metrics with W3C Trace IDs.
 */

import { getActiveTraceId } from "./tracer";
import { logger } from "./logger";

// ponytail: native performance observers -> skipped: external web-vitals npm package, add when advanced polyfills needed.

export type VitalMetricName = "LCP" | "CLS" | "FID" | "INP" | "TTFB" | "FCP";
export type VitalRating = "good" | "needs-improvement" | "poor";

export interface WebVitalMetric {
  name: VitalMetricName;
  value: number;
  rating: VitalRating;
  delta?: number;
  id?: string;
  navigationType?: string;
  traceId: string;
  timestamp: number;
}

export interface WebVitalsSummary {
  lcp?: WebVitalMetric;
  cls?: WebVitalMetric;
  fid?: WebVitalMetric;
  inp?: WebVitalMetric;
  ttfb?: WebVitalMetric;
  fcp?: WebVitalMetric;
}

// Google Web Vitals Thresholds
const VITAL_THRESHOLDS: Record<
  VitalMetricName,
  { good: number; needsImprovement: number }
> = {
  LCP: { good: 2500, needsImprovement: 4000 }, // ms
  CLS: { good: 0.1, needsImprovement: 0.25 }, // score
  FID: { good: 100, needsImprovement: 300 }, // ms
  INP: { good: 200, needsImprovement: 500 }, // ms
  TTFB: { good: 800, needsImprovement: 1800 }, // ms
  FCP: { good: 1800, needsImprovement: 3000 }, // ms
};

/**
 * Classifies a metric value into "good", "needs-improvement", or "poor".
 */
export function getVitalRating(
  name: VitalMetricName,
  value: number,
): VitalRating {
  const threshold = VITAL_THRESHOLDS[name];
  if (!threshold) return "good";

  if (value <= threshold.good) return "good";
  if (value <= threshold.needsImprovement) return "needs-improvement";
  return "poor";
}

class WebVitalsCollector {
  private summary: WebVitalsSummary = {};
  private listeners: Array<(metric: WebVitalMetric) => void> = [];

  /**
   * Records a vital metric, notifies listeners, and logs slow metrics.
   */
  public recordVital(
    name: VitalMetricName,
    value: number,
    meta?: { id?: string; delta?: number; navigationType?: string },
  ): WebVitalMetric {
    const roundedValue =
      name === "CLS"
        ? Math.round(value * 1000) / 1000
        : Math.round(value * 100) / 100;
    const rating = getVitalRating(name, roundedValue);
    const traceId = getActiveTraceId();

    const metric: WebVitalMetric = {
      name,
      value: roundedValue,
      rating,
      id: meta?.id,
      delta: meta?.delta,
      navigationType: meta?.navigationType,
      traceId,
      timestamp: Date.now(),
    };

    const key = name.toLowerCase() as keyof WebVitalsSummary;
    this.summary[key] = metric;

    // Log degraded/poor metrics as warning, good as debug
    if (rating === "poor") {
      logger.warn(`Poor Web Vital detected: ${name} = ${roundedValue}`, {
        vital: name,
        value: roundedValue,
        rating,
        traceId,
      });
    } else if (rating === "needs-improvement") {
      logger.info(`Web Vital needs improvement: ${name} = ${roundedValue}`, {
        vital: name,
        value: roundedValue,
        rating,
        traceId,
      });
    } else {
      logger.debug(
        `Web Vital recorded: ${name} = ${roundedValue} (${rating})`,
        {
          vital: name,
          value: roundedValue,
          rating,
          traceId,
        },
      );
    }

    this.listeners.forEach((listener) => {
      try {
        listener(metric);
      } catch {
        // Prevent listener failures from breaking telemetry
      }
    });

    return metric;
  }

  public getSummary(): WebVitalsSummary {
    return { ...this.summary };
  }

  public addListener(cb: (metric: WebVitalMetric) => void): () => void {
    this.listeners.push(cb);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== cb);
    };
  }

  public clear(): void {
    this.summary = {};
  }
}

export const webVitals = new WebVitalsCollector();

/**
 * Initializes browser PerformanceObservers to collect Web Vitals.
 * Safe for execution in browser; no-op during SSR.
 */
export function initWebVitals(
  onReport?: (metric: WebVitalMetric) => void,
): () => void {
  if (
    typeof window === "undefined" ||
    typeof PerformanceObserver === "undefined"
  ) {
    return () => {};
  }

  const observers: PerformanceObserver[] = [];
  let removeListener: (() => void) | null = null;

  if (onReport) {
    removeListener = webVitals.addListener(onReport);
  }

  // 1. Navigation Timing (TTFB)
  try {
    const navEntries = performance.getEntriesByType("navigation");
    if (navEntries.length > 0) {
      const nav = navEntries[0] as PerformanceNavigationTiming;
      const ttfb = nav.responseStart ? nav.responseStart - nav.requestStart : 0;
      if (ttfb > 0) {
        webVitals.recordVital("TTFB", ttfb, { navigationType: nav.type });
      }
    }
  } catch {
    // Ignore unsupported navigation entries
  }

  // 2. Paint Timing (FCP)
  try {
    const paintObserver = new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries()) {
        if (entry.name === "first-contentful-paint") {
          webVitals.recordVital("FCP", entry.startTime);
        }
      }
    });
    paintObserver.observe({ type: "paint", buffered: true });
    observers.push(paintObserver);
  } catch {
    // Paint timing not supported
  }

  // 3. Largest Contentful Paint (LCP)
  try {
    const lcpObserver = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      const lastEntry = entries[entries.length - 1];
      if (lastEntry) {
        // ``id`` is defined on PerformanceElementTiming (the LCP entry type)
        // but is absent from the base PerformanceEntry interface.
        const lcpId = (lastEntry as PerformanceEntry & { id?: string }).id;
        webVitals.recordVital("LCP", lastEntry.startTime, { id: lcpId });
      }
    });
    lcpObserver.observe({ type: "largest-contentful-paint", buffered: true });
    observers.push(lcpObserver);
  } catch {
    // LCP not supported
  }

  // 4. Cumulative Layout Shift (CLS)
  try {
    let clsValue = 0;
    const clsObserver = new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries()) {
        const layoutShift = entry as unknown as {
          hadRecentInput?: boolean;
          value?: number;
        };
        if (
          !layoutShift.hadRecentInput &&
          typeof layoutShift.value === "number"
        ) {
          clsValue += layoutShift.value;
          webVitals.recordVital("CLS", clsValue);
        }
      }
    });
    clsObserver.observe({ type: "layout-shift", buffered: true });
    observers.push(clsObserver);
  } catch {
    // CLS not supported
  }

  // 5. First Input Delay (FID) / Interaction
  try {
    const fidObserver = new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries()) {
        const firstInput = entry as unknown as {
          processingStart?: number;
          startTime: number;
        };
        if (typeof firstInput.processingStart === "number") {
          const fid = firstInput.processingStart - firstInput.startTime;
          webVitals.recordVital("FID", fid);
        }
      }
    });
    fidObserver.observe({ type: "first-input", buffered: true });
    observers.push(fidObserver);
  } catch {
    // FID not supported
  }

  return () => {
    observers.forEach((obs) => obs.disconnect());
    if (removeListener) removeListener();
  };
}
