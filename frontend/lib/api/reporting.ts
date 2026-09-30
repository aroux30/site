import type { AxiosResponse } from "axios";
import apiClient from "./client";

// ── Reporting layer v1 (admin) API ───────────────────────────────────────
// Money: every *_rial field is an integer number of Rials; format in Toman
// at the call site with formatPrice(Math.trunc(rial / 10)).

export type ReportTypeValue = "sales" | "stock" | "vendor_settlement" | "tax_vat";

export type SalesGroupBy = "day" | "week" | "month" | "category" | "vendor" | "channel";
export type StockGroupBy = "warehouse" | "category" | "variant";
export type SettlementGroupBy = "vendor" | "status";
export type TaxGroupBy = "period" | "rule" | "category";

export interface ReportColumn {
  key: string;
  label: string;
  kind: "text" | "int" | "money";
}

export interface ReportPayload {
  report_type: string;
  date_from: string;
  date_to: string;
  group_by: string;
  columns: ReportColumn[];
  rows: Array<Record<string, string | number | null>>;
  totals: Record<string, string | number | null>;
  notes: string[];
}

export interface ReportQuery {
  from: string; // ISO date (Gregorian) — display Jalali, API Gregorian
  to: string;
  group_by?: string;
  warehouse_id?: string;
  vendor_id?: string;
  category_id?: string;
  low_stock_only?: boolean;
}

export type ReportRunStatusValue =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "completed_no_delivery";

export interface SavedReport {
  id: string;
  name: string;
  report_type: ReportTypeValue;
  filters: Record<string, unknown>;
  schedule_cron: string | null;
  delivery_channels: string[];
  recipients: string[];
  owner_id: string;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SavedReportList {
  items: SavedReport[];
  total: number;
  page: number;
  page_size: number;
}

export interface SavedReportCreatePayload {
  name: string;
  report_type: ReportTypeValue;
  filters: Record<string, unknown>;
  schedule_cron?: string | null;
  delivery_channels?: string[];
  recipients?: string[];
  is_active?: boolean;
}

export interface SavedReportUpdatePayload {
  name?: string;
  filters?: Record<string, unknown>;
  schedule_cron?: string | null;
  delivery_channels?: string[];
  recipients?: string[];
  is_active?: boolean;
}

export interface ReportRun {
  id: string;
  saved_report_id: string;
  status: ReportRunStatusValue;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  row_count: number;
  delivery_result: Record<string, unknown> | null;
  has_csv: boolean;
  has_html: boolean;
}

export interface ReportRunList {
  items: ReportRun[];
  total: number;
  page: number;
  page_size: number;
}

function cleanParams(query: ReportQuery): Record<string, string> {
  const params: Record<string, string> = { from: query.from, to: query.to };
  if (query.group_by) params.group_by = query.group_by;
  if (query.warehouse_id) params.warehouse_id = query.warehouse_id;
  if (query.vendor_id) params.vendor_id = query.vendor_id;
  if (query.category_id) params.category_id = query.category_id;
  if (query.low_stock_only) params.low_stock_only = "true";
  return params;
}

export const reportingApi = {
  getReport: (reportType: ReportTypeValue, query: ReportQuery) =>
    apiClient
      .get<ReportPayload>(`/admin/reports/${reportType}`, {
        params: cleanParams(query),
      })
      .then((r) => r.data),

  exportCsv: async (
    reportType: ReportTypeValue,
    query: ReportQuery,
  ): Promise<Blob> => {
    const response: AxiosResponse<Blob> = await apiClient.get(
      `/admin/reports/${reportType}/export.csv`,
      { params: cleanParams(query), responseType: "blob" },
    );
    return response.data as Blob;
  },

  listSavedReports: (params?: { page?: number; page_size?: number }) =>
    apiClient
      .get<SavedReportList>("/admin/saved-reports", { params })
      .then((r) => r.data),

  createSavedReport: (payload: SavedReportCreatePayload) =>
    apiClient.post<SavedReport>("/admin/saved-reports", payload).then((r) => r.data),

  updateSavedReport: (id: string, payload: SavedReportUpdatePayload) =>
    apiClient
      .patch<SavedReport>(`/admin/saved-reports/${id}`, payload)
      .then((r) => r.data),

  deleteSavedReport: (id: string) =>
    apiClient.delete(`/admin/saved-reports/${id}`).then(() => undefined),

  runNow: (id: string) =>
    apiClient
      .post<ReportRun>(`/admin/saved-reports/${id}/run`)
      .then((r) => r.data),

  listRuns: (id: string, params?: { page?: number; page_size?: number }) =>
    apiClient
      .get<ReportRunList>(`/admin/saved-reports/${id}/runs`, { params })
      .then((r) => r.data),

  downloadRun: async (id: string, runId: string): Promise<Blob> => {
    const response: AxiosResponse<Blob> = await apiClient.get(
      `/admin/saved-reports/${id}/runs/${runId}/download`,
      { responseType: "blob" },
    );
    return response.data as Blob;
  },

  downloadRunHtml: async (id: string, runId: string): Promise<Blob> => {
    const response: AxiosResponse<Blob> = await apiClient.get(
      `/admin/saved-reports/${id}/runs/${runId}/download.html`,
      { responseType: "blob" },
    );
    return response.data as Blob;
  },
};
