import apiClient from "./client";

// --- Types ---

// --- API (admin) ---

export const adminApi = {
  // --- Payments (admin aliases) ---

  approvePayment: async (paymentId: number): Promise<void> => {
    await apiClient.post(`/admin/payments/${paymentId}/approve`);
  },

  rejectPayment: async (paymentId: number, reason?: string): Promise<void> => {
    await apiClient.post(`/admin/payments/${paymentId}/reject`, { reason });
  },

  // --- Blog (admin aliases) ---

  createBlogPost: async (data: Record<string, unknown>): Promise<Record<string, unknown>> => {
    const res = await apiClient.post<Record<string, unknown>>("/admin/blog/posts", data);
    return res.data;
  },

  updateBlogPost: async (postId: number, data: Record<string, unknown>): Promise<Record<string, unknown>> => {
    const res = await apiClient.patch<Record<string, unknown>>(`/admin/blog/posts/${postId}`, data);
    return res.data;
  },

  deleteBlogPost: async (postId: number): Promise<void> => {
    await apiClient.delete(`/admin/blog/posts/${postId}`);
  },

  createBlogCategory: async (data: { name: string; slug?: string }): Promise<Record<string, unknown>> => {
    const res = await apiClient.post<Record<string, unknown>>("/admin/blog/categories", data);
    return res.data;
  },

  // --- SEO (admin aliases) ---

  upsertSeoMetadata: async (
    resourceType: string,
    resourceId: string,
    data: Record<string, unknown>,
  ): Promise<Record<string, unknown>> => {
    const res = await apiClient.put<Record<string, unknown>>(
      `/admin/seo/${resourceType}/${resourceId}`,
      data,
    );
    return res.data;
  },

  deleteSeoMetadata: async (resourceType: string, resourceId: string): Promise<void> => {
    await apiClient.delete(`/admin/seo/${resourceType}/${resourceId}`);
  },

  // --- Search ---

  reindexProducts: async (): Promise<{ task_id: string; message: string }> => {
    const res = await apiClient.post<{ task_id: string; message: string }>("/admin/search/reindex");
    return res.data;
  },
};
