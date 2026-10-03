import apiClient from "./client";

// --- Types ---

export interface ContentBlock {
  id: string; // backend is UUIDv4
  created_at?: string;
  block_type:
    | "slider"
    | "category_grid"
    | "featured_products"
    | "discount_carousel"
    | "banner_grid"
    | "html_custom";
  title: string;
  config: Record<string, unknown> | null;
  position: number;
  is_active: boolean;
}

export interface MenuItem {
  id: string; // backend is UUIDv4
  parent_id: string | null;
  title: string;
  url: string;
  location: string;
  position: number;
  icon?: string | null;
  is_active?: boolean;
  children?: MenuItem[];
}

export interface Faq {
  id: string; // backend is UUIDv4
  question: string;
  answer_html: string;
  category?: string;
  position: number;
  is_active: boolean;
}

export type CmsPageStatus = "draft" | "pending_review" | "published" | "archived";

export interface CmsPage {
  id: string; // backend is UUIDv4
  title: string;
  slug: string;
  body_html: string;
  excerpt: string | null;
  status: CmsPageStatus;
  published_at: string | null;
  seo_title: string | null;
  seo_description: string | null;
  author_id: string | null;
  revision_number: number;
  locale: string;
  scheduled_publish_at: string | null;
  scheduled_unpublish_at: string | null;
  deleted_at: string | null;
  /** Whether readers may comment on this page; server-owned opt-in, false by
   *  default. Absent on older API responses, so treat undefined as false. */
  allow_comments?: boolean;
  /** Parent page id, null for a top-level page. */
  parent_id?: string | null;
  /** Manual ordering among siblings; lower sorts first. */
  menu_order?: number;
  cover_image_url?: string | null;
  visibility?: CmsPageVisibility;
  /** Whether a password is set. The hash itself never leaves the server, so
   *  without this the password field looks unset on a protected page and
   *  saving the form would submit an empty string. */
  visibility_password_set?: boolean;
  created_at: string;
  updated_at: string;
}

export interface CmsPageList {
  items: CmsPage[];
  total: number;
}

export interface CmsPageRevision {
  id: string;
  page_id: string;
  revision_number: number;
  title: string;
  slug: string;
  status: string;
  created_at: string;
}

export interface CmsPageInput {
  title: string;
  slug?: string;
  body_html?: string;
  excerpt?: string | null;
  status?: CmsPageStatus;
  seo_title?: string | null;
  seo_description?: string | null;
  locale?: string;
  scheduled_publish_at?: string | null;
  scheduled_unpublish_at?: string | null;
  allow_comments?: boolean;
  /**
   * Parent page, for the page tree. The column, the schema and the server's
   * cycle check all existed; only the client type and the admin form were
   * missing, so a page could never be nested.
   */
  parent_id?: string | null;
  /** Manual ordering among siblings. Lower comes first. */
  menu_order?: number | null;
  /** Hero image for the storefront page. */
  cover_image_url?: string | null;
  visibility?: CmsPageVisibility;
  /** Plaintext; the server hashes it and never returns it. */
  visibility_password?: string | null;
}

/** Who may read a published page. Separate from the status: a page can be
 *  published and still private. */
export type CmsPageVisibility = "public" | "private" | "password";

export interface BulkActionResult {
  succeeded: number;
  failed: number;
  errors: Record<string, string>;
}

export interface ThemeConfig {
  name?: string;
  colors: Record<string, string>;
  typography?: { font_family?: string; base_size_px?: number; heading_weight?: number };
  radius?: string;
  dark_mode_default?: boolean;
}

// --- API (user) ---

export const contentApi = {
  /** بلاک‌های صفحه اصلی */
  getHomepageBlocks: async (): Promise<ContentBlock[]> => {
    const res = await apiClient.get<ContentBlock[]>("/content/blocks");
    return Array.isArray(res.data) ? res.data : [];
  },

  /** منوی ناوبری بر اساس موقعیت */
  getMenu: async (location: string): Promise<MenuItem[]> => {
    const res = await apiClient.get<MenuItem[]>(`/content/menus/${location}`);
    return Array.isArray(res.data) ? res.data : [];
  },

  /** The built-in menu locations plus any operator-created ones in use. */
  listMenuLocations: async (): Promise<{
    builtin: string[];
    custom: string[];
    all: string[];
  }> => {
    const res = await apiClient.get<{
      builtin: string[];
      custom: string[];
      all: string[];
    }>("/content/menus/locations");
    return res.data;
  },

  /** سوالات متداول */
  getFaqs: async (category?: string): Promise<Faq[]> => {
    const res = await apiClient.get<Faq[] | { items: Faq[] }>("/content/faqs", {
      params: category ? { category } : undefined,
    });
    return Array.isArray(res.data) ? res.data : (res.data.items ?? []);
  },
};

// --- CMS pages (WordPress-style pages) ---

export const cmsPagesApi = {
  /** صفحه منتشرشده برای فروشگاه (public) */
  getPage: async (slug: string): Promise<CmsPage> => {
    const res = await apiClient.get<CmsPage>(`/content/pages/${slug}`);
    return res.data;
  },
};

export const cmsPagesAdminApi = {
  listPages: async (params?: {
    status?: CmsPageStatus;
    search?: string;
    locale?: string;
    sort?: string;
    include_trashed?: boolean;
  }): Promise<CmsPageList> => {
    const res = await apiClient.get<CmsPageList>("/content/admin/pages", { params });
    return res.data;
  },

  /** Live slug availability, for the editor's inline check.
   *  Gated server-side on the same permission as writing pages. */
  /** Purge the page trash. Omitting the window empties all of it, which is why
   *  the dialog always sends a number. */
  emptyPageTrash: async (
    olderThanDays?: number,
  ): Promise<{ removed: number; page_ids: string[] }> => {
    const { data } = await apiClient.post<{ removed: number; page_ids: string[] }>(
      "/content/admin/pages/empty-trash",
      { older_than_days: olderThanDays },
    );
    return data;
  },

  checkSlug: async (
    slug: string,
    pageId?: string,
  ): Promise<{ slug: string; available: boolean; reason: "empty" | "reserved" | "taken" | null }> => {
    const { data } = await apiClient.get<{
      slug: string;
      available: boolean;
      reason: "empty" | "reserved" | "taken" | null;
    }>("/content/admin/pages/slug-check", {
      params: { slug, page_id: pageId || undefined },
    });
    return data;
  },

  getPage: async (id: string): Promise<CmsPage> => {
    const res = await apiClient.get<CmsPage>(`/content/admin/pages/${id}`);
    return res.data;
  },

  createPage: async (data: CmsPageInput): Promise<CmsPage> => {
    const res = await apiClient.post<CmsPage>("/content/admin/pages", data);
    return res.data;
  },

  updatePage: async (id: string, data: Partial<CmsPageInput>): Promise<CmsPage> => {
    const res = await apiClient.patch<CmsPage>(`/content/admin/pages/${id}`, data);
    return res.data;
  },

  deletePage: async (id: string): Promise<void> => {
    await apiClient.delete(`/content/admin/pages/${id}`);
  },

  listRevisions: async (id: string): Promise<CmsPageRevision[]> => {
    const res = await apiClient.get<CmsPageRevision[]>(
      `/content/admin/pages/${id}/revisions`,
    );
    return Array.isArray(res.data) ? res.data : [];
  },

  restoreRevision: async (id: string, revisionNumber: number): Promise<CmsPage> => {
    const res = await apiClient.post<CmsPage>(
      `/content/admin/pages/${id}/revisions/${revisionNumber}/restore`,
    );
    return res.data;
  },

  /** تکثیر صفحه به‌صورت پیش‌نویس جدید (نامک یکتا) */
  duplicatePage: async (id: string): Promise<CmsPage> => {
    const res = await apiClient.post<CmsPage>(`/content/admin/pages/${id}/duplicate`);
    return res.data;
  },

  /** بازگردانی صفحه از سطل زباله */
  restorePage: async (id: string): Promise<CmsPage> => {
    const res = await apiClient.post<CmsPage>(`/content/admin/pages/${id}/restore`);
    return res.data;
  },

  /** حذف دائم — فقط از داخل سطل زباله */
  permanentDeletePage: async (id: string): Promise<void> => {
    await apiClient.delete(`/content/admin/pages/${id}/permanent`);
  },

  /** عملیات گروهی: publish | unpublish | trash | restore */
  bulkAction: async (action: string, ids: string[]): Promise<BulkActionResult> => {
    const res = await apiClient.post<BulkActionResult>(
      `/content/admin/pages/bulk/${action}`,
      { ids },
    );
    return res.data;
  },
};

// --- API (admin) ---

export const contentAdminApi = {
  // ── Blocks ──────────────────────────────────────────────────────────────
  /** ایجاد بلاک محتوا */
  createBlock: async (data: Omit<ContentBlock, "id" | "created_at">): Promise<ContentBlock> => {
    const res = await apiClient.post<ContentBlock>("/content/admin/blocks", data);
    return res.data;
  },

  /** ویرایش بلوک (عنوان/پیکربندی/ترتیب/فعال‌بودن) */
  updateBlock: async (
    id: string,
    data: Partial<Pick<ContentBlock, "title" | "config" | "position" | "is_active">>,
  ): Promise<ContentBlock> => {
    const res = await apiClient.patch<ContentBlock>(`/content/admin/blocks/${id}`, data);
    return res.data;
  },

  /** حذف بلوک */
  deleteBlock: async (id: string): Promise<void> => {
    await apiClient.delete(`/content/admin/blocks/${id}`);
  },

  /** مرتب‌سازی بلاک‌ها — backend expects { positions: { uuid: position } } */
  reorderBlocks: async (positions: Record<string, number>): Promise<void> => {
    await apiClient.put("/content/admin/blocks/reorder", { positions });
  },

  // ── Menus ────────────────────────────────────────────────────────────────
  /** ایجاد آیتم منو */
  createMenuItem: async (data: Omit<MenuItem, "id" | "children">): Promise<MenuItem> => {
    const res = await apiClient.post<MenuItem>("/content/admin/menus", data);
    return res.data;
  },

  /** ویرایش آیتم منو */
  updateMenuItem: async (
    id: string,
    data: Partial<Pick<MenuItem, "title" | "url" | "position" | "icon" | "is_active">>,
  ): Promise<MenuItem> => {
    const res = await apiClient.patch<MenuItem>(`/content/admin/menus/${id}`, data);
    return res.data;
  },

  /** حذف آیتم منو */
  deleteMenuItem: async (id: string): Promise<void> => {
    await apiClient.delete(`/content/admin/menus/${id}`);
  },

  /** بازچینش و جابه‌جایی درختی منو در یک درخواست.
   *
   *  Reordering used to mean one PATCH per item with a hand-computed position,
   *  and a failure halfway through left the menu in a mixed order. The
   *  `parent_id` each item carries is what re-nests a dragged branch. */
  reorderMenu: async (
    location: string,
    items: { id: string; parent_id?: string | null; position: number }[],
  ): Promise<{ updated: number; tree: MenuItem[] }> => {
    const res = await apiClient.put<{ updated: number; tree: MenuItem[] }>(
      `/content/admin/menus/${location}/reorder`,
      { items },
    );
    return res.data;
  },

  // ── FAQs ────────────────────────────────────────────────────────────────
  /** ایجاد سوال متداول */
  createFaq: async (data: { question: string; answer_html: string; category?: string; position?: number }): Promise<Faq> => {
    const res = await apiClient.post<Faq>("/content/admin/faqs", data);
    return res.data;
  },

  /** ویرایش سوال متداول */
  updateFaq: async (
    id: string,
    data: Partial<{ question: string; answer_html: string; category: string; position: number; is_active: boolean }>,
  ): Promise<Faq> => {
    const res = await apiClient.patch<Faq>(`/content/admin/faqs/${id}`, data);
    return res.data;
  },

  /** حذف سوال متداول */
  deleteFaq: async (id: string): Promise<void> => {
    await apiClient.delete(`/content/admin/faqs/${id}`);
  },
};

// --- Single Types (Strapi-style singleton configs) ---

export interface SingleType<T = Record<string, unknown>> {
  key: string;
  value: T | null;
  updated_at: string | null;
}

export interface HomepageConfig {
  hero_banner: {
    title?: string;
    subtitle?: string;
    image_media_id?: string;
    cta_text?: string;
    cta_url?: string;
  } | null;
  featured_category_slugs: string[];
  announcement_bar: { enabled: boolean; text: string; url: string };
  show_recent_blog_posts: boolean;
}

export interface HeaderMenuConfig {
  cta_button: { label: string; url: string; visible: boolean };
  top_bar_message: string;
  highlight_menu_item: string | null;
}

export const singleTypesApi = {
  /** لیست تایپ‌های تکی ثبت‌شده */
  list: async (): Promise<{ key: string; description: string }[]> => {
    const res = await apiClient.get<{ key: string; description: string }[]>(
      "/content/single-types",
    );
    return Array.isArray(res.data) ? res.data : [];
  },

  /** دریافت پیکربندی صفحه اصلی (public) */
  getHomepageConfig: async (): Promise<SingleType<HomepageConfig>> => {
    const res = await apiClient.get<SingleType<HomepageConfig>>(
      "/content/single-types/homepage_config",
    );
    return res.data;
  },

  /** دریافت تنظیمات هدر (public) */
  getHeaderMenu: async (): Promise<SingleType<HeaderMenuConfig>> => {
    const res = await apiClient.get<SingleType<HeaderMenuConfig>>(
      "/content/single-types/header_menu",
    );
    return res.data;
  },

  /** دریافت توکن‌های تم (public — رنگ‌ها و تایپوگرافی فروشگاه) */
  getTheme: async (): Promise<SingleType<ThemeConfig>> => {
    const res = await apiClient.get<SingleType<ThemeConfig>>(
      "/content/single-types/theme",
    );
    return res.data;
  },
};

export const singleTypesAdminApi = {
  /** ذخیره یک تایپ تکی (admin) */
  upsert: async <T = Record<string, unknown>>(
    key: string,
    value: T,
  ): Promise<SingleType<T>> => {
    const res = await apiClient.put<SingleType<T>>(`/content/admin/single-types/${key}`, {
      value,
    });
    return res.data;
  },
};
