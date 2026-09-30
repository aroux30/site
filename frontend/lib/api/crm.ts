import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export type InquiryStage =
  | "new"
  | "contacted"
  | "qualified"
  | "negotiating"
  | "converted"
  | "lost";

export type InquirySource =
  | "web_form"
  | "phone"
  | "email"
  | "referral"
  | "social"
  | "other";

export interface LeadInquiry {
  id: string;
  contact_name: string;
  company_name: string | null;
  phone: string;
  email: string | null;
  stage: InquiryStage;
  source: InquirySource;
  message: string | null;
  estimated_monthly_value_rial: number | null;
  estimated_monthly_volume: number | null;
  owner_id: string | null;
  converted_user_id: string | null;
  converted_at: string | null;
  lost_reason: string | null;
  notes: Array<{ at: string; actor_id: string | null; text: string; event: string }> | null;
  next_follow_up_at: string | null;
  created_at: string;
}

export interface PipelineSummary {
  total: number;
  open: number;
  by_stage: Record<string, number>;
  value_by_stage_rial: Record<string, number>;
  open_pipeline_value_rial: number;
}

export interface ConvertResult {
  inquiry: LeadInquiry;
  api_key_id: string;
  key_prefix: string;
  /** نمایش یک‌باره */
  api_key: string;
}

// ── API ─────────────────────────────────────────────────────────────────────

export const crmApi = {
  /** ثبت درخواست عمده‌فروشی (عمومی — بدون احراز هویت) */
  capture: async (payload: {
    contact_name: string;
    phone: string;
    company_name?: string | null;
    email?: string | null;
    message?: string | null;
    estimated_monthly_volume?: number | null;
  }): Promise<LeadInquiry> => {
    const res = await apiClient.post<LeadInquiry>("/crm/inquiries", payload);
    return res.data;
  },

  /** فهرست درخواست‌ها */
  list: async (params?: {
    stage?: InquiryStage;
    owner_id?: string;
    include_closed?: boolean;
    limit?: number;
  }): Promise<LeadInquiry[]> => {
    const res = await apiClient.get<LeadInquiry[]>("/crm/admin/inquiries", { params });
    return res.data;
  },

  /** خلاصه قیف (تعداد و ارزش هر مرحله) */
  pipeline: async (): Promise<PipelineSummary> => {
    const res = await apiClient.get<PipelineSummary>("/crm/admin/pipeline");
    return res.data;
  },

  /** تغییر مرحله */
  moveStage: async (
    inquiryId: string,
    payload: { stage: InquiryStage; lost_reason?: string; note?: string },
  ): Promise<LeadInquiry> => {
    const res = await apiClient.patch<LeadInquiry>(
      `/crm/admin/inquiries/${inquiryId}/stage`,
      payload,
    );
    return res.data;
  },

  /** تخصیص کارشناس */
  assignOwner: async (inquiryId: string, ownerId: string | null): Promise<LeadInquiry> => {
    const res = await apiClient.patch<LeadInquiry>(
      `/crm/admin/inquiries/${inquiryId}/owner`,
      { owner_id: ownerId },
    );
    return res.data;
  },

  /** افزودن یادداشت */
  addNote: async (inquiryId: string, text: string): Promise<LeadInquiry> => {
    const res = await apiClient.post<LeadInquiry>(
      `/crm/admin/inquiries/${inquiryId}/notes`,
      { text },
    );
    return res.data;
  },

  /** تبدیل به همکار B2B — کلید فقط یک‌بار برمی‌گردد */
  convert: async (
    inquiryId: string,
    payload: { user_id: string; api_key_name?: string | null },
  ): Promise<ConvertResult> => {
    const res = await apiClient.post<ConvertResult>(
      `/crm/admin/inquiries/${inquiryId}/convert`,
      payload,
    );
    return res.data;
  },
};
