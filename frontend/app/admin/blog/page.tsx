"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  BookOpen,
  ExternalLink,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  CalendarClock,
  CheckCircle2,
  Clock,
  History,
  Tag,
  Copy,
  RotateCcw,
  Sparkles,
  MessageSquare,
  Calendar,
  ClipboardCheck,
  Images,
  Video,
  Lock,
  Download,
  Upload,
  Zap,
  Eye,
  AlertCircle,
  FileCode,
  FolderTree,
  LayoutTemplate, GitCompare,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import RichBodyEditor from "@/components/admin/RichBodyEditor";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { MediaPicker } from "@/components/admin/media-picker";
import { BlockPatternPicker } from "@/components/admin/block-pattern-picker";
import { toPersianDigits } from "@/lib/utils";
import {
  blogAdminApi,
  fetchBlogCategories,
  fetchBlogTags,
  type BlogPost,
  type BlogPostCategory,
  type BlogPostStatus,
  type BlogRevision,
  type BlogTag,
  type PostVisibility,
  type PostFormat,
  type BlogPostMeta,
} from "@/lib/api/blog";
import { useAdminQuery } from "@/lib/api/admin-query";
import { CommentsModerationTab } from "@/components/admin/blog/comments-moderation-tab";
import { editorialWorkflowApi } from "@/lib/api/wp-parity";
import { ReviewQueueTab } from "@/components/admin/blog/review-queue-tab";
import { EditorialCalendarTab } from "@/components/admin/blog/editorial-calendar-tab";
import { QuickEditDialog } from "@/components/admin/blog/quick-edit-dialog";
import { usePageEditingLock } from "@/hooks/use-page-editing-lock";
import { PostPreviewDialog } from "@/components/admin/blog/post-preview-dialog";
import { RevisionCompareDialog } from "@/components/admin/blog/revision-compare-dialog";
import { BulkEditDialog } from "@/components/admin/blog/bulk-edit-dialog";
import { PostTermsPicker } from "@/components/admin/blog/post-terms-picker";
import { useAdminAuthors } from "@/hooks/use-admin-authors";
import { TaxonomiesTab } from "@/components/admin/blog/taxonomies-tab";
import { TaxonomyManagerTab } from "@/components/admin/blog/taxonomy-manager-tab";
import { ContentTypesTab } from "@/components/admin/blog/content-types-tab";
import { TransferTab } from "@/components/admin/blog/transfer-tab";

const BLOG_TAXONOMIES_QUERY_KEY = "admin-blog-taxonomies" as const;
const BLOG_POSTS_QUERY_KEY = "admin-blog-posts" as const;

const statusMeta: Record<BlogPostStatus, { label: string; className: string }> = {
  published: { label: "منتشر شده", className: "text-emerald-600" },
  draft: { label: "پیش‌نویس", className: "text-amber-600" },
  pending_review: { label: "در انتظار بازبینی", className: "text-sky-600" },
  archived: { label: "بایگانی", className: "text-muted-foreground" },
};

function isScheduled(post: BlogPost): boolean {
  if (!post.scheduled_for) return false;
  return new Date(post.scheduled_for).getTime() > Date.now() && post.status === "draft";
}

export default function AdminBlogPage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<string>("posts");
  const [search, setSearch] = useState("");
  // `?search=` seeds the filter box. The admin bar's contextual "ویرایش نوشته"
  // link lands here with the slug, so the operator sees the post they came from
  // instead of the whole list. Read once on mount: re-seeding on every render
  // would fight the operator's typing.
  const searchParam = useSearchParams()?.get("search");
  useEffect(() => {
    if (searchParam) setSearch(searchParam);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [statusFilter, setStatusFilter] = useState<BlogPostStatus | "all">("all");
  // Author / date-range / featured filters. The admin list had search and
  // status only, so "what did we publish in March" or "who writes the news
  // posts" meant reading the whole table. All three are server-side: filtering
  // the current page would silently hide matches on later pages.
  const [authorFilter, setAuthorFilter] = useState<string>("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [featuredOnly, setFeaturedOnly] = useState(false);

  // editor dialog
  const [editorOpen, setEditorOpen] = useState(false);
  // Non-published posts preview through the admin route; published ones keep
  // the plain site link, so this stays null in the common case.
  const [previewPostId, setPreviewPostId] = useState<string | null>(null);
  const [comparePostId, setComparePostId] = useState<string | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const [bulkEditOpen, setBulkEditOpen] = useState(false);
  const [bulkEditRows, setBulkEditRows] = useState<BlogPost[]>([]);
  const [editing, setEditing] = useState<BlogPost | null>(null);
  // Which post is mid-submit, so the button disables only for that one.
  const [submittingForReviewId, setSubmittingForReviewId] = useState<string | null>(
    null,
  );
  const [formTitle, setFormTitle] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formContent, setFormContent] = useState("");
  const [patternPickerOpen, setPatternPickerOpen] = useState(false);
  const [formExcerpt, setFormExcerpt] = useState("");
  const [formCover, setFormCover] = useState("");
  const [formStatus, setFormStatus] = useState<BlogPostStatus>("draft");
  const [formLocale, setFormLocale] = useState<string>("fa");
  const [formCategory, setFormCategory] = useState<string>("");
  const [formTagIds, setFormTagIds] = useState<string[]>([]);
  const [formScheduled, setFormScheduled] = useState<string>("");
  // The publish date of a post that is already live, and of one being backdated.
  // Distinct from formScheduled: a *future* date is a schedule the beat task
  // promotes, while this is a real publication date the server accepts today.
  const [formPublished, setFormPublished] = useState<string>("");
  const [formFeatured, setFormFeatured] = useState(false);
  const [formVisibility, setFormVisibility] = useState<PostVisibility>("public");
  const [formVisibilityPassword, setFormVisibilityPassword] = useState("");
  const [formAllowComments, setFormAllowComments] = useState(true);
  const [formFormat, setFormFormat] = useState<PostFormat>("standard");
  const [formGalleryImages, setFormGalleryImages] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  // Post Meta (Custom Fields)
  const [postMetas, setPostMetas] = useState<BlogPostMeta[]>([]);
  const [newMetaKey, setNewMetaKey] = useState("");
  const [newMetaValue, setNewMetaValue] = useState("");
  const [metaLoading, setMetaLoading] = useState(false);

  // Autosave & Locking
  const [autosaveNotice, setAutosaveNotice] = useState<{
    has: boolean;
    data?: Record<string, unknown>;
    savedAt?: string;
  } | null>(null);
  const [lockWarning, setLockWarning] = useState<string | null>(null);
  const heartbeatTimer = useRef<NodeJS.Timeout | null>(null);
  const autosaveTimer = useRef<NodeJS.Timeout | null>(null);

  // quick edit dialog
  const [quickEditPost, setQuickEditPost] = useState<BlogPost | null>(null);
  // WordPress offers a take-over when a lock is left behind by an
  // editor who closed their tab; the lock service had the override
  // and no route, so it was unreachable.
  const { lockedByOther, takeOver } = usePageEditingLock(
    editorOpen && editing ? editing.id : null,
    "posts",
  );
  const [quickEditOpen, setQuickEditOpen] = useState(false);

  // revision history dialog
  const [revOpen, setRevOpen] = useState(false);
  const [revPost, setRevPost] = useState<BlogPost | null>(null);
  const [revisions, setRevisions] = useState<BlogRevision[]>([]);
  const [revLoading, setRevLoading] = useState(false);
  const [restoring, setRestoring] = useState<number | null>(null);

  // Import file ref
  const importFileRef = useRef<HTMLInputElement | null>(null);

  // Taxonomies query
  const { data: taxonomies } = useAdminQuery({
    queryKey: [BLOG_TAXONOMIES_QUERY_KEY],
    queryFn: async () => {
      const [cats, tgs] = await Promise.all([fetchBlogCategories(), fetchBlogTags()]);
      return { categories: cats, tags: tgs };
    },
    fallbackError: "دریافت دسته‌ها و برچسب‌ها ناموفق بود",
  });
  const categories: BlogPostCategory[] = taxonomies?.categories ?? [];
  const tags: BlogTag[] = taxonomies?.tags ?? [];

  // Authors for the list filter. Walks every page of users rather than asking
  // for one oversized slice: the endpoint caps page_size at 100, so a single
  // call would quietly omit everyone past the hundred.
  const { authors, truncated: authorsTruncated } = useAdminAuthors();

  // Posts query
  const isTrashTab = activeTab === "trash";
  // Server-side paging: the list used to fetch a fixed 50 rows and page
  // client-side over those 50, so post 51 onward was unreachable. The pager now
  // asks the server for each page and pages over the real total.
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 25;
  const {
    data: postsData,
    loading,
    reload: loadPosts,
  } = useAdminQuery({
    queryKey: [
      BLOG_POSTS_QUERY_KEY, search, statusFilter, isTrashTab, page,
      authorFilter, dateFrom, dateTo, featuredOnly,
    ],
    queryFn: () =>
      blogAdminApi.listPosts({
        search: search || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
        // The API takes instants; a date input yields a local midnight, and
        // the end date must include its whole day or "1 March" loses
        // everything published that evening.
        published_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
        published_to: dateTo
          ? new Date(`${dateTo}T23:59:59`).toISOString()
          : undefined,
        author_id: authorFilter || undefined,
        is_featured: featuredOnly ? true : undefined,
        page,
        page_size: PAGE_SIZE,
        include_trashed: isTrashTab,
      }),
    fallbackError: "خطا در دریافت مقالات",
    toastOnError: true,
    toastDescription: "اتصال به سرویس وبلاگ برقرار نشد.",
  });
  const posts: BlogPost[] = (postsData?.items ?? []).filter((p) =>
    isTrashTab ? p.deleted_at !== null : p.deleted_at === null,
  );
  // The trash tab filters client-side, so the page in hand may hold fewer rows
  // than the server's total; paging still works, the count just reads high.
  const postsTotal = postsData?.total ?? 0;

  const resetForm = () => {
    setFormTitle("");
    setFormSlug("");
    setFormContent("");
    setFormExcerpt("");
    setFormCover("");
    setFormStatus("draft");
    setFormLocale("fa");
    setFormCategory("");
    setFormTagIds([]);
    setFormScheduled("");
    setFormPublished("");
    setFormFeatured(false);
    setFormVisibility("public");
    setFormVisibilityPassword("");
    setFormAllowComments(true);
    setFormFormat("standard");
    setFormGalleryImages([]);
    setPostMetas([]);
    setAutosaveNotice(null);
    setLockWarning(null);
  };

  const openCreate = () => {
    setEditing(null);
    resetForm();
    setEditorOpen(true);
  };

  const openEdit = async (post: BlogPost) => {
    setEditing(post);
    setFormTitle(post.title);
    setFormSlug(post.slug);
    setFormContent(post.content || "");
    setFormExcerpt(post.excerpt || "");
    setFormCover(post.cover_image_url || "");
    setFormStatus(post.status);
    setFormLocale(post.locale ?? "fa");
    setFormCategory(post.category_id || "");
    setFormTagIds((post.tags || []).map((t) => t.id));
    setFormScheduled(
      post.scheduled_for ? new Date(post.scheduled_for).toISOString().slice(0, 16) : "",
    );
    setFormPublished(
      post.published_at ? new Date(post.published_at).toISOString().slice(0, 16) : "",
    );
    setFormFeatured(post.is_featured || false);
    setFormVisibility(post.visibility || "public");
    setFormVisibilityPassword(post.visibility_password || "");
    setFormAllowComments(post.allow_comments !== false);
    setFormFormat(post.post_format || "standard");
    setFormGalleryImages(post.gallery_image_ids || []);
    setEditorOpen(true);

    // 1. Try to acquire lock
    try {
      const lockRes = await blogAdminApi.acquireLock(post.id);
      if (!lockRes.locked && lockRes.locked_by) {
        setLockWarning(`این نوشته در حال حاضر توسط کاربر دیگری در حال ویرایش است.`);
      } else {
        setLockWarning(null);
      }
    } catch {
      setLockWarning(null);
    }

    // 2. Check for autosave
    try {
      const autoRes = await blogAdminApi.getAutosave(post.id);
      if (autoRes.has_autosave && autoRes.data) {
        setAutosaveNotice({
          has: true,
          data: autoRes.data,
          savedAt: autoRes.saved_at,
        });
      } else {
        setAutosaveNotice(null);
      }
    } catch {
      setAutosaveNotice(null);
    }

    // 3. Load Post Meta
    loadPostMetas(post.id);
  };

  const loadPostMetas = async (postId: string) => {
    setMetaLoading(true);
    try {
      const metas = await blogAdminApi.listPostMeta(postId);
      setPostMetas(metas);
    } catch {
      setPostMetas([]);
    } finally {
      setMetaLoading(false);
    }
  };

  // A new filter or tab means a new result set: page 5 of the old one has no
  // meaning in the new one, and staying there shows an empty table.
  useEffect(() => {
    setPage(1);
  }, [search, statusFilter, activeTab]);
  // A narrowed filter usually shrinks the result set past the current page;
  // staying on page 4 would show an empty table and read as "no posts".
  useEffect(() => {
    setPage(1);
  }, [authorFilter, dateFrom, dateTo, featuredOnly]);

  // Heartbeat & Autosave interval hooks
  useEffect(() => {
    if (!editorOpen || !editing) {
      if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
      if (autosaveTimer.current) clearInterval(autosaveTimer.current);
      return;
    }

    const postId = editing.id;

    // Heartbeat every 45s
    heartbeatTimer.current = setInterval(() => {
      blogAdminApi.heartbeatLock(postId).catch(() => {});
    }, 45000);

    // Autosave every 30s
    autosaveTimer.current = setInterval(() => {
      if (formTitle.trim() || formContent.trim()) {
        blogAdminApi
          .saveAutosave(postId, {
            title: formTitle,
            content: formContent,
            excerpt: formExcerpt,
          })
          .catch(() => {});
      }
    }, 30000);

    return () => {
      if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
      if (autosaveTimer.current) clearInterval(autosaveTimer.current);
      // Release lock on close
      blogAdminApi.releaseLock(postId).catch(() => {});
    };
  }, [editorOpen, editing, formTitle, formContent, formExcerpt]);

  const handleRestoreAutosave = () => {
    if (!autosaveNotice?.data) return;
    const d = autosaveNotice.data as { title?: string; content?: string; excerpt?: string };
    if (d.title) setFormTitle(d.title);
    if (d.content) setFormContent(d.content);
    if (d.excerpt) setFormExcerpt(d.excerpt);
    setAutosaveNotice(null);
    toast({ title: "پیش‌نویس ذخیره خودکار بازیابی شد" });
  };

  const handleAddMeta = async () => {
    if (!editing || !newMetaKey.trim()) return;
    try {
      await blogAdminApi.upsertPostMeta(editing.id, {
        meta_key: newMetaKey.trim(),
        meta_value: newMetaValue.trim(),
      });
      setNewMetaKey("");
      setNewMetaValue("");
      await loadPostMetas(editing.id);
      toast({ title: "زمینه دلخواه اضافه شد" });
    } catch {
      toast({ title: "افزودن زمینه دلخواه ناموفق بود", variant: "destructive" });
    }
  };

  const handleDeleteMeta = async (key: string) => {
    if (!editing) return;
    try {
      await blogAdminApi.deletePostMeta(editing.id, key);
      await loadPostMetas(editing.id);
      toast({ title: "زمینه دلخواه حذف شد" });
    } catch {
      toast({ title: "حذف ناموفق بود", variant: "destructive" });
    }
  };

  const toggleTag = (id: string) => {
    setFormTagIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id],
    );
  };

  /**
   * Hand the saved post to the editorial queue.
   *
   * The submission works on the stored row, so this saves first — otherwise an
   * editor pressing it on unsaved changes would submit yesterday's text. A
   * failure is surfaced rather than swallowed: the post stays a draft and the
   * editor has to know why nothing happened.
   */
  const submitForReview = async (postId: string) => {
    setSubmittingForReviewId(postId);
    try {
      await handleSave();
      await editorialWorkflowApi.submitForReview(postId);
      toast({
        title: "نوشته برای بازبینی ارسال شد",
        description: "سردبیر آن را در «صف بازبینی» می‌بیند.",
      });
      setEditorOpen(false);
      await loadPosts();
    } catch (err) {
      toast({
        title: "ارسال برای بازبینی ناموفق بود",
        description:
          err instanceof Error
            ? err.message
            : "لطفاً دوباره تلاش کنید. نوشته همچنان پیش‌نویس است.",
        variant: "destructive",
      });
    } finally {
      setSubmittingForReviewId(null);
    }
  };

  const handleSave = async () => {
    if (!formTitle.trim() || !formContent.trim()) return;
    setSaving(true);
    const payload = {
      title: formTitle,
      slug: formSlug || undefined,
      content: formContent,
      excerpt: formExcerpt || undefined,
      cover_image_url: formCover || undefined,
      status: formStatus,
      locale: formLocale,
      category_id: formCategory || undefined,
      tag_ids: formTagIds,
      scheduled_for: formScheduled ? new Date(formScheduled).toISOString() : undefined,
      published_at: formPublished ? new Date(formPublished).toISOString() : undefined,
      is_featured: formFeatured,
      visibility: formVisibility,
      visibility_password: formVisibility === "password" ? formVisibilityPassword : undefined,
      allow_comments: formAllowComments,
      post_format: formFormat,
      gallery_image_ids: formGalleryImages,
    };
    try {
      if (editing) {
        await blogAdminApi.updatePost(editing.id, payload);
        await blogAdminApi.clearAutosave(editing.id).catch(() => {});
        toast({ title: "مقاله به‌روزرسانی شد" });
      } else {
        await blogAdminApi.createPost(payload);
        toast({ title: "مقاله جدید ایجاد شد" });
      }
      setEditorOpen(false);
      await loadPosts();
    } catch {
      toast({
        title: "ذخیره مقاله ناموفق بود",
        description: "نامک ممکن است تکراری باشد یا داده نامعتبر است.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  // Trash (soft delete)
  const handleTrash = async (post: BlogPost) => {
    if (!confirm(`مقاله «${post.title}» به سطل زباله منتقل شود؟`)) return;
    try {
      await blogAdminApi.deletePost(post.id);
      toast({ title: "مقاله به سطل زباله منتقل شد" });
      await loadPosts();
    } catch {
      toast({ title: "عملیات ناموفق بود", variant: "destructive" });
    }
  };

  // Bulk actions (wave 6 #72). The backend re-checks per-post ownership and
  // returns a per-post result, so the toast reports "17 of 20" rather than
  // claiming all 20 succeeded.
  const handleBulk = async (
    action: "publish" | "draft" | "archive" | "trash" | "restore",
    selected: BlogPost[],
  ): Promise<boolean> => {
    if (selected.length === 0) return false;
    try {
      const res = await blogAdminApi.bulkPosts(selected.map((p) => p.id), action);
      if (res.failed > 0) {
        toast({
          title: `${res.ok} مورد انجام شد، ${res.failed} مورد ناموفق`,
          description: "برخی نوشته‌ها مال شما نیستند یا در وضعیت مناسبی نبودند.",
          variant: "destructive",
        });
      } else {
        toast({ title: `${res.ok} مورد با موفقیت انجام شد` });
      }
      await loadPosts();
      return true;
    } catch (e) {
      toast({
        title: "عملیات گروهی ناموفق بود",
        description: e instanceof Error ? e.message : undefined,
        variant: "destructive",
      });
      return false;
    }
  };

  const activeBulkActions = isTrashTab
    ? [
        {
          id: "restore",
          label: "بازیابی",
          onRun: (rows: BlogPost[]) => handleBulk("restore", rows),
        },
        {
          id: "purge",
          label: "حذف کامل",
          variant: "destructive" as const,
          onRun: async (rows: BlogPost[]) => {
            if (
              !window.confirm(
                `${rows.length} نوشته برای همیشه حذف می‌شود. این عمل بازگشت‌پذیر نیست.`
              )
            )
              return false;
            for (const post of rows) {
              await blogAdminApi.hardDeletePost(post.id);
            }
            toast({ title: `${rows.length} نوشته حذف شد` });
            await loadPosts();
            return true;
          },
        },
      ]
    : [
        {
          id: "publish",
          label: "انتشار",
          onRun: (rows: BlogPost[]) => handleBulk("publish", rows),
        },
        {
          id: "draft",
          label: "بازگشت به پیش‌نویس",
          onRun: (rows: BlogPost[]) => handleBulk("draft", rows),
        },
        {
          id: "archive",
          label: "بایگانی",
          onRun: (rows: BlogPost[]) => handleBulk("archive", rows),
        },
        {
          id: "trash",
          label: "انتقال به سطل زباله",
          variant: "destructive" as const,
          confirm: (rows: BlogPost[]) =>
            `${rows.length} نوشته به سطل زباله منتقل شود؟ این عمل برگشت‌پذیر است.`,
          onRun: (rows: BlogPost[]) => handleBulk("trash", rows),
        },
        {
          // A field change, not a state change: it needs a form, so it opens
          // its own dialog. Returns false so the table does not clear the
          // selection before the server has answered.
          id: "edit",
          label: "ویرایش گروهی",
          onRun: (rows: BlogPost[]) => {
            setBulkEditRows(rows);
            setBulkEditOpen(true);
            return false;
          },
        },
      ];

  // Restore from trash
  const handleRestoreFromTrash = async (post: BlogPost) => {
    try {
      await blogAdminApi.restorePost(post.id);
      toast({ title: "مقاله بازیابی شد" });
      await loadPosts();
    } catch {
      toast({ title: "بازیابی ناموفق بود", variant: "destructive" });
    }
  };

  // Permanent Delete
  const handlePermanentDelete = async (post: BlogPost) => {
    if (!confirm(`آیا از حذف همیشگی «${post.title}» اطمینان دارید؟ این عمل قابل بازگشت نیست.`))
      return;
    try {
      await blogAdminApi.hardDeletePost(post.id);
      toast({ title: "مقاله برای همیشه پاک شد" });
      await loadPosts();
    } catch {
      toast({ title: "حذف دائمی ناموفق بود", variant: "destructive" });
    }
  };

  // Duplicate post
  const handleDuplicate = async (post: BlogPost) => {
    try {
      await blogAdminApi.duplicatePost(post.id);
      toast({ title: "نوشته با موفقیت تکثیر و کپی شد" });
      await loadPosts();
    } catch {
      toast({ title: "تکثیر نوشته ناموفق بود", variant: "destructive" });
    }
  };

  // Export JSON
  const handleExportJson = () => {
    const dataStr =
      "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(posts, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `blog-export-${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    toast({ title: "خروجی JSON مقالات آماده و دانلود شد" });
  };

  // Import JSON
  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const imported = JSON.parse(text);
      const items = Array.isArray(imported) ? imported : imported.posts || [];
      let count = 0;
      for (const item of items) {
        if (item.title && item.content) {
          await blogAdminApi.createPost({
            title: item.title,
            slug: item.slug,
            content: item.content,
            excerpt: item.excerpt,
            status: "draft",
          });
          count++;
        }
      }
      toast({ title: `${toPersianDigits(String(count))} مقاله با موفقیت درون‌ریزی شد` });
      await loadPosts();
    } catch {
      toast({ title: "خطا در خواندن یا درون‌ریزی فایل", variant: "destructive" });
    } finally {
      if (importFileRef.current) importFileRef.current.value = "";
    }
  };

  const openRevisions = async (post: BlogPost) => {
    setRevPost(post);
    setRevOpen(true);
    setRevLoading(true);
    try {
      setRevisions(await blogAdminApi.listRevisions(post.id));
    } catch {
      toast({ title: "دریافت تاریخچه نسخه‌ها ناموفق بود", variant: "destructive" });
      setRevisions([]);
    } finally {
      setRevLoading(false);
    }
  };

  const handleRestore = async (revisionNumber: number) => {
    if (!revPost) return;
    if (!confirm(`مقاله به نسخه ${toPersianDigits(String(revisionNumber))} بازگردانده شود؟`))
      return;
    setRestoring(revisionNumber);
    try {
      await blogAdminApi.restoreRevision(revPost.id, revisionNumber);
      toast({ title: "مقاله به نسخه قبلی بازگردانده شد" });
      setRevOpen(false);
      await loadPosts();
    } catch {
      toast({ title: "بازگردانی نسخه ناموفق بود", variant: "destructive" });
    } finally {
      setRestoring(null);
    }
  };

  const columns: DataTableColumn<BlogPost>[] = [
    {
      key: "title",
      header: "عنوان نوشته",
      sortValue: (p) => p.title,
      columnLabel: "عنوان",
      className: "font-medium text-foreground",
      render: (post) => (
        <div className="flex items-center gap-2">
          {post.is_featured && (
            <span title="نوشته ویژه">
              <Sparkles className="h-4 w-4 text-amber-500 shrink-0" />
            </span>
          )}
          {post.post_format === "gallery" && (
            <span title="گالری تصویر">
              <Images className="h-4 w-4 text-sky-500 shrink-0" />
            </span>
          )}
          {post.post_format === "video" && (
            <span title="ویدیو">
              <Video className="h-4 w-4 text-purple-500 shrink-0" />
            </span>
          )}
          {post.visibility === "password" && (
            <span title="رمزدار">
              <Lock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            </span>
          )}
          <span className="line-clamp-1 font-bold">{post.title}</span>
          {post.locale && post.locale !== "fa" && (
            <span className="rounded bg-muted px-1 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
              {post.locale}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "category",
      header: "دسته‌بندی",
      className: "text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (post) => post.category?.name ?? "—",
    },
    {
      key: "comments",
      header: "دیدگاه‌ها",
      className: "text-center text-xs",
      hideOnMobile: true,
      render: (post) => (
        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 font-medium">
          <MessageSquare className="h-3 w-3 text-muted-foreground" />
          {toPersianDigits(String(post.comment_count ?? 0))}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (post) => {
        if (isScheduled(post)) {
          return (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-sky-600">
              <CalendarClock className="h-3.5 w-3.5" /> زمان‌بندی شده
            </span>
          );
        }
        const meta = statusMeta[post.status];
        const Icon = post.status === "published" ? CheckCircle2 : Clock;
        return (
          <span className={`inline-flex items-center gap-1 text-xs font-medium ${meta.className}`}>
            <Icon className="h-3.5 w-3.5" /> {meta.label}
          </span>
        );
      },
    },
    {
      key: "views",
      header: "بازدید",
      sortValue: (p) => p.view_count ?? 0,
      columnLabel: "بازدید",
      className: "text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (post) => toPersianDigits(String(post.view_count ?? 0)),
    },
    {
      key: "updated",
      header: "تاریخ",
      sortValue: (p) => (p.updated_at ? new Date(p.updated_at).getTime() : null),
      columnLabel: "تاریخ",
      className: "text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (post) => toPersianDigits(new Date(post.updated_at).toLocaleDateString("fa-IR")),
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-center",
      render: (post) => {
        if (isTrashTab) {
          return (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1 text-xs text-emerald-600"
                onClick={() => handleRestoreFromTrash(post)}
              >
                <RotateCcw className="h-3.5 w-3.5" /> بازگردانی
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1 text-xs text-destructive hover:bg-destructive/10"
                onClick={() => handlePermanentDelete(post)}
              >
                <Trash2 className="h-3.5 w-3.5" /> حذف دائمی
              </Button>
            </div>
          );
        }

        return (
          <div className="flex items-center justify-center gap-1 flex-wrap">
            {post.status === "published" && (
              <Button variant="outline" size="sm" asChild className="h-7 px-2 text-xs">
                <Link href={`/blog/${post.slug}`} target="_blank" title="مشاهده در سایت">
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              </Button>
            )}
            {post.status !== "published" && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => setPreviewPostId(post.id)}
                title="پیش‌نمایش (بدون انتشار)"
              >
                <Eye className="h-3.5 w-3.5" />
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2.5 text-xs font-medium"
              onClick={() => openEdit(post)}
            >
              ویرایش
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-amber-600 hover:text-amber-700"
              onClick={() => {
                setQuickEditPost(post);
                setQuickEditOpen(true);
              }}
              title="ویرایش سریع"
            >
              <Zap className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => handleDuplicate(post)}
              title="تکثیر / کپی"
            >
              <Copy className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => openRevisions(post)}
              title="تاریخچه نسخه‌ها"
            >
              <History className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-destructive hover:bg-destructive/10"
              onClick={() => handleTrash(post)}
              title="انتقال به سطل زباله"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-black text-foreground">مدیریت وبلاگ و محتوا</h1>
          <p className="text-sm text-muted-foreground">
            مدیریت کامل مقالات، دیدگاه‌ها، تقویم تحریریه و قابلیت‌های پیشرفته CMS وردپرس
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <input
            type="file"
            ref={importFileRef}
            onChange={handleImportFile}
            accept=".json"
            className="hidden"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => importFileRef.current?.click()}
            className="gap-1.5 text-xs"
          >
            <Upload className="h-3.5 w-3.5" /> درون‌ریزی JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportJson}
            className="gap-1.5 text-xs"
          >
            <Download className="h-3.5 w-3.5" /> برون‌بری JSON
          </Button>
          <Button variant="outline" size="sm" onClick={() => void loadPosts()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={openCreate} className="gap-1.5 bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4" /> نوشته جدید
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="bg-card border border-border p-1">
          <TabsTrigger value="posts" className="gap-1.5 text-xs">
            <BookOpen className="h-4 w-4" /> همه نوشته‌ها
          </TabsTrigger>
          <TabsTrigger value="comments" className="gap-1.5 text-xs">
            <MessageSquare className="h-4 w-4" /> دیدگاه‌ها
          </TabsTrigger>
          <TabsTrigger value="calendar" className="gap-1.5 text-xs">
            <Calendar className="h-4 w-4" /> تقویم محتوا
          </TabsTrigger>
          <TabsTrigger value="review-queue" className="gap-1.5 text-xs">
            <ClipboardCheck className="h-4 w-4" /> صف بازبینی
          </TabsTrigger>
          <TabsTrigger value="taxonomy-manager" className="gap-1.5 text-xs">
            <FolderTree className="h-4 w-4" /> دسته و برچسب
          </TabsTrigger>
          <TabsTrigger value="taxonomies" className="gap-1.5 text-xs">
            <Tag className="h-4 w-4" /> تاکسونومی‌ها
          </TabsTrigger>
          <TabsTrigger value="content-types" className="gap-1.5 text-xs">
            <FileCode className="h-4 w-4" /> تایپ‌های محتوا
          </TabsTrigger>
          <TabsTrigger value="transfer" className="gap-1.5 text-xs">
            <Download className="h-4 w-4" /> ورود/خروج
          </TabsTrigger>
          <TabsTrigger value="trash" className="gap-1.5 text-xs">
            <Trash2 className="h-4 w-4 text-muted-foreground" /> زباله‌دان
          </TabsTrigger>
        </TabsList>

        {/* Posts Tab */}
        <TabsContent value="posts" className="space-y-4">
          <Card className="p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="relative flex-1">
                <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="جستجو در عنوان یا متن مقاله..."
                  className="ps-9"
                />
              </div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as BlogPostStatus | "all")}
                className="h-9 rounded-md border border-input bg-background px-3 text-xs"
              >
                <option value="all">همه وضعیت‌ها</option>
                <option value="draft">پیش‌نویس</option>
                <option value="pending_review">در انتظار بازبینی</option>
                <option value="published">منتشر شده</option>
                <option value="archived">بایگانی</option>
              </select>
              <select
                value={authorFilter}
                onChange={(e) => setAuthorFilter(e.target.value)}
                disabled={authors.length === 0}
                className="h-9 rounded-md border border-input bg-background px-3 text-xs disabled:opacity-60"
                aria-label={authorsTruncated ? "فیلتر نویسنده (فقط ۲۰۰۰ کاربر اول)" : "فیلتر نویسنده"}
              >
                <option value="">همه نویسندگان</option>
                {authors.map((u) => (
                  <option key={u.id} value={String(u.id)}>
                    {[u.first_name, u.last_name].filter(Boolean).join(" ").trim() || u.phone}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-1.5 whitespace-nowrap text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={featuredOnly}
                  onChange={(e) => setFeaturedOnly(e.target.checked)}
                  className="h-3.5 w-3.5"
                />
                فقط ویژه‌ها
              </label>
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span>از</span>
                <input
                  type="date"
                  value={dateFrom}
                  max={dateTo || undefined}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-2 text-xs"
                  aria-label="انتشار از تاریخ"
                />
                <span>تا</span>
                <input
                  type="date"
                  value={dateTo}
                  min={dateFrom || undefined}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-2 text-xs"
                  aria-label="انتشار تا تاریخ"
                />
              </div>
              {(authorFilter || dateFrom || dateTo || featuredOnly) && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-9 text-xs"
                  onClick={() => {
                    setAuthorFilter("");
                    setDateFrom("");
                    setDateTo("");
                    setFeaturedOnly(false);
                  }}
                >
                  حذف فیلترها
                </Button>
              )}
            </div>
          </Card>

          <DataTable<BlogPost>
            columns={columns}
            rows={posts}
            rowKey={(p) => p.id}
            emptyMessage={loading ? "در حال بارگذاری..." : "مقاله‌ای یافت نشد."}
            selectable
            bulkActions={activeBulkActions}
            pageSize={PAGE_SIZE}
            serverTotal={postsTotal}
            onServerPageChange={(p) => setPage(p)}
            defaultSort={{ key: "updated", dir: "desc" }}
            columnVisibilityKey="admin.blog.columns"
          />
        </TabsContent>

        {/* Comments Tab */}
        <TabsContent value="comments">
          <CommentsModerationTab />
        </TabsContent>

        {/* Calendar Tab */}
        <TabsContent value="calendar">
          <EditorialCalendarTab posts={posts} onSelectPost={openEdit} />
        </TabsContent>

        {/* Review queue: where a contributor's submission goes to be published
            or sent back. Without this tab a submitted post was unreachable. */}
        <TabsContent value="review-queue">
          <ReviewQueueTab onChanged={() => void loadPosts()} />
        </TabsContent>

        {/* Blog categories and tags: the ones posts are actually filed under */}
        <TabsContent value="taxonomy-manager">
          <TaxonomyManagerTab />
        </TabsContent>

        {/* Custom Taxonomies Tab */}
        <TabsContent value="taxonomies">
          <TaxonomiesTab />
        </TabsContent>

        {/* Custom Post Types Tab */}
        <TabsContent value="content-types">
          <ContentTypesTab />
        </TabsContent>

        {/* Import / Export Tab */}
        <TabsContent value="transfer">
          <TransferTab />
        </TabsContent>

        {/* Trash Tab */}
        <TabsContent value="trash" className="space-y-4">
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-4 text-xs text-amber-700 dark:text-amber-300">
            نوشته‌های موجود در سطل زباله پس از بررسی قابل بازگردانی هستند یا می‌توانید آن‌ها را برای همیشه پاک کنید.
          </div>
          <DataTable<BlogPost>
            columns={columns}
            rows={posts}
            rowKey={(p) => p.id}
            emptyMessage={loading ? "در حال بارگذاری..." : "سطل زباله خالی است."}
            selectable
            bulkActions={activeBulkActions}
            pageSize={PAGE_SIZE}
            serverTotal={postsTotal}
            onServerPageChange={(p) => setPage(p)}
            columnVisibilityKey="admin.blog.columns"
          />
        </TabsContent>
      </Tabs>

      {/* Quick Edit Dialog */}
      <QuickEditDialog
        post={quickEditPost}
        open={quickEditOpen}
        onOpenChange={setQuickEditOpen}
        categories={categories}
        tags={tags}
        onSaved={loadPosts}
      />

      <PostPreviewDialog
        postId={previewPostId}
        fallbackTitle={editing?.title}
        open={previewPostId !== null}
        onOpenChange={(open) => {
          if (!open) setPreviewPostId(null);
        }}
      />

      {/* Editor dialog */}
      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <DialogTitle>{editing ? "ویرایش مقاله" : "مقاله جدید"}</DialogTitle>
              {editing && (
                /* A published post's public URL really works, so keep the link
                   for those. For anything else it 404s, because the article
                   page reads the *public* endpoint — which by design does not
                   serve a draft. Those go to the admin preview, which is
                   access-checked and returns any status. */
                editing.status === "published" ? (
                  <Button variant="outline" size="sm" asChild className="gap-1 text-xs">
                    <Link href={`/blog/${editing.slug}`} target="_blank">
                      <Eye className="h-3.5 w-3.5" /> پیش‌نمایش در سایت
                    </Link>
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1 text-xs"
                    onClick={() => setPreviewPostId(editing.id)}
                  >
                    <Eye className="h-3.5 w-3.5" /> پیش‌نمایش
                  </Button>
                )
              )}
            </div>
            <DialogDescription>
              تنظیم مشخصات، محتوا، متاداده‌ها و گزینه‌های پیشرفته تحریریه
            </DialogDescription>
          </DialogHeader>

          {/* Lock Alert Banner */}
          {lockWarning && (
            <div className="flex items-center justify-between gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-700 dark:text-rose-300">
              <span className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {lockWarning}
              </span>
              {/* WordPress's take-over. The lock service had the override and
                  no route, so the only escape from a lock left behind by a
                  closed tab was the full editor. */}
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  void takeOver().then(() => setLockWarning(null));
                }}
              >
                تصاحب ویرایش
              </Button>
            </div>
          )}

          {/* Autosave Notice Banner */}
          {autosaveNotice?.has && (
            <div className="flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
              <span className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                یک نسخه ذخیره خودکار جدیدتر از این نوشته یافت شد.
              </span>
              <Button size="sm" variant="outline" onClick={handleRestoreAutosave} className="h-7 text-xs">
                بازیابی پیش‌نویس
              </Button>
            </div>
          )}

          <div className="space-y-5">
            {/* Title */}
            <div className="grid gap-2">
              <Label htmlFor="bp-title">عنوان مقاله</Label>
              <Input
                id="bp-title"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                placeholder="عنوان جذاب مقاله..."
                className="text-base font-bold"
              />
            </div>

            {/* Slug & Cover */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="bp-slug">نامک (Slug)</Label>
                <Input
                  id="bp-slug"
                  value={formSlug}
                  onChange={(e) => setFormSlug(e.target.value)}
                  placeholder="article-slug"
                  dir="ltr"
                  className="text-left font-mono text-xs"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="bp-cover">تصویر شاخص (Cover Image)</Label>
                <MediaPicker value={formCover} onChange={setFormCover} label="تصویر شاخص" />
              </div>
            </div>

            {/* Excerpt */}
            <div className="grid gap-2">
              <Label htmlFor="bp-excerpt">چکیده / خلاصه (Excerpt)</Label>
              <Textarea
                id="bp-excerpt"
                value={formExcerpt}
                onChange={(e) => setFormExcerpt(e.target.value)}
                rows={2}
                placeholder="خلاصه کوتاه برای پیش‌نمایش در لیست‌ها و شبکه‌های اجتماعی..."
              />
            </div>

            {/* Main Content Body */}
            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label>متن کامل مقاله</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setPatternPickerOpen(true)}
                >
                  <LayoutTemplate className="h-4 w-4 ms-1" />
                  درج الگوی بلوک
                </Button>
              </div>
              <RichBodyEditor value={formContent} onChange={setFormContent} />
            </div>

            {/* WordPress Settings Panel */}
            <div className="rounded-2xl border border-border bg-muted/30 p-5 space-y-4">
              <h4 className="font-bold text-sm text-foreground flex items-center gap-2">
                <Zap className="h-4 w-4 text-emerald-600" />
                تنظیمات انتشار و نگارش وردپرس
              </h4>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
                <div className="grid gap-1.5">
                  <Label htmlFor="bp-format">فرمت نوشته</Label>
                  <select
                    id="bp-format"
                    value={formFormat}
                    onChange={(e) => setFormFormat(e.target.value as PostFormat)}
                    className="h-9 rounded-md border border-input bg-background px-3 text-xs"
                  >
                    <option value="standard">استاندارد</option>
                    <option value="gallery">گالری تصاویر</option>
                    <option value="video">ویدیو</option>
                    <option value="audio">صوت / پادکست</option>
                    <option value="quote">نقل‌قول</option>
                    <option value="link">لینک</option>
                    <option value="status">وضعیت کوتاه</option>
                    <option value="image">تک تصویر</option>
                  </select>
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="bp-status">وضعیت نوشته</Label>
                  <select
                    id="bp-status"
                    value={formStatus}
                    onChange={(e) => setFormStatus(e.target.value as BlogPostStatus)}
                    className="h-9 rounded-md border border-input bg-background px-3 text-xs"
                  >
                    <option value="draft">پیش‌نویس</option>
                    <option value="published">منتشر شده</option>
                    <option value="archived">بایگانی</option>
                  </select>
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="bp-visibility">قابلیت مشاهده</Label>
                  <select
                    id="bp-visibility"
                    value={formVisibility}
                    onChange={(e) => setFormVisibility(e.target.value as PostVisibility)}
                    className="h-9 rounded-md border border-input bg-background px-3 text-xs"
                  >
                    <option value="public">عمومی</option>
                    <option value="private">خصوصی</option>
                    <option value="password">رمزدار</option>
                  </select>
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="bp-category">دسته‌بندی</Label>
                  <select
                    id="bp-category"
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    className="h-9 rounded-md border border-input bg-background px-3 text-xs"
                  >
                    <option value="">بدون دسته</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Password input if visibility is password */}
              {formVisibility === "password" && (
                <div className="grid gap-1.5 max-w-sm">
                  <Label htmlFor="bp-vis-pass">رمز عبور نوشته</Label>
                  <Input
                    id="bp-vis-pass"
                    value={formVisibilityPassword}
                    onChange={(e) => setFormVisibilityPassword(e.target.value)}
                    placeholder="رمز ورود جهت خواندن..."
                    dir="ltr"
                    className="text-left"
                  />
                </div>
              )}

              {/* Toggles */}
              <div className="flex flex-wrap items-center gap-6 pt-2">
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formFeatured}
                    onChange={(e) => setFormFeatured(e.target.checked)}
                    className="h-4 w-4 rounded border-input text-emerald-600 focus:ring-emerald-500"
                  />
                  <span className="flex items-center gap-1 text-xs font-medium">
                    <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                    سنجاق به بالای وبلاگ (نوشته ویژه)
                  </span>
                </label>

                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formAllowComments}
                    onChange={(e) => setFormAllowComments(e.target.checked)}
                    className="h-4 w-4 rounded border-input text-emerald-600 focus:ring-emerald-500"
                  />
                  <span className="flex items-center gap-1 text-xs font-medium">
                    <MessageSquare className="h-3.5 w-3.5 text-emerald-600" />
                    پذیرش دیدگاه‌ها برای این نوشته
                  </span>
                </label>
              </div>

              {/* Publication date and scheduled date are different fields on
                  purpose. `published_at` is when the post went (or should read
                  as having gone) live — it accepts a past date, which is how a
                  backdated import or a corrected date is entered. `scheduled_for`
                  is a future moment the beat task promotes; the server keeps
                  the post a draft until then. Overloading one field for both
                  meant the only way to record a real date was to publish now and
                  fix it afterwards. */}
              <div className="grid gap-1.5 max-w-sm pt-2">
                <Label htmlFor="bp-published">تاریخ انتشار</Label>
                <Input
                  id="bp-published"
                  type="datetime-local"
                  value={formPublished}
                  onChange={(e) => setFormPublished(e.target.value)}
                  dir="ltr"
                  className="text-left text-xs"
                />
                <p className="text-[11px] text-muted-foreground">
                  تاریخ واقعی انتشار. می‌توانید تاریخی در گذشته وارد کنید (مثلاً برای
                  مطالب بازimport‌شده یا اصلاح تاریخ).
                </p>
              </div>

              {/* Scheduled date */}
              <div className="grid gap-1.5 max-w-sm pt-2">
                <Label htmlFor="bp-scheduled">انتشار زمان‌بندی‌شده</Label>
                <Input
                  id="bp-scheduled"
                  type="datetime-local"
                  value={formScheduled}
                  onChange={(e) => setFormScheduled(e.target.value)}
                  dir="ltr"
                  className="text-left text-xs"
                />
              </div>
            </div>

            {/* Custom Fields / Post Meta (WordPress Post Meta Parity) */}
            {editing && (
              <div className="rounded-2xl border border-border bg-card p-5 space-y-3">
                <h4 className="font-bold text-sm text-foreground flex items-center gap-2">
                  <FileCode className="h-4 w-4 text-purple-600" />
                  زمینه‌های دلخواه (Post Meta / Custom Fields)
                </h4>

                <div className="space-y-2">
                  {metaLoading ? (
                    <p className="text-xs text-muted-foreground">در حال بارگذاری زمینه‌ها...</p>
                  ) : postMetas.length === 0 ? (
                    <p className="text-xs text-muted-foreground">هیچ زمینه دلخواهی ثبت نشده است.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {postMetas.map((m) => (
                        <div
                          key={m.id}
                          className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-1.5 text-xs font-mono"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-primary">{m.meta_key}:</span>
                            <span className="text-muted-foreground truncate max-w-xs">
                              {m.meta_value}
                            </span>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteMeta(m.meta_key)}
                            className="h-6 w-6 p-0 text-destructive"
                          >
                            ×
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Add New Meta Field */}
                  <div className="flex items-center gap-2 pt-2">
                    <Input
                      value={newMetaKey}
                      onChange={(e) => setNewMetaKey(e.target.value)}
                      placeholder="نام کلید (e.g. source_url)"
                      className="h-8 text-xs font-mono dir-ltr"
                    />
                    <Input
                      value={newMetaValue}
                      onChange={(e) => setNewMetaValue(e.target.value)}
                      placeholder="مقدار"
                      className="h-8 text-xs"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleAddMeta}
                      className="h-8 text-xs shrink-0"
                    >
                      افزودن کلید
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Tags */}
            {tags.length > 0 && (
              <div className="grid gap-2">
                <Label className="inline-flex items-center gap-1 text-xs">
                  <Tag className="h-3.5 w-3.5" /> برچسب‌ها
                </Label>
                <div className="flex flex-wrap gap-2">
                  {tags.map((t) => (
                    <button
                      type="button"
                      key={t.id}
                      onClick={() => toggleTag(t.id)}
                      className={`rounded-full border px-3 py-1 text-xs transition-all ${
                        formTagIds.includes(t.id)
                          ? "border-emerald-600 bg-emerald-600/10 font-bold text-emerald-600"
                          : "border-border bg-muted/50 text-muted-foreground hover:border-emerald-500/40"
                      }`}
                    >
                      #{t.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Custom taxonomies. The attach route and the typed client both
                existed with no caller, so a custom taxonomy could be filled
                with terms and never used. Mounted on its own save button
                because the endpoint replaces the post's whole term set. */}
            {editing && (
              <div className="grid gap-2">
                <Label className="inline-flex items-center gap-1 text-xs">
                  <FolderTree className="h-3.5 w-3.5" /> تاکسونومی‌های سفارشی
                </Label>
                <PostTermsPicker postId={editing.id} objectType="blog_post" />
              </div>
            )}
          </div>

          <DialogFooter className="flex items-center justify-between sm:justify-between">
            <div className="text-[11px] text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              ذخیره خودکار در پس‌زمینه فعال است
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setEditorOpen(false)}>
                انصراف
              </Button>
              {/* The contributor's way into the queue. Without it the status
                  was only reachable by a direct API call, which is what left
                  the review workflow with no visible entry point. Saving first
                  is deliberate: the submit endpoint works on a stored post. */}
              {editing && (
                <Button
                  variant="outline"
                  onClick={() => void submitForReview(editing.id)}
                  disabled={saving || submittingForReviewId === editing.id}
                >
                  {submittingForReviewId === editing.id
                    ? "در حال ارسال..."
                    : "ارسال برای بازبینی"}
                </Button>
              )}
              <Button
                onClick={handleSave}
                disabled={saving || !formTitle.trim() || !formContent.trim()}
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                {saving ? "در حال ذخیره..." : "ذخیره نوشته"}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* الگوهای بلوک: خروجی رندرشده به انتهای متن فعلی مقاله اضافه می‌شود. */}
      <BlockPatternPicker
        open={patternPickerOpen}
        onOpenChange={setPatternPickerOpen}
        onInsert={(html) =>
          setFormContent((prev) => (prev.trim() ? `${prev}\n\n${html}` : html))
        }
      />

      {/* Revision history dialog */}
      <Dialog open={revOpen} onOpenChange={setRevOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>تاریخچه نسخه‌ها — {revPost?.title}</DialogTitle>
            <DialogDescription>
              با بازگردانی، یک نسخه جدید از وضعیت بازگردانده‌شده ساخته می‌شود و هیچ نسخه‌ای پاک نمی‌شود.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[50vh] space-y-2 overflow-y-auto">
            {revLoading ? (
              <p className="py-6 text-center text-sm text-muted-foreground">در حال بارگذاری...</p>
            ) : revisions.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">نسخه‌ای ثبت نشده است.</p>
            ) : (
              revisions.map((rev) => (
                <div
                  key={rev.id}
                  className="flex items-center justify-between rounded-lg border border-border p-3"
                >
                  <div>
                    <p className="text-sm font-medium">
                      نسخه {toPersianDigits(String(rev.revision_number))} — {rev.title}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {toPersianDigits(new Date(rev.created_at).toLocaleString("fa-IR"))} · وضعیت: {rev.status}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs"
                      disabled={restoring !== null}
                      onClick={() => handleRestore(rev.revision_number)}
                    >
                      {restoring === rev.revision_number ? "در حال بازگردانی..." : "بازگردانی"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 px-2 text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => {
                        setComparePostId(revPost?.id ?? null);
                        setCompareOpen(true);
                      }}
                      title="مقایسه با نسخه‌های دیگر"
                    >
                      <GitCompare className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      <BulkEditDialog
        open={bulkEditOpen}
        onOpenChange={setBulkEditOpen}
        posts={bulkEditRows}
        categories={categories}
        tags={tags}
        onDone={loadPosts}
      />

      <RevisionCompareDialog
        postId={comparePostId}
        revisions={revisions}
        open={compareOpen}
        onOpenChange={setCompareOpen}
      />
    </div>
  );
}
