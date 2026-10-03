import apiClient from "./client";

// ── Data-exchange (generic import/export) admin API ─────────────────────────

export interface DataExchangeColumn {
  key: string;
  label: string;
  required: boolean;
  type: "string" | "integer" | "boolean";
  aliases: string[];
}

export interface DataExchangeEntity {
  entity_type: string;
  label: string;
  columns: DataExchangeColumn[];
}

export interface ImportJobStats {
  total: number;
  valid: number;
  invalid: number;
  imported: number;
  skipped: number;
}

export type ImportJobStatus =
  | "draft"
  | "mapping"
  | "validating"
  | "ready"
  | "importing"
  | "completed"
  | "failed";

export interface ImportJob {
  id: string;
  entity_type: string;
  status: ImportJobStatus;
  original_filename: string;
  detected_headers: string[] | null;
  column_mapping: Record<string, string> | null;
  stats: ImportJobStats | null;
  has_error_report: boolean;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ExportJob {
  id: string;
  entity_type: string;
  status: "pending" | "processing" | "completed" | "failed";
  filters: Record<string, unknown> | null;
  row_count: number | null;
  created_at: string | null;
}

export interface ImportJobList {
  items: ImportJob[];
  total: number;
  page: number;
  page_size: number;
}

export interface ExportJobList {
  items: ExportJob[];
  total: number;
  page: number;
  page_size: number;
}

/** One post as an RSS/Atom feed describes it. */
export interface FeedPostPreview {
  title: string;
  content: string;
  excerpt: string | null;
  status: string;
  category_slug: string | null;
  tag_slugs: string[];
  published_at?: string;
}

/** What `previewFeed` reports: enough to decide before importing anything. */
export interface FeedPreview {
  format: "rss" | "atom";
  counts: { posts: number; categories: number; tags: number };
  sample: FeedPostPreview[];
  categories: Array<{ name: string }>;
  tags: Array<{ name: string }>;
}

/** What `importFeed` creates. Same shape `import_json` returns. */
export interface FeedImportStats {
  categories: number;
  tags: number;
  posts: number;
  skipped: number;
}

export const dataExchangeApi = {
  entities: () =>
    apiClient.get<DataExchangeEntity[]>("/admin/data-exchange/entities").then((r) => r.data),

  // ── Import ────────────────────────────────────────────────────────────────
  createImportJob: (entityType: string, file: File) => {
    const form = new FormData();
    form.append("entity_type", entityType);
    form.append("file", file);
    return apiClient
      .post<ImportJob>("/admin/import-jobs", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  /** Parse an RSS/Atom feed and report what it holds. Writes nothing. */
  previewFeed: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<FeedPreview>("/admin/import-feed/preview", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  /**
   * Import a feed. Every entry becomes a draft — a feed publishes by
   * definition, and an archive imported as live posts is unreviewed content on
   * the storefront.
   */
  importFeed: (file: File, skipExisting = true) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<FeedImportStats>("/admin/import-feed", form, {
        headers: { "Content-Type": "multipart/form-data" },
        params: { skip_existing: skipExisting },
      })
      .then((r) => r.data);
  },
  listImportJobs: (params?: { entity_type?: string; page?: number; page_size?: number }) =>
    apiClient
      .get<ImportJobList>("/admin/import-jobs", { params })
      .then((r) => r.data),
  getImportJob: (id: string) =>
    apiClient.get<ImportJob>(`/admin/import-jobs/${id}`).then((r) => r.data),
  autoMapping: (id: string) =>
    apiClient
      .get<{ mapping: Record<string, string> }>(`/admin/import-jobs/${id}/auto-mapping`)
      .then((r) => r.data.mapping),
  setMapping: (id: string, mapping: Record<string, string>) =>
    apiClient
      .post<{ job: ImportJob }>(`/admin/import-jobs/${id}/mapping`, { mapping })
      .then((r) => r.data.job),
  validateImportJob: (id: string) =>
    apiClient.post<ImportJob>(`/admin/import-jobs/${id}/validate`).then((r) => r.data),
  executeImportJob: (id: string, idempotencyKey?: string) =>
    apiClient
      .post<ImportJob>(`/admin/import-jobs/${id}/execute`, { idempotency_key: idempotencyKey })
      .then((r) => r.data),
  downloadErrorReport: (id: string) =>
    apiClient
      .get(`/admin/import-jobs/${id}/errors`, { responseType: "blob" })
      .then((r) => r.data as Blob),

  // ── Export ────────────────────────────────────────────────────────────────
  createExportJob: (entityType: string, filters: Record<string, unknown>) =>
    apiClient
      .post<ExportJob>("/admin/export-jobs", { entity_type: entityType, filters })
      .then((r) => r.data),
  listExportJobs: (params?: { entity_type?: string; page?: number; page_size?: number }) =>
    apiClient
      .get<ExportJobList>("/admin/export-jobs", { params })
      .then((r) => r.data),
  downloadExport: (id: string) =>
    apiClient
      .get(`/admin/export-jobs/${id}/download`, { responseType: "blob" })
      .then((r) => r.data as Blob),
};

/** Trigger a browser download for a Blob payload. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
