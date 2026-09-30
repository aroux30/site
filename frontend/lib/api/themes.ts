/**
 * Switchable themes API client (WordPress appearance parity).
 * A theme is a named token set; activation makes it the live storefront look
 * by copying its tokens into the ``theme`` single type.
 */

import apiClient from "@/lib/api/client";

export interface ThemeTokens {
  colors: Record<string, string>;
  radius?: string;
  dark_mode_default?: boolean;
}

export interface SiteTheme {
  id: string;
  slug: string;
  name: string;
  tokens: ThemeTokens;
  is_builtin: boolean;
  is_active: boolean;
}

export const themesApi = {
  list: async (): Promise<SiteTheme[]> => {
    const { data } = await apiClient.get("/settings/admin/themes");
    return data.items;
  },

  create: async (name: string, tokens: ThemeTokens): Promise<SiteTheme> => {
    const { data } = await apiClient.post("/settings/admin/themes", { name, tokens });
    return data;
  },

  activate: async (themeId: string): Promise<{ message: string }> => {
    const { data } = await apiClient.post(`/settings/admin/themes/${themeId}/activate`);
    return data;
  },

  remove: async (themeId: string): Promise<void> => {
    await apiClient.delete(`/settings/admin/themes/${themeId}`);
  },
};
