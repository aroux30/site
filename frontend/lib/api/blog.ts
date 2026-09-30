import apiClient from "./client";

export interface BlogPostCategory {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  parent_id?: string | null;
  position?: number;
  created_at?: string;
  updated_at?: string;
  post_count?: number;
  /** Populated by GET /blog/categories/tree only. */
  children?: BlogPostCategory[];
  /** Root-first chain, for a breadcrumb on the category archive. */
  ancestors?: { id: string; name: string; slug: string }[];
}

export interface BlogTag {
  id: string;
  name: string;
  slug: string;
  created_at?: string;
  updated_at?: string;
  post_count?: number;
}

export type PostVisibility = "public" | "private" | "password";
export type PostFormat =
  | "standard"
  | "gallery"
  | "video"
  | "audio"
  | "quote"
  | "link"
  | "status"
  | "image";
export type CommentStatus = "pending" | "approved" | "spam" | "trash";

export interface BlogPost {
  id: string;
  author_id: string;
  author_slug?: string | null;
  author_name?: string;
  title: string;
  slug: string;
  locale?: string;
  // i18n: posts sharing a group are translations of one another (null = not
  // translated). The storefront language switcher groups on this.
  translation_group?: string | null;
  excerpt?: string;
  content?: string;
  cover_image_url?: string;
  status: "draft" | "pending_review" | "published" | "archived";
  published_at?: string;
  scheduled_for?: string;
  category_id?: string;
  category?: BlogPostCategory;
  tags?: BlogTag[];
  reading_time?: number;
  view_count: number;
  is_featured?: boolean;
  visibility?: PostVisibility;
  visibility_password?: string;
  /** Body withheld: the post is password-protected and no/wrong password
   *  was supplied. Render the unlock form instead of the article. */
  content_locked?: boolean;
  allow_comments?: boolean;
  post_format?: PostFormat;
  gallery_image_ids?: string[];
  comment_count?: number;
  deleted_at?: string | null;
  related_posts?: BlogPost[];
  seo?: {
    title?: string;
    description?: string;
    canonical_url?: string;
    og_title?: string;
    og_description?: string;
    og_image?: string;
    schema_markup?: Record<string, unknown>;
  };
  created_at: string;
  updated_at: string;
}

export interface BlogComment {
  id: string;
  post_id: string;
  author_id?: string | null;
  author_name?: string | null;
  author_email?: string | null;
  author_url?: string | null;
  /** Uploaded avatar, else Gravatar; absent means render initials. */
  author_avatar_url?: string | null;
  content: string;
  status: CommentStatus;
  parent_id?: string | null;
  created_at: string;
  updated_at: string;
  replies?: BlogComment[];
}

export interface BlogCommentListResponse {
  items: BlogComment[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface BlogPostMeta {
  id: string;
  post_id: string;
  meta_key: string;
  meta_value?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface BlogListResponse {
  items: BlogPost[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface BlogQueryParams {
  category?: string;
  tag?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

/* -------------------------------------------------------------------------- */
/*  Errors propagate: a dead API must never masquerade as "no posts" (BUG-FE-06) */
/* -------------------------------------------------------------------------- */

export async function fetchBlogPosts(
  params?: BlogQueryParams,
): Promise<BlogListResponse> {
  const { data } = await apiClient.get<BlogListResponse>("/blog/posts", {
    params,
  });
  return data;
}

export async function fetchBlogPostBySlug(
  slug: string,
  options?: { password?: string },
): Promise<BlogPost | null> {
  try {
    const { data } = await apiClient.get<BlogPost>(`/blog/posts/${slug}`, {
      // Only sent when the reader submitted the unlock form; the backend
      // verifies it against the stored Argon2 hash and answers with
      // content_locked=false + body on success.
      params: options?.password ? { password: options.password } : undefined,
    });
    if (data && data.id) {
      return data;
    }
    return null;
  } catch (error) {
    // A real 404 means the post does not exist. Network/5xx failures must
    // propagate so the detail page renders error.tsx instead of a fake 404.
    if (
      typeof error === "object" &&
      error !== null &&
      "response" in error &&
      (error as { response?: { status?: number } }).response?.status === 404
    ) {
      return null;
    }
    throw error;
  }
}

export async function fetchBlogCategories(): Promise<BlogPostCategory[]> {
  const { data } = await apiClient.get<BlogPostCategory[]>("/blog/categories");
  return Array.isArray(data) ? data : [];
}

export async function fetchBlogTags(): Promise<BlogTag[]> {
  const { data } = await apiClient.get<BlogTag[]>("/blog/tags");
  return Array.isArray(data) ? data : [];
}

export async function fetchPostComments(
  postId: string,
  page: number = 1,
  pageSize: number = 20,
): Promise<BlogCommentListResponse> {
  const { data } = await apiClient.get<BlogCommentListResponse>(
    `/blog/posts/${postId}/comments`,
    {
      params: { page, page_size: pageSize },
    },
  );
  return data;
}

export async function submitPostComment(
  postId: string,
  payload: {
    content: string;
    parent_id?: string;
    author_name?: string;
    author_email?: string;
    author_url?: string;
  },
): Promise<BlogComment> {
  const { data } = await apiClient.post<BlogComment>(
    `/blog/posts/${postId}/comments`,
    {
      post_id: postId,
      ...payload,
    },
  );
  return data;
}

/* -------------------------------------------------------------------------- */
/*  Admin                                                                     */
/* -------------------------------------------------------------------------- */

export type BlogPostStatus = "draft" | "pending_review" | "published" | "archived";

export interface AdminBlogPostInput {
  title: string;
  slug?: string;
  content: string;
  excerpt?: string;
  cover_image_url?: string;
  status?: BlogPostStatus;
  published_at?: string;
  category_id?: string;
  tag_ids?: string[];
  scheduled_for?: string;
  is_featured?: boolean;
  visibility?: PostVisibility;
  visibility_password?: string;
  allow_comments?: boolean;
  post_format?: PostFormat;
  gallery_image_ids?: string[];
}

export interface BlogRevision {
  id: string;
  revision_number: number;
  title: string;
  slug: string;
  status: string;
  created_at: string;
}

export const blogAdminApi = {
  listPosts: async (params?: {
    category?: string;
    status?: BlogPostStatus;
    search?: string;
    page?: number;
    page_size?: number;
    include_trashed?: boolean;
  }): Promise<BlogListResponse> => {
    const { data } = await apiClient.get<BlogListResponse>("/admin/blog/posts", {
      params,
    });
    return data;
  },

  getPost: async (id: string): Promise<BlogPost> => {
    const { data } = await apiClient.get<BlogPost>(`/admin/blog/posts/${id}`);
    return data;
  },

  createPost: async (body: AdminBlogPostInput): Promise<BlogPost> => {
    const { data } = await apiClient.post<BlogPost>("/admin/blog/posts", body);
    return data;
  },

  updatePost: async (id: string, body: Partial<AdminBlogPostInput>): Promise<BlogPost> => {
    const { data } = await apiClient.patch<BlogPost>(`/admin/blog/posts/${id}`, body);
    return data;
  },

  deletePost: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/blog/posts/${id}`);
  },

  restorePost: async (id: string): Promise<BlogPost> => {
    const { data } = await apiClient.post<BlogPost>(`/admin/blog/posts/${id}/restore`);
    return data;
  },

  hardDeletePost: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/blog/posts/${id}/permanent`);
  },

  /** One action over many posts (wave 6 #72).
   *  Per-post ownership is re-checked server-side, and the response reports
   *  each post's outcome — so the UI can say "17 of 20" instead of claiming
   *  all 20 succeeded. */
  bulkPosts: async (
    ids: string[],
    action: "publish" | "draft" | "archive" | "trash" | "restore",
  ): Promise<{
    action: string;
    ok: number;
    failed: number;
    total: number;
    results: { id: string; ok: boolean; error?: string }[];
  }> => {
    const { data } = await apiClient.post<{
      action: string;
      ok: number;
      failed: number;
      total: number;
      results: { id: string; ok: boolean; error?: string }[];
    }>(`/admin/blog/posts/bulk/${action}`, { ids });
    return data;
  },

  duplicatePost: async (id: string): Promise<BlogPost> => {
    const { data } = await apiClient.post<BlogPost>(`/admin/blog/posts/${id}/duplicate`);
    return data;
  },

  previewPost: async (id: string): Promise<BlogPost> => {
    const { data } = await apiClient.get<BlogPost>(`/admin/blog/posts/${id}/preview`);
    return data;
  },

  createTag: async (name: string, slug?: string): Promise<BlogTag> => {
    const { data } = await apiClient.post<BlogTag>("/admin/blog/tags", { name, slug });
    return data;
  },

  listRevisions: async (id: string): Promise<BlogRevision[]> => {
    const { data } = await apiClient.get<BlogRevision[]>(
      `/admin/blog/posts/${id}/revisions`,
    );
    return Array.isArray(data) ? data : [];
  },

  restoreRevision: async (id: string, revisionNumber: number): Promise<BlogPost> => {
    const { data } = await apiClient.post<BlogPost>(
      `/admin/blog/posts/${id}/revisions/${revisionNumber}/restore`,
    );
    return data;
  },

  /* Comments */
  listComments: async (params?: {
    post_id?: string;
    status?: CommentStatus;
    page?: number;
    page_size?: number;
  }): Promise<BlogCommentListResponse> => {
    const { data } = await apiClient.get<BlogCommentListResponse>("/admin/blog/comments", {
      params,
    });
    return data;
  },

  approveComment: async (id: string): Promise<BlogComment> => {
    const { data } = await apiClient.post<BlogComment>(`/admin/blog/comments/${id}/approve`);
    return data;
  },

  spamComment: async (id: string): Promise<BlogComment> => {
    const { data } = await apiClient.post<BlogComment>(`/admin/blog/comments/${id}/spam`);
    return data;
  },

  deleteComment: async (id: string): Promise<void> => {
    await apiClient.delete(`/admin/blog/comments/${id}`);
  },

  updateComment: async (
    id: string,
    body: { content?: string; status?: CommentStatus },
  ): Promise<BlogComment> => {
    const { data } = await apiClient.patch<BlogComment>(`/admin/blog/comments/${id}`, body);
    return data;
  },

  /* Post Meta (Custom Fields) */
  listPostMeta: async (postId: string): Promise<BlogPostMeta[]> => {
    const { data } = await apiClient.get<BlogPostMeta[]>(`/admin/blog/posts/${postId}/meta`);
    return Array.isArray(data) ? data : [];
  },

  upsertPostMeta: async (
    postId: string,
    body: { meta_key: string; meta_value?: string },
  ): Promise<BlogPostMeta> => {
    const { data } = await apiClient.post<BlogPostMeta>(`/admin/blog/posts/${postId}/meta`, body);
    return data;
  },

  deletePostMeta: async (postId: string, metaKey: string): Promise<void> => {
    await apiClient.delete(`/admin/blog/posts/${postId}/meta/${metaKey}`);
  },

  /* Post Locking */
  acquireLock: async (postId: string): Promise<{ locked: boolean; locked_by?: string }> => {
    const { data } = await apiClient.post<{ locked: boolean; locked_by?: string }>(
      `/admin/blog/posts/${postId}/lock`,
    );
    return data;
  },

  releaseLock: async (postId: string): Promise<{ released: boolean }> => {
    const { data } = await apiClient.delete<{ released: boolean }>(
      `/admin/blog/posts/${postId}/lock`,
    );
    return data;
  },

  heartbeatLock: async (postId: string): Promise<{ extended: boolean }> => {
    const { data } = await apiClient.post<{ extended: boolean }>(
      `/admin/blog/posts/${postId}/lock/heartbeat`,
    );
    return data;
  },

  checkLock: async (postId: string): Promise<{ locked: boolean; locked_by?: string }> => {
    const { data } = await apiClient.get<{ locked: boolean; locked_by?: string }>(
      `/admin/blog/posts/${postId}/lock`,
    );
    return data;
  },

  /* Autosave */
  saveAutosave: async (
    postId: string,
    payload: Record<string, unknown>,
  ): Promise<{ saved: boolean; saved_at?: string }> => {
    const { data } = await apiClient.post<{ saved: boolean; saved_at?: string }>(
      `/admin/blog/posts/${postId}/autosave`,
      payload,
    );
    return data;
  },

  getAutosave: async (
    postId: string,
  ): Promise<{ has_autosave: boolean; data?: Record<string, unknown>; saved_at?: string }> => {
    const { data } = await apiClient.get<{
      has_autosave: boolean;
      data?: Record<string, unknown>;
      saved_at?: string;
    }>(`/admin/blog/posts/${postId}/autosave`);
    return data;
  },

  clearAutosave: async (postId: string): Promise<void> => {
    await apiClient.delete(`/admin/blog/posts/${postId}/autosave`);
  },
};


/* ── Author archive (WordPress parity: /author/<slug>) ─────────────────── */

export interface BlogAuthor {
  slug: string;
  name: string;
  bio?: string | null;
  avatar_url?: string | null;
  post_count: number;
}

export interface BlogAuthorArchive {
  author: BlogAuthor;
  posts: BlogListResponse;
}

export async function fetchAuthorArchive(
  slug: string,
  page = 1,
  pageSize = 10,
): Promise<BlogAuthorArchive> {
  const { data } = await apiClient.get<BlogAuthorArchive>(`/blog/authors/${slug}`, {
    params: { page, page_size: pageSize },
  });
  return data;
}

/* ── Category / tag editing ────────────────────────────────────────────────
 * Only create existed, so a category could be added and then never renamed or
 * removed. Deleting orphans the posts rather than destroying them. */

export const blogTaxonomyApi = {
  updateCategory: async (id: string, data: { name?: string; slug?: string }): Promise<BlogPostCategory> => {
    const { data: res } = await apiClient.patch<BlogPostCategory>(`/blog/categories/${id}`, data);
    return res;
  },

  deleteCategory: async (id: string): Promise<{ deleted: boolean; orphaned_posts: number }> => {
    const { data } = await apiClient.delete<{ deleted: boolean; orphaned_posts: number }>(
      `/blog/categories/${id}`,
    );
    return data;
  },

  updateTag: async (id: string, data: { name?: string; slug?: string }): Promise<BlogTag> => {
    const { data: res } = await apiClient.patch<BlogTag>(`/blog/tags/${id}`, data);
    return res;
  },

  deleteTag: async (id: string): Promise<{ deleted: boolean; orphaned_posts: number }> => {
    const { data } = await apiClient.delete<{ deleted: boolean; orphaned_posts: number }>(
      `/blog/tags/${id}`,
    );
    return data;
  },
};

/** The category forest: roots first, each with nested children.
 *  Declared before the parameter routes on the server, so "tree" is not
 *  parsed as a category id. */
export async function fetchCategoryTree(): Promise<BlogPostCategory[]> {
  const { data } = await apiClient.get<BlogPostCategory[]>("/blog/categories/tree");
  return Array.isArray(data) ? data : [];
}
