import { apiClient } from "./client";
import type { DesignTokensDocument } from "@/lib/builder/theme-schema";

export interface SiteTheme {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  is_active: boolean;
  tokens: DesignTokensDocument;
  css_variables?: Record<string, string>;
  author_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ThemeRevision {
  id: string;
  theme_id: string;
  version: number;
  name: string;
  change_summary?: string | null;
  tokens: DesignTokensDocument;
  created_by?: string | null;
  created_at: string;
}

export const themesAdminApi = {
  list: async (): Promise<SiteTheme[]> => {
    const res = await apiClient.get<SiteTheme[]>("/content/admin/themes");
    return Array.isArray(res.data) ? res.data : [];
  },

  getActive: async (): Promise<SiteTheme> => {
    const res = await apiClient.get<SiteTheme>("/content/themes/active");
    return res.data;
  },

  create: async (data: {
    name: string;
    slug: string;
    description?: string;
    is_active?: boolean;
    tokens: DesignTokensDocument;
  }): Promise<SiteTheme> => {
    const res = await apiClient.post<SiteTheme>("/content/admin/themes", data);
    return res.data;
  },

  update: async (
    id: string,
    data: {
      name?: string;
      description?: string;
      is_active?: boolean;
      tokens?: DesignTokensDocument;
    }
  ): Promise<SiteTheme> => {
    const res = await apiClient.patch<SiteTheme>(`/content/admin/themes/${id}`, data);
    return res.data;
  },

  activate: async (id: string): Promise<SiteTheme> => {
    const res = await apiClient.post<SiteTheme>(`/content/admin/themes/${id}/activate`);
    return res.data;
  },

  listRevisions: async (themeId: string): Promise<ThemeRevision[]> => {
    const res = await apiClient.get<ThemeRevision[]>(`/content/admin/themes/${themeId}/revisions`);
    return Array.isArray(res.data) ? res.data : [];
  },

  restoreRevision: async (themeId: string, revisionId: string): Promise<SiteTheme> => {
    const res = await apiClient.post<SiteTheme>(
      `/content/admin/themes/${themeId}/revisions/${revisionId}/restore`
    );
    return res.data;
  },

  clone: async (themeId: string, data: { name: string; slug: string }): Promise<SiteTheme> => {
    const res = await apiClient.post<SiteTheme>(`/content/admin/themes/${themeId}/clone`, data);
    return res.data;
  },

  delete: async (themeId: string): Promise<void> => {
    await apiClient.delete(`/content/admin/themes/${themeId}`);
  },
};
