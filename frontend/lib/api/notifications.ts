import apiClient from "./client";

// --- Types ---

export type NoticeType = "banner" | "popup" | "alert_bar";

export type NoticeTargetPage = "all" | "home" | "checkout" | "dashboard";

export interface Notification {
  /** UUID, not a number — `/notifications/{id}/read` takes a uuid.UUID. */
  id: string;
  type: string;
  title: string;
  body: string;
  data?: Record<string, unknown> | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface Notice {
  id: string;
  title: string;
  content_html: string;
  notice_type: NoticeType;
  target_page: NoticeTargetPage;
  start_at: string;
  end_at: string;
  is_active: boolean;
  created_at: string;
}

export interface NoticeCreatePayload {
  title: string;
  content_html: string;
  notice_type: NoticeType;
  target_page: NoticeTargetPage;
  start_at?: string;
  end_at?: string;
}

export interface SmsDispatchResult {
  success: boolean;
  provider: string | null;
  to: string | null;
  error: string | null;
}

// --- API (user) ---

export const notificationsApi = {
  /** لیست اعلان‌های کاربر */
  list: async (params?: {
    is_read?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<{ items: Notification[]; total: number; unread_count: number }> => {
    const res = await apiClient.get<{ items: Notification[]; total: number; unread_count: number }>(
      "/notifications",
      { params },
    );
    return res.data;
  },

  /** خوانده‌شده کردن یک اعلان */
  markAsRead: async (notificationId: string): Promise<void> => {
    await apiClient.post(`/notifications/${notificationId}/read`);
  },

  /** خوانده‌شده کردن همه */
  markAllRead: async (): Promise<{ marked_count: number }> => {
    const res = await apiClient.post<{ marked_count: number }>("/notifications/read-all");
    return res.data;
  },

  /** اطلاعیه‌های فعال (بنرها) */
  getActiveNotices: async (targetPage = "all"): Promise<Notice[]> => {
    const res = await apiClient.get<Notice[]>("/notifications/notices/active", {
      params: { target_page: targetPage },
    });
    return Array.isArray(res.data) ? res.data : [];
  },

  /** مشاهده‌شده کردن یک اطلاعیه */
  markNoticeSeen: async (noticeId: string): Promise<{ user_id: string; notice_id: string; seen_at: string; message: string }> => {
    const res = await apiClient.post<{ user_id: string; notice_id: string; seen_at: string; message: string }>(
      `/notifications/notices/${noticeId}/seen`,
    );
    return res.data;
  },
};

// --- API (admin) ---

export const notificationsAdminApi = {
  /** ایجاد اطلاعیه زمان‌دار جدید (بنر، پاپ‌آپ یا نوار هشدار) */
  createNotice: async (data: NoticeCreatePayload): Promise<Notice> => {
    const res = await apiClient.post<Notice>("/notifications/notices/admin", data);
    return res.data;
  },

  /** لیست همه اطلاعیه‌ها */
  listAllNotices: async (): Promise<Notice[]> => {
    const res = await apiClient.get<Notice[]>("/notifications/notices/admin/all");
    return Array.isArray(res.data) ? res.data : [];
  },

  /**
   * ارسال پیامک با زنجیره سرویس‌دهنده‌های پشتیبان.
   *
   * `mobile` must be 10–15 characters as the server validates it before
   * normalizing (the hub rewrites 9xxxxxxxxx / 989xxxxxxxxx to 09xxxxxxxxx
   * itself), and the response reports success per provider — a failover that
   * exhausted every provider comes back `success: false` with the reason, not
   * as a delivered message.
   */
  dispatchSms: async (data: {
    mobile: string;
    text: string;
    pattern?: string;
  }): Promise<SmsDispatchResult> => {
    const res = await apiClient.post<SmsDispatchResult>(
      "/notifications/notices/sms/dispatch",
      {
        mobile: data.mobile.trim(),
        text: data.text,
        ...(data.pattern ? { pattern: data.pattern } : {}),
      },
    );
    return res.data;
  },
};
