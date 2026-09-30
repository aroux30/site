import apiClient from "./client";

// --- Types ---

export interface AdminVendor {
  id: number | string;
  slug: string;
  shop_name?: string;
  store_name?: string;
  is_verified: boolean;
  is_active: boolean;
  created_at: string;
  total_products?: number;
  total_sales?: number;
  total_sales_count?: number;
}

export interface VendorEarnings {
  total_earned?: number;
  total_sales?: number;
  net_earnings?: number;
  pending_settlement: number;
  settled?: number;
  settled_amount?: number;
  commission_rate: number;
}

export interface VendorSettlement {
  id: number | string;
  vendor_id: number | string;
  amount: number;
  status: "pending" | "paid" | "failed" | string;
  reference?: string;
  payment_reference?: string;
  created_at: string;
  paid_at?: string;
}

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

  // --- Vendors ---

  listVendors: async (params?: {
    page?: number;
    is_verified?: boolean;
  }): Promise<{ items: AdminVendor[]; total: number }> => {
    const res = await apiClient.get<{ items: AdminVendor[]; total: number }>("/admin/vendors", { params });
    return res.data;
  },

  getVendor: async (id: number | string): Promise<AdminVendor> => {
    const res = await apiClient.get<any>(`/admin/vendors/${id}`);
    const v = res.data;
    return {
      ...v,
      shop_name: v?.shop_name || v?.store_name || "",
      store_name: v?.store_name || v?.shop_name || "",
      total_sales: v?.total_sales ?? v?.total_sales_count ?? 0,
    };
  },

  verifyVendor: async (id: number | string, verified: boolean): Promise<AdminVendor> => {
    const res = await apiClient.patch<any>(`/admin/vendors/${id}/verify`, { is_verified: verified });
    const v = res.data;
    return {
      ...v,
      shop_name: v?.shop_name || v?.store_name || "",
      store_name: v?.store_name || v?.shop_name || "",
      total_sales: v?.total_sales ?? v?.total_sales_count ?? 0,
    };
  },

  updateVendor: async (id: number | string, data: Partial<AdminVendor>): Promise<AdminVendor> => {
    const res = await apiClient.patch<any>(`/admin/vendors/${id}`, data);
    const v = res.data;
    return {
      ...v,
      shop_name: v?.shop_name || v?.store_name || "",
      store_name: v?.store_name || v?.shop_name || "",
      total_sales: v?.total_sales ?? v?.total_sales_count ?? 0,
    };
  },

  getVendorEarnings: async (id: number | string): Promise<VendorEarnings> => {
    const res = await apiClient.get<any>(`/admin/vendors/${id}/earnings`);
    const e = res.data;
    return {
      ...e,
      total_earned: e?.total_earned ?? e?.net_earnings ?? e?.total_sales ?? 0,
      settled: e?.settled ?? e?.settled_amount ?? 0,
    };
  },

  getVendorSettlements: async (id: number | string): Promise<VendorSettlement[]> => {
    const res = await apiClient.get<{ items: VendorSettlement[] }>(`/admin/vendors/${id}/settlements`);
    const raw = res.data;
    const items = Array.isArray(raw) ? raw : (raw as any)?.items || [];
    return items.map((s: any) => ({
      ...s,
      reference: s?.reference || s?.payment_reference || "",
      payment_reference: s?.payment_reference || s?.reference || "",
    }));
  },

  createVendorSettlement: async (id: number | string, data: {
    amount: number;
    reference?: string;
    payment_reference?: string;
  }): Promise<VendorSettlement> => {
    const payload = {
      amount: Math.trunc(data.amount),
      payment_reference: data.payment_reference || data.reference || undefined,
    };
    const res = await apiClient.post<any>(`/admin/vendors/${id}/settlements`, payload);
    const s = res.data;
    return {
      ...s,
      reference: s?.reference || s?.payment_reference || "",
      payment_reference: s?.payment_reference || s?.reference || "",
    };
  },
};
