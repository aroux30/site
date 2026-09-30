import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export type ComparisonMode = "previous_period" | "same_period_last_year";

export interface MetricDelta {
  key: string;
  current: number;
  previous: number;
  change_abs: number;
  /** null when the prior value was zero — a percentage against it is undefined. */
  change_pct: number | null;
  direction: "up" | "down" | "flat";
  /** true when the true change exceeded the meaningful cap. */
  pct_capped: boolean;
}

export interface ComparedRow {
  [key: string]: unknown;
  // Metric cells are MetricDelta objects under their metric name.
}

export interface ComparisonResult {
  report_type: string;
  mode: ComparisonMode;
  current_window: { from: string; to: string };
  previous_window: { from: string; to: string };
  totals: MetricDelta[];
  rows?: ComparedRow[];
  row_key?: string;
  metrics?: string[];
}

// ── API (admin) ─────────────────────────────────────────────────────────────

export const biApi = {
  /** مقایسه یک گزارش با دوره قبل */
  compare: async (params: {
    report_type: string;
    from: string;
    to: string;
    mode?: ComparisonMode;
    group_by?: string;
    warehouse_id?: string;
    vendor_id?: string;
    category_id?: string;
    row_key?: string;
  }): Promise<ComparisonResult> => {
    const res = await apiClient.get<ComparisonResult>("/bi/admin/compare", {
      params,
    });
    return res.data;
  },

  /** گزارش‌های قابل مقایسه و حالت‌ها */
  comparableReports: async (): Promise<{
    reports: string[];
    modes: ComparisonMode[];
  }> => {
    const res = await apiClient.get<{ reports: string[]; modes: ComparisonMode[] }>(
      "/bi/admin/comparable-reports",
    );
    return res.data;
  },
};
