import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export type SubscriptionStatus =
  | "active"
  | "paused"
  | "past_due"
  | "cancelled"
  | "expired";

export type SubscriptionInterval =
  | "weekly"
  | "monthly"
  | "quarterly"
  | "yearly"
  | "custom_days";

export interface SubscriptionItem {
  id: string;
  variant_id: string;
  product_name: string;
  sku: string;
  quantity: number;
  /** Raw DB column — Rial. Divide by 10 to show. */
  unit_price_rial: number;
}

export interface SubscriptionBilling {
  id: string;
  period_index: number;
  status: "pending" | "paid" | "failed" | "skipped";
  amount_rial: number;
  order_id: string | null;
  payment_id: string | null;
  attempt_count: number;
  last_error: string | null;
  billed_at: string | null;
  renewal_notified: boolean;
  created_at: string;
}

export interface Subscription {
  id: string;
  name: string;
  status: SubscriptionStatus;
  interval: SubscriptionInterval;
  interval_count: number;
  custom_interval_days: number | null;
  saved_method_id: string | null;
  total_per_cycle: number;
  started_at: string;
  next_billing_at: string | null;
  last_billed_at: string | null;
  cancelled_at: string | null;
  cancelled_reason: string | null;
  failure_count: number;
  notes: string | null;
  items: SubscriptionItem[];
  created_at: string;
}

export interface SubscriptionDetail extends Subscription {
  billings: SubscriptionBilling[];
}

export interface CreateSubscriptionPayload {
  name: string;
  interval: SubscriptionInterval;
  interval_count?: number;
  custom_interval_days?: number;
  items: Array<{ variant_id: string; quantity: number; product_name?: string }>;
  saved_method_id?: string | null;
  shipping_address_snapshot?: Record<string, unknown> | null;
  notes?: string;
}

// ── Customer API ────────────────────────────────────────────────────────────

export const subscriptionsApi = {
  /** فهرست اشتراک‌های کاربر */
  list: async (): Promise<Subscription[]> => {
    const res = await apiClient.get<Subscription[]>("/subscriptions");
    return res.data;
  },

  /** یک اشتراک با تاریخچه دوره‌ها */
  get: async (id: string): Promise<SubscriptionDetail> => {
    const res = await apiClient.get<SubscriptionDetail>(`/subscriptions/${id}`);
    return res.data;
  },

  /** ایجاد اشتراک جدید */
  create: async (payload: CreateSubscriptionPayload): Promise<SubscriptionDetail> => {
    const res = await apiClient.post<SubscriptionDetail>("/subscriptions", payload);
    return res.data;
  },

  /** توقف موقت اشتراک */
  pause: async (id: string): Promise<Subscription> => {
    const res = await apiClient.post<Subscription>(`/subscriptions/${id}/pause`, {});
    return res.data;
  },

  /** فعال‌سازی مجدد اشتراک متوقف‌شده */
  resume: async (id: string): Promise<Subscription> => {
    const res = await apiClient.post<Subscription>(`/subscriptions/${id}/resume`, {});
    return res.data;
  },

  /** لغو اشتراک */
  cancel: async (id: string, reason?: string): Promise<Subscription> => {
    const res = await apiClient.post<Subscription>(`/subscriptions/${id}/cancel`, {
      reason,
    });
    return res.data;
  },
};

// ── Admin API ───────────────────────────────────────────────────────────────

export const adminSubscriptionsApi = {
  /** فهرست اشتراک‌ها (ادمین) */
  list: async (params?: { status?: string; user_id?: string; limit?: number }): Promise<Subscription[]> => {
    const res = await apiClient.get<Subscription[]>("/admin/subscriptions", { params });
    return res.data;
  },

  /** جزئیات اشتراک (ادمین) */
  get: async (id: string): Promise<SubscriptionDetail> => {
    const res = await apiClient.get<SubscriptionDetail>(`/admin/subscriptions/${id}`);
    return res.data;
  },

  /** صورتحساب فوری یک دوره (ادمین) */
  billNow: async (id: string): Promise<SubscriptionBilling> => {
    const res = await apiClient.post<SubscriptionBilling>(
      `/admin/subscriptions/${id}/bill-now`,
      {},
    );
    return res.data;
  },

  /** اجرای سراسری صورتحساب‌های سررسیدشده (ادمین) */
  runDue: async (): Promise<{
    due: number;
    paid: number;
    failed: number;
    skipped: number;
    errors: number;
  }> => {
    const res = await apiClient.post<{
      due: number;
      paid: number;
      failed: number;
      skipped: number;
      errors: number;
    }>("/admin/subscriptions/run-due", {});
    return res.data;
  },
};
