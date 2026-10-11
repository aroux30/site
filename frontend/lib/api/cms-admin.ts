import apiClient from "./client";

// ── Redirects ───────────────────────────────────────────────────────────────

export interface RedirectRule {
  id: string;
  from_path: string;
  /** Null for 410/451 — those codes have no destination by definition. */
  to_path: string | null;
  status_code: number;
  hit_count: number;
  is_active?: boolean;
  /** Regex mode: from_path is a pattern; $1 in to_path is a back-reference. */
  is_regex?: boolean;
  note?: string | null;
}

export interface RedirectImportResult {
  created: number;
  updated: number;
  total: number;
  errors: Array<{ line: number; error: string }>;
}

export const redirectsApi = {
  list: () => apiClient.get<RedirectRule[]>("/admin/seo/redirects").then((r) => r.data),
  create: (body: {
    from_path: string;
    to_path?: string | null;
    status_code?: number;
    is_regex?: boolean;
    note?: string | null;
  }) => apiClient.post<RedirectRule>("/admin/seo/redirects", body).then((r) => r.data),
  update: (
    id: string,
    body: Partial<{
      from_path: string;
      to_path: string | null;
      status_code: number;
      is_active: boolean;
      is_regex: boolean;
      note: string | null;
    }>,
  ) => apiClient.patch<RedirectRule>(`/admin/seo/redirects/${id}`, body).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/admin/seo/redirects/${id}`),
  exportCsv: () =>
    apiClient
      .get("/admin/seo/redirects/export", { responseType: "blob" })
      .then((r) => r.data as Blob),
  importCsv: (content: string) =>
    apiClient
      .post<RedirectImportResult>("/admin/seo/redirects/import", { content })
      .then((r) => r.data),
};

// ── Reusable blocks (WordPress "synced patterns") ───────────────────────────

export type ReusableBlockStatus = "draft" | "published" | "archived";

export interface ReusableBlock {
  id: string;
  name: string;
  slug: string;
  body_html: string;
  description: string | null;
  status: ReusableBlockStatus;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

/** The token an editor pastes into a page or post body. */
export const reusableBlockToken = (slug: string) => `[block slug="${slug}"]`;

export const reusableBlocksApi = {
  list: (params?: { includeDeleted?: boolean }) =>
    apiClient
      .get<ReusableBlock[]>("/content/admin/reusable-blocks", {
        params: { include_deleted: params?.includeDeleted },
      })
      .then((r) => r.data),
  create: (body: {
    name: string;
    body_html?: string;
    slug?: string;
    description?: string;
    status?: ReusableBlockStatus;
  }) => apiClient.post<ReusableBlock>("/content/admin/reusable-blocks", body).then((r) => r.data),
  update: (id: string, body: Partial<Pick<ReusableBlock, "name" | "body_html" | "description" | "status" | "is_active">>) =>
    apiClient.patch<ReusableBlock>(`/content/admin/reusable-blocks/${id}`, body).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/content/admin/reusable-blocks/${id}`),
  restore: (id: string) =>
    apiClient.post<ReusableBlock>(`/content/admin/reusable-blocks/${id}/restore`).then((r) => r.data),
  hardRemove: (id: string) => apiClient.delete(`/content/admin/reusable-blocks/${id}/permanent`),
};
