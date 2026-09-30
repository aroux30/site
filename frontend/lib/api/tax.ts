import type { AxiosResponse } from "axios";
import apiClient from "./client";

export { saveBlob } from "./data-exchange";

// ── Tax engine v1 (admin) API ───────────────────────────────────────────────

export type TaxRuleTypeValue = "vat" | "exempt" | "compound" | "withholding";
export type TaxRuleScopeValue = "default" | "category" | "product";

export interface TaxRule {
  id: string;
  name: string;
  code: string;
  rule_type: TaxRuleTypeValue;
  scope: TaxRuleScopeValue;
  category_id: string | null;
  product_id: string | null;
  rate_basis_points: number;
  is_active: boolean;
  priority: number;
  effective_from: string | null;
  effective_to: string | null;
  exempt_reason: string | null;
  description: string | null;
  created_at: string;
}

export interface TaxRuleList {
  items: TaxRule[];
  total: number;
}

export interface TaxRuleCreatePayload {
  name: string;
  code: string;
  rule_type: TaxRuleTypeValue;
  scope: TaxRuleScopeValue;
  category_id?: string | null;
  product_id?: string | null;
  rate_basis_points: number;
  is_active?: boolean;
  priority?: number;
  effective_from?: string | null;
  effective_to?: string | null;
  exempt_reason?: string | null;
  description?: string | null;
}

export interface TaxHealth {
  ok: boolean;
  has_active_default_rule: boolean;
  active_rules_count: number;
  default_rule_code: string | null;
  warnings: string[];
}

export interface TaxReportBucket {
  bucket: string;
  order_count: number;
  taxable_total_rial: number;
  vat_total_rial: number;
  withholding_total_rial: number;
  tax_total_rial: number;
}

export interface TaxReport {
  date_from: string;
  date_to: string;
  group_by: string;
  buckets: TaxReportBucket[];
  vat_total_rial: number;
  withholding_total_rial: number;
  tax_total_rial: number;
  order_count: number;
}

export const taxApi = {
  listRules: (params?: {
    rule_type?: TaxRuleTypeValue;
    scope?: TaxRuleScopeValue;
    is_active?: boolean;
    category_id?: string;
  }) => apiClient.get<TaxRuleList>("/admin/tax/rules", { params }).then((r) => r.data),

  getRule: (id: string) =>
    apiClient.get<TaxRule>(`/admin/tax/rules/${id}`).then((r) => r.data),

  createRule: (payload: TaxRuleCreatePayload) =>
    apiClient.post<TaxRule>("/admin/tax/rules", payload).then((r) => r.data),

  updateRule: (id: string, payload: Partial<TaxRuleCreatePayload>) =>
    apiClient.patch<TaxRule>(`/admin/tax/rules/${id}`, payload).then((r) => r.data),

  deactivateRule: (id: string) =>
    apiClient.delete(`/admin/tax/rules/${id}`).then((r) => r.data as unknown),

  health: () =>
    apiClient.get<TaxHealth>("/admin/tax/health").then((r) => r.data),

  report: (params: { from: string; to: string; group_by: "period" | "rule" | "category" }) =>
    apiClient.get<TaxReport>("/admin/tax/report", { params }).then((r) => r.data),

  reportCsv: async (params: {
    from: string;
    to: string;
    group_by: "period" | "rule" | "category";
  }): Promise<Blob> => {
    const response: AxiosResponse<Blob> = await apiClient.get(
      "/admin/tax/report.csv",
      { params, responseType: "blob" },
    );
    return response.data as Blob;
  },
};