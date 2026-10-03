import apiClient from "./client";

// ── Webhooks ────────────────────────────────────────────────────────────────

export interface WebhookEndpoint {
  id: string;
  name: string;
  url: string;
  events: string[];
  is_active: boolean;
}

export interface WebhookDelivery {
  id: string;
  endpoint_id: string;
  event: string;
  status: "pending" | "success" | "failed";
  attempts: number;
  response_status: number | null;
  last_error: string | null;
  payload?: Record<string, unknown> | null;
  created_at?: string | null;
  next_attempt_at?: string | null;
  delivered_at?: string | null;
}

export const webhooksApi = {
  listEvents: () => apiClient.get<string[]>("/integrations/admin/webhooks/events").then((r) => r.data),
  list: () => apiClient.get<WebhookEndpoint[]>("/integrations/admin/webhooks").then((r) => r.data),
  create: (body: { name: string; url: string; events: string[]; secret?: string }) =>
    apiClient.post<WebhookEndpoint>("/integrations/admin/webhooks", body).then((r) => r.data),
  update: (id: string, body: Partial<WebhookEndpoint & { secret: string }>) =>
    apiClient.patch<WebhookEndpoint>(`/integrations/admin/webhooks/${id}`, body).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/integrations/admin/webhooks/${id}`),
  deliveries: (params?: { limit?: number; endpointId?: string; status?: string }) =>
    apiClient
      .get<WebhookDelivery[]>("/integrations/admin/webhooks/deliveries", {
        params: {
          limit: params?.limit ?? 30,
          endpoint_id: params?.endpointId,
          status: params?.status,
        },
      })
      .then((r) => r.data),
  test: (id: string) =>
    apiClient.post<WebhookDelivery>(`/integrations/admin/webhooks/${id}/test`).then((r) => r.data),
  rotateSecret: (id: string) =>
    apiClient
      .post<{ secret: string }>(`/integrations/admin/webhooks/${id}/secret/rotate`)
      .then((r) => r.data),
};

// ── Redirects ───────────────────────────────────────────────────────────────

export interface RedirectRule {
  id: string;
  from_path: string;
  to_path: string;
  status_code: number;
  hit_count: number;
  is_active?: boolean;
}

export const redirectsApi = {
  list: () => apiClient.get<RedirectRule[]>("/admin/seo/redirects").then((r) => r.data),
  create: (body: { from_path: string; to_path: string; status_code?: number }) =>
    apiClient.post<RedirectRule>("/admin/seo/redirects", body).then((r) => r.data),
  update: (
    id: string,
    body: Partial<{ from_path: string; to_path: string; status_code: number; is_active: boolean }>,
  ) => apiClient.patch<RedirectRule>(`/admin/seo/redirects/${id}`, body).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/admin/seo/redirects/${id}`),
};

// ── Dynamic content types ───────────────────────────────────────────────────

export interface ContentTypeField {
  name: string;
  type: string;
  required?: boolean;
  multiple?: boolean;
  options?: string[];
  target?: string;
  fields?: ContentTypeField[];
  default?: unknown;
}

export interface ContentTypeDef {
  id: string;
  slug: string;
  name: string;
  kind: "collection" | "single";
  description: string | null;
  fields: ContentTypeField[];
}

export interface ContentEntryRow {
  id: string;
  data: Record<string, unknown>;
  status?: string;
  locale?: string;
  position?: number;
  revision_number?: number;
}

export const contentTypesApi = {
  list: () => apiClient.get<ContentTypeDef[]>("/content/admin/content-types").then((r) => r.data),
  create: (body: { slug: string; name: string; kind?: string; description?: string; fields: ContentTypeField[] }) =>
    apiClient.post("/content/admin/content-types", body).then((r) => r.data),
  listEntries: (slug: string, params?: { status?: string; locale?: string }) =>
    apiClient
      .get<ContentEntryRow[]>(`/content/admin/content-types/${slug}/entries`, { params })
      .then((r) => r.data),
  createEntry: (
    slug: string,
    body: {
      data: Record<string, unknown>;
      status?: string;
      locale?: string;
      scheduled_publish_at?: string | null;
    },
  ) => apiClient.post(`/content/admin/content-types/${slug}/entries`, body).then((r) => r.data),
  updateEntry: (
    id: string,
    body: {
      data?: Record<string, unknown>;
      status?: string;
      scheduled_publish_at?: string | null;
      scheduled_unpublish_at?: string | null;
    },
  ) => apiClient.patch(`/content/admin/entries/${id}`, body).then((r) => r.data),
  trashEntry: (id: string) => apiClient.delete(`/content/admin/entries/${id}`),
  restoreEntry: (id: string) =>
    apiClient.post(`/content/admin/entries/${id}/restore`).then((r) => r.data),
  permanentDeleteEntry: (id: string) => apiClient.delete(`/content/admin/entries/${id}/permanent`),
  revisions: (id: string) =>
    apiClient.get(`/content/admin/entries/${id}/revisions`).then((r) => r.data),
  restoreRevision: (id: string, revisionNumber: number) =>
    apiClient
      .post(`/content/admin/entries/${id}/revisions/${revisionNumber}/restore`)
      .then((r) => r.data),
};

// ── Content transfer ────────────────────────────────────────────────────────

export const contentTransferApi = {
  export: () => apiClient.get("/content/admin/content/export").then((r) => r.data),
  import: (doc: unknown) =>
    apiClient.post("/content/admin/content/import", doc).then((r) => r.data),
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

/** Storefront-side access to content types.
 *
 *  Separate from `contentTypesApi` above on purpose: that one is behind the
 *  admin guard and can list entries in any status, which is not what a
 *  customer is allowed to see. The public route only ever returns published
 *  entries, and reaching for the admin client from a storefront page would
 *  silently change what the page shows if the two were ever merged.
 */
export interface ContentTypeField {
  key: string;
  label: string;
  type: string;
}

export interface ContentTypePublic {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  field_schema: ContentTypeField[];
}

export interface PublicContentEntry {
  id: string;
  data: Record<string, unknown>;
  locale?: string | null;
  position?: number | null;
}

export const contentTypesPublicApi = {
  /** Every active type, for a nav entry or a landing page. */
  list: async (): Promise<ContentTypePublic[]> => {
    const { data } = await apiClient.get<ContentTypePublic[]>("/content/content-types");
    return Array.isArray(data) ? data : [];
  },

  /** Published entries of one type. Never any other status. */
  entries: async (
    typeSlug: string,
    params?: { locale?: string },
  ): Promise<PublicContentEntry[]> => {
    const { data } = await apiClient.get<PublicContentEntry[]>(
      `/content/content-types/${typeSlug}/entries`,
      { params },
    );
    return Array.isArray(data) ? data : [];
  },
};
