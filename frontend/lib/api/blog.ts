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
  /** Free text about the tag. Absent on older API responses, so treat
   *  undefined as "no description yet" rather than an empty string. */
  description?: string | null;
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
  /**
   * Legacy addressing: set for post comments, `null` for page comments. The
   * API really does send null for a CMS-page comment, so this cannot be typed
   * `string` — an admin replying to a page comment was posting to
   * `/blog/posts/null/comments` and getting a 422.
   * Use `resource_type` + `resource_id` to address a comment.
   */
  post_id: string | null;
  /** Which kind of object this comment belongs to: "blog_post" | "cms_page". */
  resource_type: "blog_post" | "cms_page";
  /** UUID of the target post or page; null only on legacy rows. */
  resource_id: string | null;
  author_id?: string | null;
  author_name?: string | null;
  author_email?: string | null;
  author_url?: string | null;
  /** The address the comment came from. Admin responses only — the public
   *  endpoint withholds it, and a type that carries it on both is a type that
   *  invites someone to render it where a visitor can see it. */
  author_ip?: string | null;
  /** Present on admin responses; lets the editor say a password is set without
   *  a second request. Never carries the password itself. */
  author_date?: string | null;
  /** Uploaded avatar, else Gravatar; absent means render initials. */
  author_avatar_url?: string | null;
  content: string;
  status: CommentStatus;
  /**
   * "comment" for a reader's comment, "note" for a private team note. Only the
   * admin schema carries it: a public read never returns a note, so the field
   * is absent there by design.
   */
  comment_type?: "comment" | "note";
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

export interface CustomTaxonomyTerm {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  parent_id?: string | null;
}

/** Terms of a custom taxonomy, for a storefront archive.
 *
 *  Separate from `fetchBlogCategories` and `fetchBlogTags`, which are the two
 *  built-in taxonomies. A custom taxonomy is a third vocabulary with its own
 *  slug, and reading it through one of the others returns the wrong list — the
 *  archive for "product type" showing the blog's categories, which is a page
 *  that looks right and is not.
 */
export async function fetchCustomTaxonomyTerms(
  taxonomySlug: string,
): Promise<CustomTaxonomyTerm[]> {
  const { data } = await apiClient.get<CustomTaxonomyTerm[]>(
    `/blog/taxonomies/${encodeURIComponent(taxonomySlug)}/terms`,
  );
  return Array.isArray(data) ? data : [];
}

export interface CustomTaxonomyTermPost {
  id: string;
  slug: string;
  title: string;
  excerpt?: string | null;
  content?: string | null;
  cover_image_url?: string | null;
  published_at?: string | null;
}

/** Published posts carrying one custom term.
 *
 *  Filtered on the server rather than in the page. Paging the whole blog and
 *  filtering here looks identical and stops being right as soon as the blog has
 *  more posts than fit in one page — the term's archive starts showing posts
 *  that are not in the term.
 */
export async function fetchCustomTaxonomyTermPosts(
  taxonomySlug: string,
  termSlug: string,
  page = 1,
  pageSize = 12,
): Promise<{
  term: { id: string; name: string; slug: string; description?: string | null };
  items: CustomTaxonomyTermPost[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}> {
  const { data } = await apiClient.get(
    `/blog/taxonomies/${encodeURIComponent(taxonomySlug)}` +
    `/terms/${encodeURIComponent(termSlug)}/posts`,
    { params: { page, page_size: pageSize } },
  );
  return data;
}

export async function fetchBlogTags(): Promise<BlogTag[]> {
  const { data } = await apiClient.get<BlogTag[]>("/blog/tags");
  return Array.isArray(data) ? data : [];
}

export async function fetchResourceComments(
  resourceType: "blog_post" | "cms_page",
  resourceId: string,
  page: number = 1,
  pageSize: number = 20,
): Promise<BlogCommentListResponse> {
  const { data } = await apiClient.get<BlogCommentListResponse>("/blog/comments", {
    params: { resource_type: resourceType, resource_id: resourceId, page, page_size: pageSize },
  });
  return data;
}

export async function submitResourceComment(
  resourceType: "blog_post" | "cms_page",
  resourceId: string,
  payload: {
    content: string;
    parent_id?: string;
    author_name?: string;
    author_email?: string;
    author_url?: string;
  },
): Promise<BlogComment> {
  const { data } = await apiClient.post<BlogComment>("/blog/comments", {
    ...payload,
    resource_type: resourceType,
    resource_id: resourceId,
  });
  return data;
}

/**
 * Where a reply to this comment should be posted.
 *
 * A comment is addressed by (resource_type, resource_id). Reading `post_id`
 * instead breaks on a CMS-page comment, where the API sends null — the reply
 * then goes to `/blog/posts/null/comments` and 422s. Legacy rows may carry a
 * post_id and no resource_id, so post_id stays as a fallback; when neither is
 * present the caller must not attempt a reply at all.
 */
export function commentTarget(
  comment: Pick<BlogComment, "post_id" | "resource_type" | "resource_id">,
): { resourceType: "blog_post" | "cms_page"; resourceId: string } | null {
  const resourceId = comment.resource_id ?? comment.post_id;
  if (!resourceId) return null;
  return { resourceType: comment.resource_type ?? "blog_post", resourceId };
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
  /** Move the post to another author; omit to keep the current one. */
  author_id?: string;
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

/** One word-level token of an inline diff. `equal`+`delete` reconstructs the
 *  older text; `equal`+`insert` reconstructs the newer one. */
export interface RevisionDiffToken {
  op: "equal" | "insert" | "delete";
  text: string;
}

export interface RevisionFieldDiff {
  field: string;
  label: string;
  changed: boolean;
  a?: string | null;
  b?: string | null;
  /** Present for long text fields (the body). */
  inline_diff?: RevisionDiffToken[] | null;
}

export interface RevisionDiffResponse {
  post_id: string;
  rev_a: { id: string; revision_number: number; created_at?: string | null };
  rev_b: { id: string; revision_number: number; created_at?: string | null };
  fields: RevisionFieldDiff[];
  changed: boolean;
}

export const blogAdminApi = {
  listPosts: async (params?: {
    category?: string;
    status?: BlogPostStatus;
    search?: string;
    author_id?: string;
    /** ISO instants bounding published_at, inclusive on both ends. */
    published_from?: string;
    published_to?: string;
    is_featured?: boolean;
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
  /** WordPress's "convert categories to tags". Destructive-capable, so the
   *  response reports the skipped posts as well as the converted ones. */
  categoriesToTags: async (
    opts?: { postIds?: string[]; clearCategories?: boolean },
  ): Promise<{
    converted: number;
    skipped_no_category: number;
    tags_created: number;
    tags_reused: number;
    categories_cleared: boolean;
    posts_considered: number;
  }> => {
    const { data } = await apiClient.post<{
      converted: number;
      skipped_no_category: number;
      tags_created: number;
      tags_reused: number;
      categories_cleared: boolean;
      posts_considered: number;
    }>("/admin/blog/categories-to-tags", {
      post_ids: opts?.postIds,
      clear_categories: opts?.clearCategories ?? false,
    });
    return data;
  },

  /** Purge the post trash. Omitting the window empties all of it, which is
   *  why the dialog always sends a number. */
  emptyPostTrash: async (
    olderThanDays?: number,
  ): Promise<{ removed: number; post_ids: string[] }> => {
    const { data } = await apiClient.post<{ removed: number; post_ids: string[] }>(
      "/admin/blog/posts/empty-trash",
      { older_than_days: olderThanDays },
    );
    return data;
  },

  bulkPosts: async (
    ids: string[],
    action: "publish" | "draft" | "archive" | "trash" | "restore" | "edit",
    edits?: Partial<AdminBlogPostInput>,
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
    }>(`/admin/blog/posts/bulk/${action}`, { ids, edits });
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

  /** Field-level diff between two stored revisions.
   *  The backend compares by revision *id* (not number), because restoring an
   *  old number back onto the post makes two different rows claim it. */
  diffRevisions: async (
    postId: string,
    revAId: string,
    revBId: string,
  ): Promise<RevisionDiffResponse> => {
    const { data } = await apiClient.get<RevisionDiffResponse>(
      `/admin/blog/posts/${postId}/revisions/${revAId}/diff/${revBId}`,
    );
    return data;
  },

  /* Comments */
  listComments: async (params?: {
    post_id?: string;
    status?: CommentStatus;
    // Omitted, the moderation table shows comments and private notes together;
    // "comment" or "note" narrows to one.
    comment_type?: "comment" | "note";
    resource_type?: string;
    resource_id?: string;
    threaded?: boolean;
    /** Body, author name, email or website. Server-side: filtering the page
     *  already in hand would miss a match on a later page. */
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<BlogCommentListResponse> => {
    const { data } = await apiClient.get<BlogCommentListResponse>("/admin/blog/comments", {
      params,
    });
    return data;
  },

  /** Attach a private team note. Never reaches a public read. */
  createCommentNote: async (body: {
    resource_type?: "blog_post" | "cms_page";
    resource_id: string;
    content: string;
    parent_id?: string;
  }): Promise<BlogComment> => {
    const { data } = await apiClient.post<BlogComment>("/admin/blog/comments/notes", body);
    return data;
  },

  /** How many comments are waiting for a decision, and how many went to spam.
   *
   *  Separate from the moderation list for a reason that is easy to get wrong:
   *  the list paginates, so its `total` is only right on page one. A nav badge
   *  built from it would read 20 whenever twenty comments were waiting and one
   *  when forty were — a number that goes down as the queue grows. */
  pendingCommentCount: async (): Promise<{ pending: number; spam: number }> => {
    const { data } = await apiClient.get<{ pending: number; spam: number }>(
      "/admin/blog/comments/pending-count",
    );
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

  /** One moderation action over many comments. Reports per-comment outcomes
   *  so the UI can say "40 approved, 2 not found" rather than a single count. */
  bulkComments: async (
    ids: string[],
    action: "approve" | "unapprove" | "spam" | "trash" | "restore" | "delete",
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
    }>(`/admin/blog/comments/bulk/${action}`, { ids });
    return data;
  },

  updateComment: async (
    id: string,
    body: {
      content?: string;
      status?: CommentStatus;
      author_name?: string | null;
      author_email?: string | null;
      author_url?: string | null;
    },
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
  /* Lock and autosave cover posts and CMS pages alike — WordPress applies one
     mechanism to everything an author can edit, and the two types differ
     only in which table the id is looked up in. `kind` defaults to "posts" so
     every existing caller keeps working. */
  acquireLock: async (
    postId: string,
    kind: "posts" | "pages" = "posts",
  ): Promise<{ locked: boolean; locked_by?: string }> => {
    const { data } = await apiClient.post<{ locked: boolean; locked_by?: string }>(
      `/admin/blog/${kind}/${postId}/lock`,
    );
    return data;
  },

  /* Break another editor's lock and take it.
   *
   * A lock outlives the tab that took it when that tab is closed abruptly, and
   * the escape has to exist — otherwise the only way out is the full editor.
   */
  takeOverLock: async (
    postId: string,
    kind: "posts" | "pages" = "posts",
  ): Promise<{ acquired: boolean }> => {
    const { data } = await apiClient.post<{ acquired: boolean }>(
      `/admin/blog/${kind}/${postId}/lock/take-over`,
    );
    return data;
  },

  releaseLock: async (
    postId: string,
    kind: "posts" | "pages" = "posts",
  ): Promise<{ released: boolean }> => {
    const { data } = await apiClient.delete<{ released: boolean }>(
      `/admin/blog/${kind}/${postId}/lock`,
    );
    return data;
  },

  heartbeatLock: async (
    postId: string,
    kind: "posts" | "pages" = "posts",
  ): Promise<{ extended: boolean }> => {
    const { data } = await apiClient.post<{ extended: boolean }>(
      `/admin/blog/${kind}/${postId}/lock/heartbeat`,
    );
    return data;
  },

  checkLock: async (
    postId: string,
    kind: "posts" | "pages" = "posts",
  ): Promise<{ locked: boolean; locked_by?: string }> => {
    const { data } = await apiClient.get<{ locked: boolean; locked_by?: string }>(
      `/admin/blog/${kind}/${postId}/lock`,
    );
    return data;
  },

  /* Autosave */
  saveAutosave: async (
    postId: string,
    payload: Record<string, unknown>,
    kind: "posts" | "pages" = "posts",
  ): Promise<{ saved: boolean; saved_at?: string }> => {
    const { data } = await apiClient.post<{ saved: boolean; saved_at?: string }>(
      `/admin/blog/${kind}/${postId}/autosave`,
      payload,
    );
    return data;
  },

  getAutosave: async (
    postId: string,
    kind: "posts" | "pages" = "posts",
  ): Promise<{ has_autosave: boolean; data?: Record<string, unknown>; saved_at?: string }> => {
    const { data } = await apiClient.get<{
      has_autosave: boolean;
      data?: Record<string, unknown>;
      saved_at?: string;
    }>(`/admin/blog/${kind}/${postId}/autosave`);
    return data;
  },

  clearAutosave: async (
    postId: string,
    kind: "posts" | "pages" = "posts",
  ): Promise<void> => {
    await apiClient.delete(`/admin/blog/${kind}/${postId}/autosave`);
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
  updateCategory: async (
    id: string,
    data: {
      name?: string;
      slug?: string;
      description?: string | null;
      /** null moves the category to the top level. */
      parent_id?: string | null;
      /** Manual order among siblings; lower sorts first. */
      position?: number;
    },
  ): Promise<BlogPostCategory> => {
    const { data: res } = await apiClient.patch<BlogPostCategory>(`/blog/categories/${id}`, data);
    return res;
  },

  deleteCategory: async (id: string): Promise<{ deleted: boolean; orphaned_posts: number }> => {
    const { data } = await apiClient.delete<{ deleted: boolean; orphaned_posts: number }>(
      `/blog/categories/${id}`,
    );
    return data;
  },

  updateTag: async (
    id: string,
    data: { name?: string; slug?: string; description?: string | null },
  ): Promise<BlogTag> => {
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
