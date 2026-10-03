import apiClient from "./client";

// --- Types ---
// Field names mirror the backend MediaAssetResponse exactly: id is a UUID
// string and the public URL field is file_url (not url).

export interface MediaUsage {
  /** Total live references. The delete is refused while this is non-zero. */
  total: number;
  /** One Persian line naming the buckets, e.g. "نوشته: ۳، دسته‌بندی: ۱". */
  summary: string;
  posts: number;
  pages: number;
  custom_entries: number;
  categories: number;
  brands: number;
  vendors: number;
  user_profiles: number;
  seo_metadata: number;
  documents: number;
  logistics: number;
  products: number;
  in_html: number;
}

export interface MediaAsset {
  id: string;
  uploader_id: string | null;
  file_name: string;
  file_path: string;
  file_url: string;
  file_size: number;
  mime_type: string;
  width?: number | null;
  height?: number | null;
  alt_text?: string | null;
  /** WordPress's Title field. NULL means never titled; surfaces fall back to
   *  `file_name` rather than showing a blank. */
  title?: string | null;
  caption?: string | null;
  description?: string | null;
  folder?: string | null;
  /** The post this asset is attached to: WordPress's "Attached to" column.
   *  `null` means unattached, a real state an operator filters for, not
   *  the absence of data. */
  post_id?: string | null;
  focal_x?: number | null;
  focal_y?: number | null;
  /**
   * Non-destructive editing chain. Set when this file was produced by editing
   * another one, which is what makes "restore the original" possible; absent on
   * an upload that was never edited.
   */
  source_asset_id?: string | null;
  edit_operation?: string | null;
  /** Computed by the server: an image with no alt text. The list used to
   *  recompute the rule locally and ignore this field entirely — so the two
   *  could drift (e.g. a non-image with an empty alt) and the server's answer
   *  was never exercised. */
  needs_alt_text?: boolean;
  created_at: string;
  updated_at?: string;
}

export interface MediaListResponse {
  items: MediaAsset[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface MediaUploadResponse {
  asset: MediaAsset;
  message: string;
}

/** One file that failed inside a batch; the accepted ones are not rolled back. */
export interface MediaBatchUploadError {
  filename: string;
  error: string;
}

export interface MediaBatchUploadResponse {
  uploaded: MediaAsset[];
  errors: MediaBatchUploadError[];
}

// --- API ---

export const mediaApi = {
  /** آپلود فایل رسانه‌ای — پاسخ مستقیم MediaAsset است */
  upload: async (data: FormData): Promise<MediaAsset> => {
    const res = await apiClient.post<MediaUploadResponse>("/media/upload", data, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data.asset;
  },

  /**
   * آپلود چند فایل در یک درخواست
   *
   * The endpoint took one file at a time before, so an operator with twenty
   * assets to add clicked upload twenty times and watched twenty toasts fire.
   * Each file still succeeds or fails on its own: a rejected one comes back in
   * `errors` rather than failing the whole request.
   */
  uploadBatch: async (
    files: File[],
    folder?: string,
  ): Promise<MediaBatchUploadResponse> => {
    const fd = new FormData();
    for (const file of files) fd.append("files", file);
    if (folder) fd.append("folder", folder);
    const res = await apiClient.post<MediaBatchUploadResponse>(
      "/media/upload/batch",
      fd,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return res.data;
  },

  /**
   * سایدلود تصویر از URL — WordPress's "Add media from URL".
   *
   * The server fetches the URL behind an SSRF guard (private and loopback
   * addresses are refused there, not here). The operator pastes a link they
   * were given — a supplier's photo, a press image — instead of downloading
   * it to their machine first and re-uploading it.
   */
  sideload: async (body: {
    url: string;
    alt_text?: string;
    folder?: string;
  }): Promise<MediaAsset> => {
    const res = await apiClient.post<MediaAsset>("/media/sideload", body);
    return res.data;
  },

  /** لیست فایل‌های رسانه‌ای */
  list: async (params?: {
    page?: number;
    page_size?: number;
    mime_type?: string;
    folder?: string;
    search?: string;
    /** Only assets attached to this post. Mutually exclusive with
     *  `unattached` — the server refuses the pair rather than guessing. */
    post_id?: string;
    /** Only assets attached to nothing. */
    unattached?: boolean;
    /** Only assets uploaded at or after this instant. */
    created_from?: string;
    /** Only assets uploaded at or before this instant. */
    created_to?: string;
  }): Promise<MediaListResponse> => {
    const res = await apiClient.get<MediaListResponse>("/media", { params });
    return res.data;
  },

  /** دریافت یک فایل رسانه‌ای */
  get: async (assetId: string): Promise<MediaAsset> => {
    const res = await apiClient.get<MediaAsset>(`/media/${assetId}`);
    return res.data;
  },

  /** به‌روزرسانی متادیتای فایل (متن جایگزین، زیرنویس، توضیحات، پوشه) */
  update: async (
    assetId: string,
    data: {
      alt_text?: string | null;
      title?: string | null;
      caption?: string | null;
      description?: string | null;
      folder?: string | null;
    },
  ): Promise<MediaAsset> => {
    const res = await apiClient.patch<MediaAsset>(`/media/${assetId}`, data);
    return res.data;
  },

  /** حذف فایل رسانه‌ای */
  /** Replace the bytes behind an asset, keeping its URL. The new file must be
   *  the same type as the old one; the server refuses a mismatch rather than
   *  serving jpeg bytes from a .png URL. */
  replaceFile: async (assetId: string, file: File): Promise<MediaAsset> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await apiClient.post<MediaAsset>(`/media/${assetId}/replace`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },

  /** Trash many assets in one request. Per-item results, because a partial
   *  success is the normal case: one file still in use must not hide the fact
   *  that the other nineteen went. */
  bulkTrash: async (
    ids: string[],
    opts?: { force?: boolean },
  ): Promise<{ ok: number; failed: number; total: number; results: Array<Record<string, unknown>> }> => {
    const { data } = await apiClient.post<{
      ok: number;
      failed: number;
      total: number;
      results: Array<Record<string, unknown>>;
    }>("/media/bulk-trash", { ids, force: opts?.force ?? false });
    return data;
  },

  delete: async (assetId: string, opts?: { force?: boolean }): Promise<void> => {
    await apiClient.delete(`/media/${assetId}`, {
      params: opts?.force ? { force: true } : undefined,
    });
  },

  /** The trash: soft-deleted assets, oldest first. */
  listTrash: async (page: number = 1, pageSize: number = 20): Promise<MediaListResponse> => {
    const { data } = await apiClient.get<MediaListResponse>("/media/trash", {
      params: { page, page_size: pageSize },
    });
    return data;
  },

  /** Bring a trashed asset back into the library. */
  restore: async (assetId: string): Promise<MediaAsset> => {
    const { data } = await apiClient.post<MediaAsset>(`/media/${assetId}/restore`);
    return data;
  },

  /** Remove one trashed asset for good. */
  purge: async (assetId: string): Promise<void> => {
    await apiClient.delete(`/media/trash/${assetId}`);
  },

  /** Empty the trash. Pass olderThanDays so a scheduled run can never purge
   *  something an operator is about to restore. */
  emptyTrash: async (olderThanDays?: number): Promise<{ purged: number }> => {
    const { data } = await apiClient.post<{ purged: number }>(
      "/media/trash/empty",
      undefined,
      { params: olderThanDays ? { older_than_days: olderThanDays } : undefined },
    );
    return data;
  },

  /** Where this asset is referenced. The delete confirmation asks for this
   *  first, so it can say "the cover of 3 posts" instead of "are you sure". */
  usage: async (assetId: string): Promise<MediaUsage> => {
    const { data } = await apiClient.get<MediaUsage>(`/media/${assetId}/usage`);
    return data;
  },

  /** درخت پوشه‌های رسانه با شمار فایل */
  listFolders: async (): Promise<Array<{ path: string; asset_count: number }>> => {
    const res = await apiClient.get<Array<{ path: string; asset_count: number }>>(
      "/media/folders",
    );
    return Array.isArray(res.data) ? res.data : [];
  },

  /** جابه‌جایی گروهی فایل‌ها به یک پوشه (null = ریشه) */
  move: async (ids: string[], folder: string | null): Promise<{ moved: number }> => {
    const res = await apiClient.post<{ moved: number }>("/media/move", {
      ids,
      folder,
    });
    return res.data;
  },

  /** ساخت پوشه (می‌تواند خالی باشد) */
  createFolder: async (path: string): Promise<{ path: string; created: boolean }> => {
    const res = await apiClient.post<{ path: string; created: boolean }>("/media/folders", {
      path,
    });
    return res.data;
  },

  /** حذف پوشه؛ بدون confirm وقتی فایل دارد، خطا می‌دهد */
  deleteFolder: async (
    path: string,
    deleteAssets = false,
  ): Promise<{ path: string; removed: number }> => {
    const res = await apiClient.delete<{ path: string; removed: number }>("/media/folders", {
      data: { path, delete_assets: deleteAssets },
    });
    return res.data;
  },

  /** تنظیم نقطه کانونی برش هوشمند (مختصات نسبی ۰..۱) */
  setFocalPoint: async (assetId: string, x: number, y: number): Promise<MediaAsset> => {
    const res = await apiClient.patch<MediaAsset>(`/media/${assetId}/focal-point`, {
      focal_x: x,
      focal_y: y,
    });
    return res.data;
  },

  /** اتصال یک فایل به یک نوشته (null = جدا کردن) */
  attachToPost: async (assetId: string, postId: string | null): Promise<MediaAsset> => {
    const res = await apiClient.put<MediaAsset>(`/media/${assetId}/attach`, {
      post_id: postId,
    });
    return res.data;
  },

  /** URL واریانت رندرشده روی سرور (resize/format on the fly) */
  variantUrl: (assetId: string, params: { width?: number; height?: number; quality?: number; fmt?: string }): string => {
    const q = new URLSearchParams();
    if (params.width) q.set("width", String(params.width));
    if (params.height) q.set("height", String(params.height));
    if (params.quality) q.set("quality", String(params.quality));
    if (params.fmt) q.set("fmt", params.fmt);
    return `/api/v1/media/${assetId}/variant?${q.toString()}`;
  },
};
