/**
 * Newsletter campaign API client — the admin mailout half of the newsletter
 * module.
 *
 * Every shape below is transcribed from the backend contracts in
 * `backend/app/modules/newsletter/schemas/newsletter.py` and
 * `.../domain/models.py`. The field names are not inferred: `status` uses the
 * five `CampaignStatus` members, and a recipient's primary key is the
 * subscriber's email address, which the API exposes as `email`.
 *
 * Lifecycle: draft → scheduled → sending → sent | failed. The API never writes
 * `sending` itself — the worker does — so a `sending` row means a send is in
 * flight and the campaign is no longer editable or deletable.
 */

import apiClient from "@/lib/api/client";

export type CampaignStatus = "draft" | "scheduled" | "sending" | "sent" | "failed";

export type RecipientStatus = "pending" | "sent" | "failed";

export interface NewsletterCampaign {
  id: string;
  name: string;
  subject: string;
  preheader?: string | null;
  body_html: string;
  body_text?: string | null;
  status: CampaignStatus;
  scheduled_at?: string | null;
  sent_at?: string | null;
  total_recipients: number;
  total_sent: number;
  total_failed: number;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignListResponse {
  items: NewsletterCampaign[];
  total: number;
  page: number;
  page_size: number;
}

export interface CampaignCreatePayload {
  name: string;
  subject: string;
  body_html: string;
  preheader?: string;
  body_text?: string;
}

export type CampaignUpdatePayload = Partial<CampaignCreatePayload>;

export interface CampaignSendResponse {
  id: string;
  status: CampaignStatus;
  /** `queued` = handed to the Celery worker; `inline` = no broker, sent in-request. */
  mode: "queued" | "inline";
  total_recipients: number;
  total_sent: number;
  total_failed: number;
}

export interface CampaignPreviewResponse {
  subject: string;
  html: string;
  text: string;
}

export interface CampaignRecipient {
  campaign_id: string;
  email: string;
  status: RecipientStatus;
  error?: string | null;
  sent_at?: string | null;
  created_at: string;
}

export interface CampaignRecipientListResponse {
  items: CampaignRecipient[];
  total: number;
  page: number;
  page_size: number;
}

export const newsletterCampaignsApi = {
  /** Paginated campaign list, newest first. */
  list: async (page = 1, pageSize = 20): Promise<CampaignListResponse> => {
    const { data } = await apiClient.get<CampaignListResponse>(
      "/admin/newsletter/campaigns",
      { params: { page, page_size: pageSize } },
    );
    return data;
  },

  /** One campaign by id. */
  get: async (campaignId: string): Promise<NewsletterCampaign> => {
    const { data } = await apiClient.get<NewsletterCampaign>(
      `/admin/newsletter/campaigns/${campaignId}`,
    );
    return data;
  },

  /** Create a draft campaign. */
  create: async (payload: CampaignCreatePayload): Promise<NewsletterCampaign> => {
    const { data } = await apiClient.post<NewsletterCampaign>(
      "/admin/newsletter/campaigns",
      payload,
    );
    return data;
  },

  /** Patch a draft campaign. Ignored fields stay untouched. */
  update: async (
    campaignId: string,
    payload: CampaignUpdatePayload,
  ): Promise<NewsletterCampaign> => {
    const { data } = await apiClient.patch<NewsletterCampaign>(
      `/admin/newsletter/campaigns/${campaignId}`,
      payload,
    );
    return data;
  },

  /** Delete a draft or failed campaign (the server refuses sending/sent ones). */
  remove: async (campaignId: string): Promise<void> => {
    await apiClient.delete(`/admin/newsletter/campaigns/${campaignId}`);
  },

  /** Fully rendered email — unsubscribe footer included — for admin review. */
  preview: async (campaignId: string): Promise<CampaignPreviewResponse> => {
    const { data } = await apiClient.get<CampaignPreviewResponse>(
      `/admin/newsletter/campaigns/${campaignId}/preview`,
    );
    return data;
  },

  /** Send now. Returns the recipient snapshot and how the send was dispatched. */
  send: async (campaignId: string): Promise<CampaignSendResponse> => {
    const { data } = await apiClient.post<CampaignSendResponse>(
      `/admin/newsletter/campaigns/${campaignId}/send`,
    );
    return data;
  },

  /** Schedule (or re-time) a campaign; the beat sweep fires within ~1 min. */
  schedule: async (
    campaignId: string,
    scheduledAt: string,
  ): Promise<NewsletterCampaign> => {
    const { data } = await apiClient.post<NewsletterCampaign>(
      `/admin/newsletter/campaigns/${campaignId}/schedule`,
      { scheduled_at: scheduledAt },
    );
    return data;
  },

  /** Send the rendered campaign to one address without creating recipient rows. */
  testSend: async (
    campaignId: string,
    email: string,
  ): Promise<{ email: string; sent: boolean }> => {
    const { data } = await apiClient.post<{ email: string; sent: boolean }>(
      `/admin/newsletter/campaigns/${campaignId}/test`,
      { email },
    );
    return data;
  },

  /** Per-recipient delivery status for one campaign. */
  recipients: async (
    campaignId: string,
    page = 1,
    pageSize = 50,
  ): Promise<CampaignRecipientListResponse> => {
    const { data } = await apiClient.get<CampaignRecipientListResponse>(
      `/admin/newsletter/campaigns/${campaignId}/recipients`,
      { params: { page, page_size: pageSize } },
    );
    return data;
  },
};
