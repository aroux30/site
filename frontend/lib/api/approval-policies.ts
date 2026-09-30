import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export interface ApprovalPolicyStepDef {
  role: string | null;
  label: string | null;
}

export interface ApprovalStep {
  role?: string | null;
  required_role?: string | null;
  label: string | null;
  step_order?: number;
}

export interface ApprovalPolicy {
  id: string;
  resource: string;
  min_amount_rial: number | null;
  max_amount_rial: number | null;
  steps: ApprovalStep[];
  priority: number;
  is_active: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApprovalPolicyPayload {
  resource: string;
  min_amount_rial: number | null;
  max_amount_rial: number | null;
  steps: ApprovalPolicyStepDef[];
  priority: number;
  is_active: boolean;
  description?: string | null;
}

function normalizePolicy(p: any): ApprovalPolicy {
  return {
    ...p,
    steps: Array.isArray(p.steps)
      ? p.steps.map((s: any, idx: number) => ({
          ...s,
          role: s.role || s.required_role || null,
          required_role: s.required_role || s.role || null,
          label: s.label || null,
          step_order: s.step_order ?? idx + 1,
        }))
      : [],
  };
}

// ── API (admin) ─────────────────────────────────────────────────────────────

export const approvalPoliciesApi = {
  /** فهرست پالیسی‌های تایید */
  list: async (params?: { resource?: string; active_only?: boolean }): Promise<ApprovalPolicy[]> => {
    const res = await apiClient.get<ApprovalPolicy[]>("/approvals/policies", { params });
    const raw = res.data;
    const items = Array.isArray(raw) ? raw : (raw as any)?.items || [];
    return items.map(normalizePolicy);
  },

  /** ایجاد پالیسی */
  create: async (payload: ApprovalPolicyPayload): Promise<ApprovalPolicy> => {
    const res = await apiClient.post<ApprovalPolicy>("/approvals/policies", payload);
    return normalizePolicy(res.data);
  },

  /** ویرایش پالیسی */
  update: async (id: string, payload: ApprovalPolicyPayload): Promise<ApprovalPolicy> => {
    const res = await apiClient.patch<ApprovalPolicy>(`/approvals/policies/${id}`, payload);
    return normalizePolicy(res.data);
  },

  /** غیرفعال‌سازی پالیسی (soft delete) */
  deactivate: async (id: string): Promise<void> => {
    await apiClient.delete(`/approvals/policies/${id}`);
  },
};
