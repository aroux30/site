/**
 * Frontend Performance Monitoring & Latency Metrics
 * Tracks API latencies, calculates percentiles (P50, P95, P99), and detects performance bottlenecks.
 */

// ponytail: in-memory ring buffer -> skipped: indexedDB persistent metrics store, add when offline analytics needed.

export interface ApiLatencyRecord {
  endpoint: string;
  method: string;
  durationMs: number;
  status: number;
  timestamp: number;
  traceId?: string;
  requestId?: string;
}

export interface LatencySummary {
  count: number;
  p50: number;
  p95: number;
  p99: number;
  mean: number;
  min: number;
  max: number;
  errorRatePercent: number;
  slowRequestsCount: number;
}

export interface PageNavigationMetric {
  path: string;
  durationMs: number;
  ttfbMs?: number;
  domInteractiveMs?: number;
  timestamp: number;
}

export const SLOW_API_THRESHOLD_MS = 1500;
export const SLOW_PAGE_THRESHOLD_MS = 3000;

class MetricsCollector {
  private apiRecords: ApiLatencyRecord[] = [];
  private pageNavigations: PageNavigationMetric[] = [];
  private readonly MAX_RECORDS = 500;

  /**
   * Records a completed API call latency measurement.
   */
  public recordApiLatency(
    endpoint: string,
    method: string,
    durationMs: number,
    status: number,
    meta?: { traceId?: string; requestId?: string },
  ): void {
    const record: ApiLatencyRecord = {
      endpoint,
      method: method.toUpperCase(),
      durationMs: Math.max(0, Math.round(durationMs * 100) / 100),
      status,
      timestamp: Date.now(),
      traceId: meta?.traceId,
      requestId: meta?.requestId,
    };

    this.apiRecords.push(record);
    if (this.apiRecords.length > this.MAX_RECORDS) {
      this.apiRecords.shift();
    }
  }

  /**
   * Calculates nearest-rank percentile value from numeric array.
   */
  public calculatePercentile(values: number[], percentile: number): number {
    if (!values.length) return 0;
    if (values.length === 1) return values[0] ?? 0;

    const sorted = [...values].sort((a, b) => a - b);
    const index = (percentile / 100) * (sorted.length - 1);
    const lower = Math.floor(index);
    const upper = Math.ceil(index);
    const weight = index - lower;

    const valLower = sorted[lower] ?? 0;
    const valUpper = sorted[upper] ?? 0;

    if (lower === upper) {
      return Math.round(valLower * 100) / 100;
    }

    const interpolated = valLower * (1 - weight) + valUpper * weight;
    return Math.round(interpolated * 100) / 100;
  }

  /**
   * Generates summary statistics (P50, P95, P99, error rate) for API requests.
   */
  public getApiLatencySummary(endpointFilter?: string): LatencySummary {
    const filtered = endpointFilter
      ? this.apiRecords.filter((r) => r.endpoint.includes(endpointFilter))
      : this.apiRecords;

    if (filtered.length === 0) {
      return {
        count: 0,
        p50: 0,
        p95: 0,
        p99: 0,
        mean: 0,
        min: 0,
        max: 0,
        errorRatePercent: 0,
        slowRequestsCount: 0,
      };
    }

    const durations = filtered.map((r) => r.durationMs);
    const sum = durations.reduce((acc, curr) => acc + curr, 0);
    const mean = Math.round((sum / durations.length) * 100) / 100;
    const min = Math.min(...durations);
    const max = Math.max(...durations);

    const errorCount = filtered.filter(
      (r) => r.status >= 400 || r.status === 0,
    ).length;
    const errorRatePercent =
      Math.round((errorCount / filtered.length) * 10000) / 100;

    const slowRequestsCount = filtered.filter(
      (r) => r.durationMs >= SLOW_API_THRESHOLD_MS,
    ).length;

    return {
      count: filtered.length,
      p50: this.calculatePercentile(durations, 50),
      p95: this.calculatePercentile(durations, 95),
      p99: this.calculatePercentile(durations, 99),
      mean,
      min,
      max,
      errorRatePercent,
      slowRequestsCount,
    };
  }

  /**
   * Records a client-side page navigation duration.
   */
  public recordPageNavigation(
    path: string,
    durationMs: number,
    meta?: Partial<PageNavigationMetric>,
  ): void {
    const record: PageNavigationMetric = {
      path,
      durationMs: Math.max(0, Math.round(durationMs * 100) / 100),
      ttfbMs: meta?.ttfbMs,
      domInteractiveMs: meta?.domInteractiveMs,
      timestamp: Date.now(),
    };

    this.pageNavigations.push(record);
    if (this.pageNavigations.length > this.MAX_RECORDS) {
      this.pageNavigations.shift();
    }
  }

  /**
   * Returns recorded page navigations.
   */
  public getPageNavigations(): PageNavigationMetric[] {
    return [...this.pageNavigations];
  }

  /**
   * Returns list of slow API requests exceeding threshold.
   */
  public getSlowRequests(
    thresholdMs = SLOW_API_THRESHOLD_MS,
  ): ApiLatencyRecord[] {
    return this.apiRecords.filter((r) => r.durationMs >= thresholdMs);
  }

  /**
   * Captures initial page load performance timings using Navigation Timing API.
   */
  public captureInitialPageLoad(): PageNavigationMetric | null {
    if (typeof window === "undefined" || typeof performance === "undefined") {
      return null;
    }

    try {
      const entries = performance.getEntriesByType("navigation");
      if (entries.length > 0) {
        const nav = entries[0] as PerformanceNavigationTiming;
        const durationMs =
          nav.duration ||
          (nav.loadEventEnd ? nav.loadEventEnd - nav.startTime : 0);
        const ttfbMs = nav.responseStart
          ? nav.responseStart - nav.requestStart
          : undefined;
        const domInteractiveMs = nav.domInteractive
          ? nav.domInteractive - nav.startTime
          : undefined;

        const metric: PageNavigationMetric = {
          path: window.location.pathname,
          durationMs: Math.round(durationMs * 100) / 100,
          ttfbMs:
            ttfbMs !== undefined ? Math.round(ttfbMs * 100) / 100 : undefined,
          domInteractiveMs:
            domInteractiveMs !== undefined
              ? Math.round(domInteractiveMs * 100) / 100
              : undefined,
          timestamp: Date.now(),
        };

        this.recordPageNavigation(metric.path, metric.durationMs, metric);
        return metric;
      }
    } catch {
      // Ignore unsupported browser environments
    }

    return null;
  }

  /**
   * Clears in-memory metrics buffers (useful for testing).
   */
  public clear(): void {
    this.apiRecords = [];
    this.pageNavigations = [];
  }
}

export const metrics = new MetricsCollector();
export default metrics;
