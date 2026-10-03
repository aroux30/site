/**
 * Settings-module API clients that had no frontend caller.
 *
 * The backend has carried these endpoints since the WordPress parity pass and
 * nothing in the app called them, which left complete, working features with
 * no way to reach them — a route, a schema and a service that could only be
 * exercised by curl.
 */

import { apiClient } from "./client";

// ── UI string catalogue ────────────────────────────────────────────────────

export interface I18nString {
  id: string;
  key: string;
  locale: string;
  value: string;
  group: string | null;
  is_active: boolean;
}

export interface I18nCatalog {
  locale: string;
  strings: Record<string, string>;
}

export const settingsI18nApi = {
  /** Every (key, locale) row, for the admin grid. */
  list: async (): Promise<I18nString[]> => {
    const { data } = await apiClient.get<{ items: I18nString[]; total?: number }>(
      "/settings/admin/i18n/strings",
    );
    return data.items || [];
  },

  /** Create or update one (key, locale) pair. */
  upsert: async (body: {
    key: string;
    locale: string;
    value: string;
    group?: string | null;
  }): Promise<I18nString> => {
    const { data } = await apiClient.post<I18nString>(
      "/settings/admin/i18n/strings",
      body,
    );
    return data;
  },

  /** Many at once, for a translated file pasted in one go. */
  bulkUpsert: async (
    items: Array<{ key: string; locale: string; value: string; group?: string | null }>,
  ): Promise<{ created: number; updated: number; total: number }> => {
    const { data } = await apiClient.put<{
      created: number;
      updated: number;
      total: number;
    }>("/settings/admin/i18n/strings/bulk", { items });
    return data;
  },

  /** The catalogue for one locale, as a key → value map. */
  catalog: async (locale: string): Promise<I18nCatalog> => {
    const { data } = await apiClient.get<I18nCatalog>("/settings/public/i18n", {
      params: { locale },
    });
    return data;
  },
};

// ── Privacy policy ─────────────────────────────────────────────────────────

/**
 * The privacy policy a consent form links to.
 *
 * Every field is nullable because "this store has not published a policy" is an
 * answer the caller has to act on, not an error: the form then shows no link
 * rather than one that 404s on submit. WordPress makes the same distinction —
 * `get_privacy_policy_url()` returns an empty string unless the configured page
 * exists and is published.
 */
export interface PrivacyPolicy {
  title: string | null;
  slug: string | null;
  url: string | null;
}

export const privacyPolicyApi = {
  /** The published policy, or all-null when there is none. */
  get: async (): Promise<PrivacyPolicy> => {
    const { data } = await apiClient.get<PrivacyPolicy>(
      "/settings/public/privacy-policy",
    );
    return data ?? { title: null, slug: null, url: null };
  },
};

// ── Admin email (WordPress new_admin_email flow) ────────────────────────────

/**
 * The site admin address, its pending proposal, and the periodic review state.
 *
 * The address is where password resets and store notices arrive, so changing
 * it is two-step: a proposal is recorded, a confirmation link goes to the new
 * address, and `admin_email` moves only when that link is redeemed. A typo
 * therefore cannot redirect the store's recovery mail.
 */
export interface AdminEmailStatus {
  admin_email: string | null;
  pending_email: string | null;
  pending_requested_at: string | null;
  confirmed_at: string | null;
  review_interval_days: number;
  /** True when the address has not been confirmed within the review window. */
  needs_review: boolean;
  due_since: string | null;
}

export const adminEmailApi = {
  status: async (): Promise<AdminEmailStatus> => {
    const { data } = await apiClient.get<AdminEmailStatus>(
      "/settings/admin/admin-email",
    );
    return data;
  },

  /** Propose a new address; the confirmation link goes to the new one. */
  requestChange: async (
    newEmail: string,
  ): Promise<{ status: string; message: string; email_sent?: boolean }> => {
    const { data } = await apiClient.post<{
      status: string;
      message: string;
      email_sent?: boolean;
    }>("/settings/admin/admin-email/change", { new_email: newEmail });
    return data;
  },

  /** Redeem the token from the confirmation email (admin session required). */
  confirm: async (
    token: string,
  ): Promise<{ status: string; message?: string; email?: string }> => {
    const { data } = await apiClient.post<{
      status: string;
      message?: string;
      email?: string;
    }>("/settings/admin/admin-email/confirm", { token });
    return data;
  },

  /** The periodic review's "yes, still correct". */
  confirmCurrent: async (): Promise<{ status: string; email?: string }> => {
    const { data } = await apiClient.post<{ status: string; email?: string }>(
      "/settings/admin/admin-email/confirm-current",
    );
    return data;
  },
};
