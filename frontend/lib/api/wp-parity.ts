/**
 * API client for WordPress-parity features.
 *
 * Covers the endpoints added for: custom taxonomies, custom post types,
 * editorial workflow, editorial calendar, quick edit, blog import/export,
 * post relationships, breadcrumbs, site options, site health, privacy/GDPR,
 * widget areas, capabilities, media image editing, thumbnails, and EXIF.
 */

import { apiClient } from "./client";

// ── Custom taxonomies ──────────────────────────────────────────────────────

export interface CustomTaxonomy {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  hierarchical: boolean;
  is_active: boolean;
  /** How many terms this taxonomy holds; returned by the list endpoint. */
  term_count?: number;
}

export interface CustomTaxonomyTerm {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  position?: number;
  parent_id?: string | null;
  /** How many posts reference this term; returned by the list endpoint. */
  post_count?: number;
}

export const taxonomiesApi = {
  list: async (): Promise<CustomTaxonomy[]> => {
    const { data } = await apiClient.get<CustomTaxonomy[]>("/admin/blog/taxonomies");
    return data;
  },

  create: async (body: {
    name: string;
    slug?: string;
    description?: string;
    hierarchical?: boolean;
  }): Promise<CustomTaxonomy> => {
    const { data } = await apiClient.post<CustomTaxonomy>("/admin/blog/taxonomies", body);
    return data;
  },

  update: async (
    taxonomyId: string,
    body: Partial<{
      name: string;
      slug: string;
      description: string | null;
      hierarchical: boolean;
      is_active: boolean;
    }>,
  ): Promise<CustomTaxonomy> => {
    const { data } = await apiClient.patch<CustomTaxonomy>(
      `/admin/blog/taxonomies/${taxonomyId}`,
      body,
    );
    return data;
  },

  /** Deletes the taxonomy; its terms and post links cascade. */
  remove: async (
    taxonomyId: string,
  ): Promise<{ taxonomies_deleted: number; terms_deleted: number; post_links_deleted: number }> => {
    const { data } = await apiClient.delete<{
      taxonomies_deleted: number;
      terms_deleted: number;
      post_links_deleted: number;
    }>(`/admin/blog/taxonomies/${taxonomyId}`);
    return data;
  },

  listTerms: async (taxonomyId: string): Promise<CustomTaxonomyTerm[]> => {
    const { data } = await apiClient.get<CustomTaxonomyTerm[]>(
      `/admin/blog/taxonomies/${taxonomyId}/terms`,
    );
    return data;
  },

  createTerm: async (
    taxonomyId: string,
    body: { name: string; slug?: string; description?: string; parent_id?: string },
  ): Promise<CustomTaxonomyTerm> => {
    const { data } = await apiClient.post<CustomTaxonomyTerm>(
      `/admin/blog/taxonomies/${taxonomyId}/terms`,
      body,
    );
    return data;
  },

  updateTerm: async (
    taxonomyId: string,
    termId: string,
    body: Partial<{
      name: string;
      slug: string;
      description: string | null;
      position: number;
      parent_id: string | null;
    }>,
  ): Promise<CustomTaxonomyTerm> => {
    const { data } = await apiClient.patch<CustomTaxonomyTerm>(
      `/admin/blog/taxonomies/${taxonomyId}/terms/${termId}`,
      body,
    );
    return data;
  },

  removeTerm: async (
    taxonomyId: string,
    termId: string,
  ): Promise<{ terms_deleted: number; post_links_deleted: number }> => {
    const { data } = await apiClient.delete<{
      terms_deleted: number;
      post_links_deleted: number;
    }>(`/admin/blog/taxonomies/${taxonomyId}/terms/${termId}`);
    return data;
  },

  attachToPost: async (postId: string, termIds: string[]): Promise<{ attached: number }> => {
    const { data } = await apiClient.post<{ attached: number }>(
      `/admin/blog/posts/${postId}/terms`,
      { term_ids: termIds },
    );
    return data;
  },
};

// ── Custom post types ──────────────────────────────────────────────────────

export interface ContentTypeField {
  key: string;
  label: string;
  type: "text" | "number" | "image" | "rich" | "boolean" | "date";
  required?: boolean;
  min?: number;
  max?: number;
}

export interface CustomPostType {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  icon?: string | null;
  field_schema?: ContentTypeField[] | null;
  supports_categories: boolean;
  supports_comments: boolean;
  is_active: boolean;
}

export interface CustomPostEntry {
  id: string;
  title: string;
  slug: string;
  status: string;
  fields?: Record<string, unknown> | null;
  excerpt?: string | null;
  cover_image_url?: string | null;
  position?: number;
}

export const contentTypesApi = {
  list: async (): Promise<CustomPostType[]> => {
    const { data } = await apiClient.get<CustomPostType[]>("/admin/blog/content-types");
    return data;
  },

  create: async (body: {
    name: string;
    slug?: string;
    description?: string;
    icon?: string;
    field_schema?: ContentTypeField[];
  }): Promise<CustomPostType> => {
    const { data } = await apiClient.post<CustomPostType>("/admin/blog/content-types", body);
    return data;
  },

  update: async (
    typeId: string,
    body: Partial<{
      name: string;
      slug: string;
      description: string | null;
      icon: string | null;
      field_schema: ContentTypeField[] | null;
      supports_categories: boolean;
      supports_comments: boolean;
      is_active: boolean;
    }>,
  ): Promise<CustomPostType> => {
    const { data } = await apiClient.patch<CustomPostType>(
      `/admin/blog/content-types/${typeId}`,
      body,
    );
    return data;
  },

  /** Deletes the post type and every entry under it. */
  remove: async (
    typeId: string,
  ): Promise<{ content_types_deleted: number; entries_deleted: number }> => {
    const { data } = await apiClient.delete<{
      content_types_deleted: number;
      entries_deleted: number;
    }>(`/admin/blog/content-types/${typeId}`);
    return data;
  },

  listEntries: async (typeId: string): Promise<CustomPostEntry[]> => {
    const { data } = await apiClient.get<CustomPostEntry[]>(
      `/admin/blog/content-types/${typeId}/entries`,
    );
    return data;
  },

  createEntry: async (
    typeId: string,
    body: {
      title: string;
      slug?: string;
      fields?: Record<string, unknown>;
      excerpt?: string;
      cover_image_url?: string;
    },
  ): Promise<CustomPostEntry> => {
    const { data } = await apiClient.post<CustomPostEntry>(
      `/admin/blog/content-types/${typeId}/entries`,
      body,
    );
    return data;
  },

  updateEntry: async (
    typeId: string,
    entryId: string,
    body: Partial<{
      title: string;
      slug: string;
      fields: Record<string, unknown> | null;
      excerpt: string | null;
      cover_image_url: string | null;
      status: "draft" | "published" | "archived";
      position: number;
    }>,
  ): Promise<CustomPostEntry> => {
    const { data } = await apiClient.patch<CustomPostEntry>(
      `/admin/blog/content-types/${typeId}/entries/${entryId}`,
      body,
    );
    return data;
  },

  removeEntry: async (typeId: string, entryId: string): Promise<{ entries_deleted: number }> => {
    const { data } = await apiClient.delete<{ entries_deleted: number }>(
      `/admin/blog/content-types/${typeId}/entries/${entryId}`,
    );
    return data;
  },
};

// ── Editorial workflow ─────────────────────────────────────────────────────

export const editorialApi = {
  submitForReview: async (postId: string): Promise<{ status: string }> => {
    const { data } = await apiClient.post<{ status: string }>(
      `/admin/blog/posts/${postId}/submit-for-review`,
    );
    return data;
  },

  approve: async (postId: string): Promise<{ status: string }> => {
    const { data } = await apiClient.post<{ status: string }>(
      `/admin/blog/posts/${postId}/approve`,
    );
    return data;
  },

  reject: async (postId: string, reason = ""): Promise<{ status: string }> => {
    const { data } = await apiClient.post<{ status: string }>(
      `/admin/blog/posts/${postId}/reject`,
      { reason },
    );
    return data;
  },

  pendingReview: async (): Promise<Array<{ id: string; title: string; slug: string }>> => {
    const { data } = await apiClient.get<Array<{ id: string; title: string; slug: string }>>(
      "/admin/blog/pending-review",
    );
    return data;
  },
};

// ── Editorial calendar ─────────────────────────────────────────────────────

export interface CalendarDay {
  [date: string]: Array<{
    id: string;
    title: string;
    slug: string;
    status: string;
    published_at?: string | null;
    scheduled_for?: string | null;
  }>;
}

export interface EditorialCalendar {
  year: number;
  month: number;
  days: CalendarDay;
  total_posts: number;
  by_status: { published: number; draft: number; scheduled: number };
}

export const calendarApi = {
  getMonth: async (year: number, month: number): Promise<EditorialCalendar> => {
    const { data } = await apiClient.get<EditorialCalendar>("/admin/blog/editorial-calendar", {
      params: { year, month },
    });
    return data;
  },
};

// ── Quick edit ─────────────────────────────────────────────────────────────

export const quickEditApi = {
  patch: async (
    postId: string,
    fields: Record<string, unknown>,
  ): Promise<{ updated_fields: Record<string, string> }> => {
    const { data } = await apiClient.patch<{ updated_fields: Record<string, string> }>(
      `/admin/blog/posts/${postId}/quick-edit`,
      fields,
    );
    return data;
  },
};

// ── Import / Export ────────────────────────────────────────────────────────

export const blogTransferApi = {
  exportAll: async (): Promise<Record<string, unknown>> => {
    const { data } = await apiClient.get<Record<string, unknown>>("/admin/blog/export");
    return data;
  },

  importJson: async (
    payload: Record<string, unknown>,
  ): Promise<{ categories: number; tags: number; posts: number; skipped: number }> => {
    const { data } = await apiClient.post<{
      categories: number;
      tags: number;
      posts: number;
      skipped: number;
    }>("/admin/blog/import", payload);
    return data;
  },
};

// ── Post relationships ─────────────────────────────────────────────────────

export interface PostRelationship {
  id: string;
  source_post_id: string;
  target_post_id: string;
  relationship_type: string;
}

export const relationshipsApi = {
  list: async (postId: string): Promise<PostRelationship[]> => {
    const { data } = await apiClient.get<PostRelationship[]>(
      `/admin/blog/posts/${postId}/relationships`,
    );
    return data;
  },

  create: async (
    postId: string,
    targetPostId: string,
    relationshipType = "related",
  ): Promise<PostRelationship> => {
    const { data } = await apiClient.post<PostRelationship>(
      `/admin/blog/posts/${postId}/relationships`,
      { target_post_id: targetPostId, relationship_type: relationshipType },
    );
    return data;
  },
};

// ── Breadcrumbs ────────────────────────────────────────────────────────────

export interface BreadcrumbItem {
  label: string;
  url: string | null;
  is_current: boolean;
}

export const breadcrumbsApi = {
  forPost: async (
    slug: string,
  ): Promise<{ items: BreadcrumbItem[]; json_ld: Record<string, unknown> }> => {
    const { data } = await apiClient.get<{
      items: BreadcrumbItem[];
      json_ld: Record<string, unknown>;
    }>("/blog/posts/" + slug + "/breadcrumbs");
    return data;
  },
};

// ── Gravatar ───────────────────────────────────────────────────────────────

export const gravatarApi = {
  url: async (email: string, size = 80): Promise<{ url: string }> => {
    const { data } = await apiClient.get<{ url: string }>("/settings/public/gravatar", {
      params: { email, size },
    });
    return data;
  },
};

// ── Site options ───────────────────────────────────────────────────────────

export const siteOptionsApi = {
  list: async (): Promise<Record<string, string | null>> => {
    const { data } = await apiClient.get<Record<string, string | null>>(
      "/settings/admin/site-options",
    );
    return data;
  },

  set: async (key: string, value: string | null, autoload = true): Promise<void> => {
    await apiClient.put(`/settings/admin/site-options/${key}`, { value, autoload });
  },

  remove: async (key: string): Promise<void> => {
    await apiClient.delete(`/settings/admin/site-options/${key}`);
  },

  seedDefaults: async (): Promise<{ seeded: number }> => {
    const { data } = await apiClient.post<{ seeded: number }>(
      "/settings/admin/site-options/seed-defaults",
    );
    return data;
  },
};

// ── Site health ────────────────────────────────────────────────────────────

export interface HealthCheck {
  name: string;
  status: "good" | "warning" | "critical";
  value: string;
  description: string;
  details?: unknown;
}

export interface RecoveryModeState {
  paused: boolean;
  state?: Record<string, unknown> | null;
  resumed?: boolean;
}

export interface SiteHealthReport {
  overall_status: "good" | "warning" | "critical";
  checked_at: string;
  checks: HealthCheck[];
  summary: { good: number; warning: number; critical: number };
}

/** One key/value block of the info tab. Values are pre-formatted server-side. */
export interface SiteHealthInfoSection {
  [key: string]: string | number | boolean | null | undefined;
}

export interface SiteHealthInfo {
  sections: Record<string, SiteHealthInfoSection>;
  generated_at: string;
}

export const siteHealthApi = {
  run: async (): Promise<SiteHealthReport> => {
    const { data } = await apiClient.get<SiteHealthReport>("/settings/admin/site-health");
    return data;
  },

  /** The WordPress "Site Health → Info" tab: versions, database, storage.
   *  The backend builds this from an allow-list, so no secret can appear in it
   *  by default — which matters because operators paste it into tickets. */
  info: async (): Promise<SiteHealthInfo> => {
    const { data } = await apiClient.get<SiteHealthInfo>("/settings/admin/site-health/info");
    return data;
  },

  optimizeDatabase: async (): Promise<{ status: string; message: string }> => {
    const { data } = await apiClient.post<{ status: string; message: string }>(
      "/settings/admin/site-health/optimize-database",
    );
    return data;
  },

  /** Recovery mode pauses the site behind a 503 after an unhandled error.
   *  Both routes existed with no caller, so the only way back from a paused
   *  site was to delete the pause flag by hand on the host. */
  recoveryMode: async (): Promise<RecoveryModeState> => {
    const { data } = await apiClient.get<RecoveryModeState>(
      "/settings/admin/recovery-mode",
    );
    return data;
  },

  resumeRecoveryMode: async (): Promise<RecoveryModeState> => {
    const { data } = await apiClient.post<RecoveryModeState>(
      "/settings/admin/recovery-mode/resume",
    );
    return data;
  },
};

// ── Privacy / GDPR ─────────────────────────────────────────────────────────

export const privacyApi = {
  exportUser: async (userId: string): Promise<Record<string, unknown>> => {
    const { data } = await apiClient.get<Record<string, unknown>>(
      `/settings/admin/privacy/export/${userId}`,
    );
    return data;
  },

  eraseUser: async (
    userId: string,
    anonymize = true,
  ): Promise<{ actions: string[]; erased_at: string }> => {
    const { data } = await apiClient.post<{ actions: string[]; erased_at: string }>(
      `/settings/admin/privacy/erase/${userId}`,
      null,
      { params: { anonymize } },
    );
    return data;
  },
};

// ── Widget areas ───────────────────────────────────────────────────────────

export interface Widget {
  id: string;
  type: string;
  title?: string;
  config: Record<string, unknown>;
}

export interface WidgetArea {
  name: string;
  description: string;
  widgets: Widget[];
}

export const widgetsApi = {
  list: async (): Promise<{
    areas: Record<string, WidgetArea>;
    widget_types: Record<string, { name: string; description: string }>;
  }> => {
    const { data } = await apiClient.get<{
      areas: Record<string, WidgetArea>;
      widget_types: Record<string, { name: string; description: string }>;
    }>("/settings/admin/widgets");
    return data;
  },

  /** Public read for the storefront — only areas that contain widgets. */
  publicAreas: async (): Promise<{
    areas: Record<string, WidgetArea>;
    widget_types: Record<string, { name: string; description: string }>;
  }> => {
    const { data } = await apiClient.get<{
      areas: Record<string, WidgetArea>;
      widget_types: Record<string, { name: string; description: string }>;
    }>("/settings/public/widgets");
    return data;
  },

  updateArea: async (areaId: string, widgets: Widget[]): Promise<WidgetArea> => {
    const { data } = await apiClient.put<WidgetArea>(`/settings/admin/widgets/${areaId}`, {
      widgets,
    });
    return data;
  },
};

// ── Capabilities ───────────────────────────────────────────────────────────

export const capabilitiesApi = {
  list: async (): Promise<{ roles: Record<string, string[]>; all: string[] }> => {
    const { data } = await apiClient.get<{ roles: Record<string, string[]>; all: string[] }>(
      "/admin/blog/capabilities",
    );
    return data;
  },
};

// ── Media editing ──────────────────────────────────────────────────────────

export const mediaEditingApi = {
  crop: async (
    assetId: string,
    rect: { x: number; y: number; width: number; height: number },
  ): Promise<{ id: string; file_url: string }> => {
    const { data } = await apiClient.post<{ id: string; file_url: string }>(
      `/media/${assetId}/edit/crop`,
      rect,
    );
    return data;
  },

  resize: async (
    assetId: string,
    size: { width: number; height?: number },
  ): Promise<{ id: string; file_url: string }> => {
    const { data } = await apiClient.post<{ id: string; file_url: string }>(
      `/media/${assetId}/edit/resize`,
      size,
    );
    return data;
  },

  rotate: async (
    assetId: string,
    degrees: number,
  ): Promise<{ id: string; file_url: string }> => {
    const { data } = await apiClient.post<{ id: string; file_url: string }>(
      `/media/${assetId}/edit/rotate`,
      { degrees },
    );
    return data;
  },

  /** Mirror on one axis. horizontal=true (default) flips left-right. */
  flip: async (
    assetId: string,
    horizontal: boolean = true,
  ): Promise<{ id: string; file_url: string }> => {
    const { data } = await apiClient.post<{ id: string; file_url: string }>(
      `/media/${assetId}/edit/flip`,
      { horizontal },
    );
    return data;
  },

  exif: async (assetId: string): Promise<Record<string, unknown>> => {
    const { data } = await apiClient.get<Record<string, unknown>>(`/media/${assetId}/exif`);
    return data;
  },

  regenerateThumbnails: async (
    assetId: string,
  ): Promise<{ generated: string[]; files: Record<string, string> }> => {
    const { data } = await apiClient.post<{ generated: string[]; files: Record<string, string> }>(
      `/media/${assetId}/regenerate-thumbnails`,
    );
    return data;
  },

  regenerateAll: async (): Promise<{
    total: number;
    success: number;
    failed: number;
    skipped: number;
  }> => {
    const { data } = await apiClient.post<{
      total: number;
      success: number;
      failed: number;
      skipped: number;
    }>("/media/regenerate-all-thumbnails");
    return data;
  },

  optimize: async (
    assetId: string,
    opts?: { quality?: number; convert_to_webp?: boolean },
  ): Promise<{ original_size: number; new_size: number; savings_pct: number }> => {
    const { data } = await apiClient.post<{
      original_size: number;
      new_size: number;
      savings_pct: number;
    }>(`/media/${assetId}/optimize`, opts ?? {});
    return data;
  },
};

/** A post sitting in the editorial queue awaiting a publisher's decision. */
export interface PendingReviewPost {
  id: string;
  title: string;
  slug: string;
  updated_at: string;
}

/**
 * The submit → review → publish/reject cycle.
 *
 * The backend for all four calls has existed for a while and nothing in the
 * admin called it, so a post could enter `pending_review` and then sit there
 * with no editor able to see the queue, approve it, or send it back — the one
 * workflow a contributor's whole role depends on.
 */
export const editorialWorkflowApi = {
  pending: async (page = 1, pageSize = 20): Promise<PendingReviewPost[]> => {
    const { data } = await apiClient.get<PendingReviewPost[]>(
      `/admin/blog/pending-review?page=${page}&page_size=${pageSize}`,
    );
    return data;
  },

  submitForReview: async (postId: string): Promise<{ status: string }> => {
    const { data } = await apiClient.post<{ status: string }>(
      `/admin/blog/posts/${postId}/submit-for-review`,
    );
    return data;
  },

  approve: async (postId: string): Promise<{ status: string }> => {
    const { data } = await apiClient.post<{ status: string }>(
      `/admin/blog/posts/${postId}/approve`,
    );
    return data;
  },

  reject: async (postId: string, reason = ""): Promise<{ status: string }> => {
    const { data } = await apiClient.post<{ status: string }>(
      `/admin/blog/posts/${postId}/reject`,
      { reason },
    );
    return data;
  },
};
