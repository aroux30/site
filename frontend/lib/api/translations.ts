/**
 * Translation management API client (i18n admin).
 *
 * Blog posts link through typed post relationships ("translation");
 * CMS pages share a translation_group via the content admin endpoints.
 */

import apiClient from "@/lib/api/client";

export interface AdminListItem {
  id: string;
  title: string;
  slug: string;
  locale?: string;
  translation_group?: string | null;
  status?: string;
}

interface BlogRelationship {
  id: string;
  source_post_id: string;
  target_post_id: string;
  relationship_type: string;
}

export const translationsApi = {
  // ── Blog posts ────────────────────────────────────────────────────────
  listPosts: async (search = ""): Promise<AdminListItem[]> => {
    const { data } = await apiClient.get("/admin/blog/posts", {
      params: { page: 1, page_size: 200, ...(search ? { search } : {}) },
    });
    return (data.items ?? []) as AdminListItem[];
  },

  listPostRelationships: async (postId: string): Promise<BlogRelationship[]> => {
    const { data } = await apiClient.get<BlogRelationship[]>(
      `/admin/blog/posts/${postId}/relationships`,
    );
    return data;
  },

  linkPosts: async (postId: string, targetPostId: string): Promise<void> => {
    await apiClient.post(`/admin/blog/posts/${postId}/relationships`, {
      target_post_id: targetPostId,
      relationship_type: "translation",
    });
  },

  unlinkPostRelationship: async (postId: string, relationshipId: string): Promise<void> => {
    await apiClient.delete(`/admin/blog/posts/${postId}/relationships/${relationshipId}`);
  },

  /** Snapshot the source post as a new draft, relabel its locale, and link
   *  the pair as translations — the "Create translation" action. */
  duplicateAsTranslation: async (
    postId: string,
    targetLocale: string,
  ): Promise<{ newPostId: string }> => {
    const { data } = await apiClient.post(`/admin/blog/posts/${postId}/duplicate`);
    const newPost = data as { id: string };
    await apiClient.patch(`/admin/blog/posts/${newPost.id}`, { locale: targetLocale });
    await translationsApi.linkPosts(postId, newPost.id);
    return { newPostId: newPost.id };
  },

  // ── CMS pages ─────────────────────────────────────────────────────────
  listPages: async (): Promise<AdminListItem[]> => {
    const { data } = await apiClient.get("/content/admin/pages", {
      params: { page: 1, page_size: 200 },
    });
    return (data.items ?? []) as AdminListItem[];
  },

  linkPages: async (pageId: string, targetPageId: string): Promise<void> => {
    await apiClient.post(`/content/admin/pages/${pageId}/translations`, {
      target_page_id: targetPageId,
    });
  },

  unlinkPages: async (pageId: string, targetPageId: string): Promise<void> => {
    await apiClient.delete(
      `/content/admin/pages/${pageId}/translations/${targetPageId}`,
    );
  },
};
