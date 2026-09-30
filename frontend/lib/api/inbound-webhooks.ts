import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export type InboundDeliveryStatus =
  | "received"
  | "verified"
  | "rejected_signature"
  | "rejected_duplicate"
  | "processed"
  | "failed";

export interface InboundEndpoint {
  id: string;
  name: string;
  description: string | null;
  ip_whitelist: string[] | null;
  is_active: boolean;
  last_received_at: string | null;
  total_received: number;
  created_at: string;
}

export interface InboundSecret {
  endpoint: InboundEndpoint;
  /** نمایش یک‌باره — پس از بستن دیالوگ دیگر قابل بازیابی نیست */
  secret: string;
}

export interface InboundDelivery {
  id: string;
  endpoint_id: string;
  event_type: string | null;
  status: InboundDeliveryStatus;
  payload: Record<string, unknown> | null;
  idempotency_key: string | null;
  source_ip: string | null;
  user_agent: string | null;
  error: string | null;
  received_at: string;
  processed_at: string | null;
}

// ── API (admin) ─────────────────────────────────────────────────────────────

export const inboundWebhooksApi = {
  /** فهرست گیرنده‌های ورودی */
  listEndpoints: async (): Promise<InboundEndpoint[]> => {
    const res = await apiClient.get<InboundEndpoint[]>("/admin/inbound-webhooks");
    return res.data;
  },

  /** ایجاد گیرنده — راز فقط همین یک‌بار برمی‌گردد */
  createEndpoint: async (payload: {
    name: string;
    description?: string | null;
    ip_whitelist?: string[] | null;
  }): Promise<InboundSecret> => {
    const res = await apiClient.post<InboundSecret>(
      "/admin/inbound-webhooks",
      payload,
    );
    return res.data;
  },

  /** چرخش راز — راز قبلی بلافاصله بی‌اعتبار می‌شود */
  rotateSecret: async (endpointId: string): Promise<InboundSecret> => {
    const res = await apiClient.post<InboundSecret>(
      `/admin/inbound-webhooks/${endpointId}/rotate-secret`,
      {},
    );
    return res.data;
  },

  /** لاگ تحویل‌ها — شامل ردشده‌ها (ردیف‌هایی که اثر امنیتی دارند) */
  listDeliveries: async (params?: {
    endpoint_name?: string;
    status?: InboundDeliveryStatus;
    limit?: number;
  }): Promise<InboundDelivery[]> => {
    const res = await apiClient.get<InboundDelivery[]>(
      "/admin/inbound-webhooks/deliveries",
      { params },
    );
    return res.data;
  },
};
