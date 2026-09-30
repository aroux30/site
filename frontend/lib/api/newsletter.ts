/**
 * Newsletter API client — public double opt-in + admin subscriber lookup.
 */

import apiClient from "@/lib/api/client";

export type NewsletterStatus = "pending" | "subscribed" | "unsubscribed";

export interface NewsletterSubscriber {
  email: string;
  status: NewsletterStatus;
  source: string;
  confirmed_at: string | null;
  unsubscribed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriberListResponse {
  items: NewsletterSubscriber[];
  total: number;
  page: number;
  page_size: number;
  status_counts: Record<NewsletterStatus, number>;
}

export const newsletterApi = {
  /** Public signup — response is intentionally generic (no enumeration). */
  subscribe: async (email: string, source?: string): Promise<{ message: string }> => {
    const { data } = await apiClient.post("/newsletter/subscribe", {
      email,
      source: source ?? "footer",
    });
    return data;
  },

  confirm: async (token: string, email: string): Promise<{ status: NewsletterStatus }> => {
    const { data } = await apiClient.post("/newsletter/confirm", { token, email });
    return data;
  },

  unsubscribe: async (token: string, email: string): Promise<{ status: NewsletterStatus }> => {
    const { data } = await apiClient.post("/newsletter/unsubscribe", { token, email });
    return data;
  },

  /** Admin — fetch one subscriber by address. */
  adminGet: async (email: string): Promise<NewsletterSubscriber> => {
    const { data } = await apiClient.get(
      `/admin/newsletter/subscribers/${encodeURIComponent(email.trim().toLowerCase())}`,
    );
    return data;
  },

  /** Admin — paginated subscriber list with per-status totals. */
  adminList: async (
    page = 1,
    pageSize = 20,
  ): Promise<SubscriberListResponse> => {
    const { data } = await apiClient.get<SubscriberListResponse>(
      "/admin/newsletter/subscribers",
      { params: { page, page_size: pageSize } },
    );
    return data;
  },

  /** Admin — download the whole list as CSV (browser navigates to this URL
   *  so the server's Content-Disposition filename is honoured and the file
   *  streams instead of passing through an axios blob). */
  exportCsvUrl: (): string => "/api/v1/admin/newsletter/export.csv",

  adminDelete: async (email: string): Promise<void> => {
    await apiClient.delete(
      `/admin/newsletter/subscribers/${encodeURIComponent(email.trim().toLowerCase())}`,
    );
  },
};
