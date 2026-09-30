import apiClient from "./client";

// --- Types ---

export interface Campaign {
  id: number | string;
  name?: string;
  title?: string;
  channel: "sms" | "email" | "push" | "in_app";
  segment?: string;
  target_segment?: string;
  subject?: string;
  body?: string;
  message_template?: string;
  status: "draft" | "scheduled" | "processing" | "sending" | "sent" | "failed" | "cancelled";
  scheduled_at?: string;
  sent_at?: string;
  recipient_count?: number;
  total_recipients?: number;
  open_count?: number;
  click_count?: number;
  created_at: string;
}

export interface CampaignInput {
  name?: string;
  title?: string;
  channel: Campaign["channel"];
  segment?: string;
  target_segment?: string;
  subject?: string;
  body?: string;
  message_template?: string;
  scheduled_at?: string;
}

export interface SegmentEstimate {
  segment?: string;
  target_segment?: string;
  estimated_count: number;
}

// --- API (admin) ---

export const messagingApi = {
  /** لیست کمپین‌ها */
  listCampaigns: async (params?: {
    page?: number;
    status?: string;
  }): Promise<{ items: Campaign[]; total: number }> => {
    const res = await apiClient.get<{ items: Campaign[]; total: number }>("/messaging/campaigns", { params });
    const raw = res.data;
    const items = raw?.items || [];
    return {
      items: items.map((c) => ({
        ...c,
        name: c.name || c.title || "",
        segment: c.segment || c.target_segment || "",
        body: c.body || c.message_template || "",
        recipient_count: c.recipient_count ?? c.total_recipients,
      })),
      total: raw?.total ?? items.length,
    };
  },

  /** ایجاد کمپین جدید */
  createCampaign: async (data: CampaignInput): Promise<Campaign> => {
    const payload = {
      title: data.title || data.name || "",
      channel: data.channel,
      target_segment: data.target_segment || data.segment || "all_users",
      message_template: data.message_template || data.body || "",
      scheduled_at: data.scheduled_at,
    };
    const res = await apiClient.post<Campaign>("/messaging/campaigns", payload);
    const c = res.data;
    if (c) {
      if (!c.name) c.name = c.title;
      if (!c.segment) c.segment = c.target_segment;
      if (!c.body) c.body = c.message_template;
    }
    return c;
  },

  /** دریافت جزئیات کمپین */
  getCampaign: async (id: number | string): Promise<Campaign> => {
    const res = await apiClient.get<Campaign>(`/messaging/campaigns/${id}`);
    const c = res.data;
    if (c) {
      if (!c.name) c.name = c.title;
      if (!c.segment) c.segment = c.target_segment;
      if (!c.body) c.body = c.message_template;
    }
    return c;
  },

  /** ویرایش کمپین */
  updateCampaign: async (id: number | string, data: Partial<CampaignInput>): Promise<Campaign> => {
    const payload: Record<string, unknown> = {};
    if (data.title || data.name) payload.title = data.title || data.name;
    if (data.channel) payload.channel = data.channel;
    if (data.target_segment || data.segment) payload.target_segment = data.target_segment || data.segment;
    if (data.message_template || data.body) payload.message_template = data.message_template || data.body;
    if (data.scheduled_at !== undefined) payload.scheduled_at = data.scheduled_at;
    const res = await apiClient.patch<Campaign>(`/messaging/campaigns/${id}`, payload);
    return res.data;
  },

  /** ارسال کمپین */
  sendCampaign: async (id: number | string): Promise<Campaign> => {
    const res = await apiClient.post<Campaign>(`/messaging/campaigns/${id}/send`);
    return res.data;
  },

  /** تخمین تعداد مخاطبین یک سگمنت */
  estimateSegment: async (segment: string): Promise<SegmentEstimate> => {
    const res = await apiClient.get<{ estimated_count: number; target_segment?: string }>(`/messaging/estimate/${segment}`);
    return {
      segment,
      target_segment: res.data.target_segment || segment,
      estimated_count: res.data.estimated_count,
    };
  },
};
