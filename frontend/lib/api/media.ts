import apiClient from "./client";

// --- Types ---
// Field names mirror the backend MediaAssetResponse exactly: id is a UUID
// string and the public URL field is file_url (not url).

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
  caption?: string | null;
  description?: string | null;
  folder?: string | null;
  focal_x?: number | null;
  focal_y?: number | null;
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

  /** لیست فایل‌های رسانه‌ای */
  list: async (params?: {
    page?: number;
    page_size?: number;
    mime_type?: string;
    folder?: string;
    search?: string;
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
      caption?: string | null;
      description?: string | null;
      folder?: string | null;
    },
  ): Promise<MediaAsset> => {
    const res = await apiClient.patch<MediaAsset>(`/media/${assetId}`, data);
    return res.data;
  },

  /** حذف فایل رسانه‌ای */
  delete: async (assetId: string): Promise<void> => {
    await apiClient.delete(`/media/${assetId}`);
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

  /** تنظیم نقطه کانونی برش هوشمند (مختصات نسبی ۰..۱) */
  setFocalPoint: async (assetId: string, x: number, y: number): Promise<MediaAsset> => {
    const res = await apiClient.patch<MediaAsset>(`/media/${assetId}/focal-point`, {
      focal_x: x,
      focal_y: y,
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
