import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export interface CalendarEvent {
  source_module: string;
  event_type: string;
  entity_id: string;
  title: string;
  start_at: string;
  end_at: string | null;
  status: string | null;
  detail: Record<string, unknown>;
}

export interface CalendarResponse {
  events: CalendarEvent[];
  window: { from: string; to: string };
  sources: Record<string, { count: number; ok: boolean; error?: string }>;
  total: number;
}

export interface CalendarSummary {
  total: number;
  active_now: number;
  by_source: Record<string, number>;
  by_day: Record<string, number>;
}

export interface CalendarSource {
  module: string;
  label: string;
}

// ── API (admin) ─────────────────────────────────────────────────────────────

export const calendarApi = {
  /** رویدادهای زمان‌بندی‌شده در بازه */
  list: async (params?: {
    from_date?: string;
    to_date?: string;
    sources?: string[];
  }): Promise<CalendarResponse> => {
    const res = await apiClient.get<CalendarResponse>("/calendar/admin", {
      params,
      paramsSerializer: {
        indexes: null, // sources=a&sources=b
      },
    });
    return res.data;
  },

  /** خلاصه شمارشی */
  summary: async (params?: {
    from_date?: string;
    to_date?: string;
  }): Promise<CalendarSummary> => {
    const res = await apiClient.get<CalendarSummary>("/calendar/admin/summary", {
      params,
    });
    return res.data;
  },

  /** ماژول‌های منبع */
  sources: async (): Promise<{ sources: CalendarSource[] }> => {
    const res = await apiClient.get<{ sources: CalendarSource[] }>(
      "/calendar/admin/sources",
    );
    return res.data;
  },
};
