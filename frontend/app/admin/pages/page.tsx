"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  usePageAutosave,
  usePageEditingLock,
} from "@/hooks/use-page-editing-lock";
import { QuickEditPageDialog } from "@/components/admin/pages/quick-edit-page-dialog";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  FileText,
  ExternalLink,
  CheckCircle2,
  Clock,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  RotateCcw,
  Copy,
  CheckSquare,
  Square,
  History,
  LayoutTemplate,
  Tag,
  Image as ImageIcon,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import RichBodyEditor from "@/components/admin/RichBodyEditor";
import { BlockPatternPicker } from "@/components/admin/block-pattern-picker";
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
import { toPersianDigits } from "@/lib/utils";
import {
  cmsPagesAdminApi,
  type CmsPage,
  type CmsPageRevision,
  type CmsPageStatus,
  type CmsPageVisibility,
} from "@/lib/api/content";
import { useAdminQuery } from "@/lib/api/admin-query";
import { CmsPreviewDialog } from "@/components/admin/cms-preview-dialog";
import { PostTermsPicker } from "@/components/admin/blog/post-terms-picker";
import { MediaPicker } from "@/components/admin/media-picker";

const PAGES_QUERY_KEY = "admin-cms-pages" as const;

const statusLabels: Record<CmsPageStatus, { label: string; className: string }> = {
  published: { label: "منتشر شده", className: "text-emerald-600" },
  draft: { label: "پیش‌نویس", className: "text-amber-600" },
  // Ready but not live. Added with the status; the Record is exhaustive, so
  // adding the value to the type surfaced every place that has to learn it.
  pending_review: { label: "در انتظار بازبینی", className: "text-sky-600" },
  archived: { label: "بایگانی", className: "text-muted-foreground" },
};

const visibilityLabels: Record<CmsPageVisibility, string> = {
  public: "عمومی",
  private: "خصوصی (فقط مدیران)",
  password: "رمزدار",
};

export default function AdminCMSPagesPage() {
  const { toast } = useToast();
  const [search, setSearch] = useState("");
  // `?search=` seeds the filter box. The admin bar's contextual "ویرایش برگه"
  // link lands here with the slug, so the operator sees the page they came from
  // instead of the whole library. Read once on mount: re-seeding on every render
  // would fight the operator's typing.
  const searchParam = useSearchParams()?.get("search");
  useEffect(() => {
    if (searchParam) setSearch(searchParam);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [localeFilter, setLocaleFilter] = useState<string>("all");
  const [showTrashed, setShowTrashed] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [previewPageId, setPreviewPageId] = useState<string | null>(null);  const [bulkBusy, setBulkBusy] = useState(false);

  // create/edit dialog
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<CmsPage | null>(null);
  const [formTitle, setFormTitle] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formBody, setFormBody] = useState("");
  const [patternPickerOpen, setPatternPickerOpen] = useState(false);
  const [formStatus, setFormStatus] = useState<CmsPageStatus>("draft");
  const [formLocale, setFormLocale] = useState("fa");
  // Page tree: which page is the parent, and where this one sits among its
  // siblings. The column, the schema and the server's cycle check all existed —
  // only the form was missing, so a page could never be nested.
  const [formPageId, setFormPageId] = useState("");
  const [formParentId, setFormParentId] = useState("");
  const [formMenuOrder, setFormMenuOrder] = useState("0");
  const [formExcerpt, setFormExcerpt] = useState("");
  // Hero image and who may read the page. Separate from the status: a
  // page can be published and still private.
  const [formCover, setFormCover] = useState("");
  const [formVisibility, setFormVisibility] = useState<CmsPageVisibility>("public");
  const [formVisibilityPassword, setFormVisibilityPassword] = useState("");
  const [formHasPassword, setFormHasPassword] = useState(false);
  // Live slug check. Debounced: one request per keystroke is both slow
  // and prone to the earlier response landing after a later one.
  const [slugCheck, setSlugCheck] = useState<{
    slug: string;
    available: boolean;
    reason: string | null;
  } | null>(null);
  const [formSeoTitle, setFormSeoTitle] = useState("");
  const [formSeoDescription, setFormSeoDescription] = useState("");
  const [formSchedPub, setFormSchedPub] = useState("");
  const [formSchedUnpub, setFormSchedUnpub] = useState("");
  // Opt a page into comments. Off by default server-side too, so an untouched
  // page never grows a thread.
  const [formAllowComments, setFormAllowComments] = useState(false);
  const [saving, setSaving] = useState(false);
  const [quickEditPage, setQuickEditPage] = useState<CmsPage | null>(null);
  const [quickEditOpen, setQuickEditOpen] = useState(false);

  // revision history dialog
  const [revOpen, setRevOpen] = useState(false);
  const [revPage, setRevPage] = useState<CmsPage | null>(null);
  const [revisions, setRevisions] = useState<CmsPageRevision[]>([]);
  const [revLoading, setRevLoading] = useState(false);
  const [restoring, setRestoring] = useState<number | null>(null);

  const {
    data: pagesData,
    loading,
    reload: fetchPages,
  } = useAdminQuery({
    queryKey: [PAGES_QUERY_KEY, search, localeFilter, showTrashed],
    queryFn: () => {
      const params: Parameters<typeof cmsPagesAdminApi.listPages>[0] = {};
      if (search) params.search = search;
      if (localeFilter !== "all") params.locale = localeFilter;
      if (showTrashed) params.include_trashed = true;
      return cmsPagesAdminApi.listPages(params);
    },
    fallbackError: "خطا در دریافت صفحات",
    toastOnError: true,
    toastDescription: "اتصال به سرویس محتوا برقرار نشد.",
  });
  const pages: CmsPage[] = pagesData?.items ?? [];

  // Selection is cleared whenever the page set changes — the old fetch did
  // `setSelected(new Set())` on every load, and a stale selection would let a
  // bulk action target rows the operator can no longer see.
  useEffect(() => {
    setSelected(new Set());
  }, [pagesData]);

  /** Live slug check while the editor is open.
   *
   * Debounced for two reasons, not one: a request per keystroke is slow, and
   * an earlier response can land after a later one and report "taken" for a
   * slug the field has already moved off. The response is ignored unless it is
   * still about the slug currently in the box.
   */
  useEffect(() => {
    const candidate = formSlug.trim();
    if (!candidate) {
      setSlugCheck(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await cmsPagesAdminApi.checkSlug(candidate, formPageId || undefined);
        if (candidate === formSlug.trim()) setSlugCheck(res);
      } catch {
        // A failed check must not block editing; the server still enforces it
        // on save, so the worst case is the error surfacing at submit.
        if (candidate === formSlug.trim()) setSlugCheck(null);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [formSlug, formPageId]);

  const openCreate = () => {
    setEditing(null);
    setFormTitle("");
    setFormSlug("");
    setFormBody("");
    setFormStatus("draft");
    setFormLocale("fa");
    setFormPageId("");
    setFormParentId("");
    setFormMenuOrder("0");
    setFormExcerpt("");
    setFormCover("");
    setFormVisibility("public");
    setFormVisibilityPassword("");
    setFormHasPassword(false);
    setFormSeoTitle("");
    setFormSeoDescription("");
    setFormSchedPub("");
    setFormSchedUnpub("");
    setEditorOpen(true);
  };

  const openEdit = (page: CmsPage) => {
    setEditing(page);
    setFormTitle(page.title);
    setFormSlug(page.slug);
    setFormBody(page.body_html);
    setFormStatus(page.status);
    setFormLocale(page.locale ?? "fa");
    setFormPageId(page.id);
    setFormParentId(page.parent_id ?? "");
    setFormMenuOrder(String(page.menu_order ?? 0));
    setFormExcerpt(page.excerpt ?? "");
    setFormCover(page.cover_image_url ?? "");
    setFormVisibility(page.visibility ?? "public");
    // The hash never comes back, so the field starts empty and a flag says
    // whether one is set. Without the flag the field looks unset on a
    // protected page and saving would submit "" and clear it.
    setFormVisibilityPassword("");
    setFormHasPassword(Boolean(page.visibility_password_set));
    setFormSeoTitle(page.seo_title ?? "");
    setFormSeoDescription(page.seo_description ?? "");
    setFormSchedPub(page.scheduled_publish_at ? page.scheduled_publish_at.slice(0, 16) : "");
    setFormSchedUnpub(page.scheduled_unpublish_at ? page.scheduled_unpublish_at.slice(0, 16) : "");
    setFormAllowComments(page.allow_comments ?? false);
    setEditorOpen(true);
  };

  // Editing lock and autosave for the open page. Both are no-ops while the
  // editor is closed or on a page that has never been saved, so this sits
  // after `openEdit` rather than being wired into it.
  const lockPageId = editorOpen && editing ? editing.id : null;
  const { lockedByOther, takeOver } = usePageEditingLock(lockPageId);

  const autosavePayload = useMemo(
    () => ({
      title: formTitle,
      body_html: formBody,
      excerpt: formExcerpt,
      slug: formSlug || undefined,
      status: formStatus,
    }),
    [formTitle, formBody, formExcerpt, formSlug, formStatus],
  );

  /* Derived, not tracked by hand.
   *
   * Marking a form dirty from thirteen `onChange` handlers means the thirteenth
   * one is the one somebody forgets, and the failure is "close the editor, lose
   * the text" — with no error anywhere. Comparing against what was loaded
   * cannot drift: the definition of dirty is the question being asked.
   */
  const savedFingerprint = editing
    ? JSON.stringify({
        title: editing.title,
        body_html: editing.body_html,
        excerpt: editing.excerpt ?? "",
        slug: editing.slug,
        status: editing.status,
      })
    : null;
  const formDirty =
    savedFingerprint !== null &&
    savedFingerprint !== JSON.stringify(autosavePayload);

  const { dirty: autosaveDirty, markClean } = usePageAutosave(
    lockPageId,
    autosavePayload,
  );

  const handleSave = async () => {
    if (!formTitle.trim()) return;
    setSaving(true);
    try {
      const payload = {
        title: formTitle,
        slug: formSlug || undefined,
        body_html: formBody,
        status: formStatus,
        locale: formLocale,
        // Empty string means "no parent"; the API takes null, not "".
        parent_id: formParentId || null,
        menu_order: Number.parseInt(formMenuOrder, 10) || 0,
        excerpt: formExcerpt.trim() || null,
        seo_title: formSeoTitle.trim() || null,
        seo_description: formSeoDescription.trim() || null,
        scheduled_publish_at: formSchedPub ? new Date(formSchedPub).toISOString() : null,
        allow_comments: formAllowComments,
        cover_image_url: formCover.trim() || null,
        visibility: formVisibility,
        // Only sent when typed: an untouched field must not clear a
        // password that is already set.
        ...(formVisibilityPassword.trim()
          ? { visibility_password: formVisibilityPassword }
          : {}),
        scheduled_unpublish_at: formSchedUnpub ? new Date(formSchedUnpub).toISOString() : null,
      };
      if (editing) {
        await cmsPagesAdminApi.updatePage(editing.id, payload);
        toast({ title: "صفحه به‌روزرسانی شد" });
      } else {
        await cmsPagesAdminApi.createPage(payload);
        toast({ title: "صفحه جدید ایجاد شد" });
      }
      // The autosave snapshot holds the same text and would be offered back on
      // the next open, which reads as "you have unsaved changes" after a
      // deliberate save.
      markClean();
      setEditorOpen(false);
      await fetchPages();
    } catch {
      toast({
        title: "ذخیره صفحه ناموفق بود",
        description: "نامک ممکن است تکراری یا رزرو شده باشد.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDuplicate = async (page: CmsPage) => {
    try {
      const copy = await cmsPagesAdminApi.duplicatePage(page.id);
      toast({ title: "صفحه کپی شد", description: `پیش‌نویس جدید: ${copy.title}` });
      await fetchPages();
    } catch {
      toast({ title: "کپی ناموفق بود", variant: "destructive" });
    }
  };

  const handleRestoreFromTrash = async (page: CmsPage) => {
    try {
      await cmsPagesAdminApi.restorePage(page.id);
      toast({ title: "صفحه از سطل زباله بازگردانده شد" });
      await fetchPages();
    } catch {
      toast({ title: "بازگردانی ناموفق بود", variant: "destructive" });
    }
  };

  const handlePermanentDelete = async (page: CmsPage) => {
    if (!confirm(`صفحه «${page.title}» برای همیشه حذف شود؟ دیگر قابل بازگشت نیست.`)) return;
    try {
      await cmsPagesAdminApi.permanentDeletePage(page.id);
      toast({ title: "صفحه برای همیشه حذف شد" });
      await fetchPages();
    } catch {
      toast({ title: "حذف دائم ناموفق بود — ابتدا به سطل زباله منتقل کنید", variant: "destructive" });
    }
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const runBulk = async (action: "publish" | "unpublish" | "trash" | "restore") => {
    if (selected.size === 0) return;
    const labels: Record<string, string> = {
      publish: "انتشار", unpublish: "برگشت به پیش‌نویس", trash: "انتقال به سطل زباله", restore: "بازگردانی",
    };
    if (!confirm(`${toPersianDigits(String(selected.size))} صفحه — ${labels[action]}؟`)) return;
    setBulkBusy(true);
    try {
      const result = await cmsPagesAdminApi.bulkAction(action, [...selected]);
      if (result.failed > 0) {
        toast({
          title: `انجام شد با خطا`,
          description: `موفق: ${toPersianDigits(String(result.succeeded))} — ناموفق: ${toPersianDigits(String(result.failed))}`,
          variant: "destructive",
        });
      } else {
        toast({ title: `${labels[action]} انجام شد`, description: `${toPersianDigits(String(result.succeeded))} صفحه` });
      }
      await fetchPages();
    } catch {
      toast({ title: "عملیات گروهی ناموفق بود", variant: "destructive" });
    } finally {
      setBulkBusy(false);
    }
  };

  const handleDelete = async (page: CmsPage) => {
    if (!confirm(`صفحه «${page.title}» حذف شود؟ این کار قابل بازگشت نیست.`)) return;
    try {
      await cmsPagesAdminApi.deletePage(page.id);
      toast({ title: "صفحه حذف شد" });
      await fetchPages();
    } catch {
      toast({ title: "حذف صفحه ناموفق بود", variant: "destructive" });
    }
  };

  const openRevisions = async (page: CmsPage) => {
    setRevPage(page);
    setRevOpen(true);
    setRevLoading(true);
    try {
      setRevisions(await cmsPagesAdminApi.listRevisions(page.id));
    } catch {
      toast({ title: "دریافت تاریخچه نسخه‌ها ناموفق بود", variant: "destructive" });
      setRevisions([]);
    } finally {
      setRevLoading(false);
    }
  };

  const handleRestore = async (revisionNumber: number) => {
    if (!revPage) return;
    if (!confirm(`صفحه به نسخه ${toPersianDigits(String(revisionNumber))} بازگردانده شود؟`))
      return;
    setRestoring(revisionNumber);
    try {
      await cmsPagesAdminApi.restoreRevision(revPage.id, revisionNumber);
      toast({ title: "صفحه به نسخه قبلی بازگردانده شد" });
      setRevOpen(false);
      await fetchPages();
    } catch {
      toast({ title: "بازگردانی نسخه ناموفق بود", variant: "destructive" });
    } finally {
      setRestoring(null);
    }
  };

  const pageColumns: DataTableColumn<CmsPage>[] = [
    {
      key: "select",
      header: "",
      render: (page) => (
        <button
          onClick={() => toggleSelect(page.id)}
          aria-label={selected.has(page.id) ? "برداشتن انتخاب" : "انتخاب"}
          className="text-muted-foreground hover:text-foreground"
        >
          {selected.has(page.id) ? (
            <CheckSquare className="h-4 w-4 text-primary" />
          ) : (
            <Square className="h-4 w-4" />
          )}
        </button>
      ),
    },
    {
      key: "title",
      header: "عنوان صفحه",
      className: "font-medium text-foreground",
      render: (page) => (
        <div className="flex items-center gap-2.5">
          <FileText className="h-4 w-4 text-primary" />
          {page.title}
          {page.deleted_at && (
            <span className="text-xs text-destructive">[در سطل زباله]</span>
          )}
          {page.scheduled_publish_at && page.status !== "published" && (
            <span className="text-xs text-muted-foreground">[زمان‌بندی شده]</span>
          )}
        </div>
      ),
    },
    {
      key: "locale",
      header: "زبان",
      className: "text-xs text-muted-foreground",
      render: (page) => page.locale ?? "fa",
    },
    {
      key: "slug",
      header: "نامک (Slug)",
      className: "font-mono text-xs text-muted-foreground",
      render: (page) => `/${page.slug}`,
    },
    {
      key: "status",
      header: "وضعیت انتشار",
      render: (page) => {
        const s = statusLabels[page.status];
        const Icon = page.status === "published" ? CheckCircle2 : Clock;
        return (
          <span
            className={`inline-flex items-center gap-1 text-xs font-medium ${s.className}`}
          >
            <Icon className="h-3.5 w-3.5" /> {s.label}
          </span>
        );
      },
    },
    {
      key: "revision",
      header: "نسخه",
      className: "text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (page) => (
        <span className="inline-flex items-center gap-1">
          <History className="h-3.5 w-3.5" /> {toPersianDigits(String(page.revision_number))}
        </span>
      ),
    },
    {
      key: "updated",
      header: "آخرین به‌روزرسانی",
      className: "text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (page) =>
        toPersianDigits(new Date(page.updated_at).toLocaleDateString("fa-IR")),
    },
    {
      key: "actions",
      header: "مشاهده و عملیات",
      className: "text-center",
      render: (page) => (
        <div className="flex items-center justify-center gap-2">
          {page.status === "published" ? (
            <Button variant="outline" size="sm" asChild className="h-8 gap-1.5 text-xs">
              <Link href={`/${page.slug}`} target="_blank">
                <ExternalLink className="h-3.5 w-3.5" /> مشاهده
              </Link>
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5 text-xs"
              onClick={() => setPreviewPageId(page.id)}
              title="پیش‌نمایش (بدون انتشار)"
            >
              <ExternalLink className="h-3.5 w-3.5" /> پیش‌نمایش
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => openEdit(page)}
          >
            ویرایش
          </Button>
          {/* WordPress's quick edit: fix a title or flip a page to draft
              without loading the whole editor for a two-second change. */}
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => {
              setQuickEditPage(page);
              setQuickEditOpen(true);
            }}
          >
            ویرایش سریع
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => openRevisions(page)}
          >
            <History className="h-3.5 w-3.5" /> تاریخچه
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => handleDuplicate(page)}
            title="تکثیر به‌صورت پیش‌نویس"
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
          {page.deleted_at ? (
            <>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1.5 text-xs"
                onClick={() => handleRestoreFromTrash(page)}
                title="بازگردانی از سطل زباله"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5 text-xs text-destructive"
                onClick={() => handlePermanentDelete(page)}
                title="حذف دائم"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 text-xs text-destructive"
              onClick={() => handleDelete(page)}
              title="انتقال به سطل زباله"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">مدیریت صفحات فروشگاه (CMS)</h1>
          <p className="text-sm text-muted-foreground">
            مشاهده، ویرایش و مدیریت صفحات اطلاع‌رسانی، شرایط و قوانین
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchPages}
            disabled={loading}
            aria-label="بروزرسانی"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={openCreate} className="gap-1.5">
            <Plus className="h-4 w-4" /> صفحه جدید
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <Card className="p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجو بر اساس عنوان یا آدرس صفحه..."
              className="ps-9"
            />
          </div>
          <select
            value={localeFilter}
            onChange={(e) => setLocaleFilter(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            aria-label="فیلتر زبان"
          >
            <option value="all">همه زبان‌ها</option>
            <option value="fa">فارسی</option>
            <option value="en">English</option>
            <option value="ar">العربية</option>
          </select>
          <Button
            variant={showTrashed ? "default" : "outline"}
            size="sm"
            className="h-9 gap-1.5"
            onClick={() => setShowTrashed((v) => !v)}
            title="نمایش/پنهان‌کردن صفحات سطل زباله"
          >
            <Trash2 className="h-4 w-4" />
            سطل زباله
          </Button>
        </div>
      </Card>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <Card className="p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {toPersianDigits(String(selected.size))} صفحه انتخاب شده:
            </span>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulk("publish")}>
              انتشار
            </Button>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulk("unpublish")}>
              پیش‌نویس
            </Button>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulk("trash")}>
              انتقال به سطل زباله
            </Button>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulk("restore")}>
              بازگردانی
            </Button>
            <Button size="sm" variant="ghost" disabled={bulkBusy} onClick={() => setSelected(new Set())}>
              لغو انتخاب
            </Button>
          </div>
        </Card>
      )}

      {/* Table */}
      <DataTable<CmsPage>
        columns={pageColumns}
        rows={pages}
        rowKey={(p) => p.id}
        emptyMessage={loading ? "در حال بارگذاری..." : "صفحه‌ای یافت نشد."}
      />

      {/* Create / Edit dialog */}
      <Dialog
        open={editorOpen}
        onOpenChange={(open) => {
          // Closing with unsaved work is the moment an autosave earns its keep —
          // and the moment a naive `setEditorOpen` throws away what the
          // operator just typed. Autosave has already persisted the text, so
          // the confirmation is about intent rather than about losing it.
          if (!open && formDirty) {
            const keep = window.confirm(
              "تغییرات ذخیره نشده‌اند. می‌خواهید ببندید؟ متن به‌صورت خودکار ذخیره شده و بعداً قابل بازیابی است.",
            );
            if (!keep) return;
          }
          setEditorOpen(open);
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "ویرایش صفحه" : "صفحه جدید"}</DialogTitle>
            <DialogDescription>
              {editing
                ? `نسخه فعلی: ${toPersianDigits(String(editing.revision_number))}`
                : "نامک در صورت خالی بودن از روی عنوان ساخته می‌شود."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Somebody else is editing. It does not stop typing — refusing a
                keystroke turns a collision into data loss for whoever got
                there second. It warns, and offers the take-over that the
                post editor has had all along. */}
            {lockedByOther && (
              <div className="flex items-center justify-between gap-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
                <span className="text-amber-800 dark:text-amber-300">
                  کاربر دیگری ({toPersianDigits(lockedByOther)}) در حال ویرایش این
                  صفحه است.
                </span>
                <Button size="sm" variant="outline" onClick={takeOver}>
                  تصاحب ویرایش
                </Button>
              </div>
            )}
            {/* Autosave state, always visible. A feature that runs silently is
                one nobody trusts — the question "did my last change go
                anywhere?" has to have an answer on screen. */}
            {editing && (
              <p className="text-[11px] text-muted-foreground">
                {autosaveDirty
                  ? "در حال ذخیره‌ی خودکار…"
                  : formDirty
                    ? "تغییرات ذخیره شده‌اند؛ برای انتشار «ذخیره» را بزنید."
                    : "ذخیره‌ی خودکار فعال است."}
              </p>
            )}
            <div className="grid gap-2">
              <Label htmlFor="page-title">عنوان</Label>
              <Input
                id="page-title"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                placeholder="مثلاً: درباره ما"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="page-slug">نامک (Slug)</Label>
              <Input
                id="page-slug"
                value={formSlug}
                onChange={(e) => setFormSlug(e.target.value)}
                placeholder="about-us"
                dir="ltr"
                aria-describedby="page-slug-status"
                className="text-left"
              />
              {/* Live feedback. The server still rejects on save — this only
                  means the operator finds out while typing instead of after a
                  round trip. */}
              {slugCheck && !slugCheck.available && (
                <p
                  id="page-slug-status"
                  className="text-[11px] text-destructive"
                  role="status"
                >
                  {slugCheck.reason === "reserved"
                    ? `«${slugCheck.slug}» نشانی رزروشده‌ی فروشگاه است و برگه نمی‌تواند آن را بگیرد.`
                    : `نامک «${slugCheck.slug}» قبلاً به برگه‌ی دیگری اختصاص دارد.`}
                </p>
              )}
              {slugCheck?.available && (
                <p
                  id="page-slug-status"
                  className="text-[11px] text-emerald-600"
                  role="status"
                >
                  این نامک آزاد است.
                </p>
              )}
            </div>
            {/* Hero image. A post had one and a page did not, so an "about us"
                or size guide had nowhere to put it. */}
            <div className="grid gap-2 sm:col-span-2">
              <Label className="inline-flex items-center gap-1 text-xs">
                <ImageIcon className="h-3.5 w-3.5" /> تصویر شاخص
              </Label>
              <MediaPicker
                value={formCover}
                onChange={setFormCover}
                label="تصویر شاخص برگه"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="page-excerpt">خلاصه (اختیاری)</Label>
              <Input
                id="page-excerpt"
                value={formExcerpt}
                onChange={(e) => setFormExcerpt(e.target.value)}
                placeholder="یک یا دو جمله برای معرفی صفحه"
              />
            </div>
            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label>متن صفحه</Label>
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
              <RichBodyEditor value={formBody} onChange={setFormBody} />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="page-seo-title">عنوان SEO (اختیاری)</Label>
                <Input
                  id="page-seo-title"
                  value={formSeoTitle}
                  onChange={(e) => setFormSeoTitle(e.target.value)}
                  placeholder="در صورت خالی بودن از عنوان صفحه استفاده می‌شود"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="page-seo-desc">توضیح SEO (اختیاری)</Label>
                <Input
                  id="page-seo-desc"
                  value={formSeoDescription}
                  onChange={(e) => setFormSeoDescription(e.target.value)}
                  placeholder="حداکثر ۵۰۰ کاراکتر برای نتایج جستجو"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="page-status">وضعیت</Label>
              <select
                id="page-status"
                value={formStatus}
                onChange={(e) => setFormStatus(e.target.value as CmsPageStatus)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="draft">پیش‌نویس</option>
                <option value="pending_review">در انتظار بازبینی</option>
                <option value="published">منتشر شده</option>
                <option value="archived">بایگانی</option>
              </select>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {/* Who may read the page. Separate from the status because a page
                  can be published *and* private, and one dropdown cannot say
                  both. */}
              <div className="grid gap-2">
                <Label htmlFor="page-visibility">قابلیت مشاهده</Label>
                <select
                  id="page-visibility"
                  value={formVisibility}
                  onChange={(e) =>
                    setFormVisibility(e.target.value as CmsPageVisibility)
                  }
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="public">عمومی</option>
                  <option value="private">خصوصی (فقط مدیران)</option>
                  <option value="password">رمزدار</option>
                </select>
              </div>
              {formVisibility === "password" && (
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="page-visibility-password">رمز عبور برگه</Label>
                  <Input
                    id="page-visibility-password"
                    type="text"
                    dir="ltr"
                    value={formVisibilityPassword}
                    onChange={(e) => setFormVisibilityPassword(e.target.value)}
                    placeholder={
                      formHasPassword
                        ? "رمز تنظیم شده — برای تغییر، رمز جدید وارد کنید"
                        : "رمز را وارد کنید"
                    }
                    className="text-left font-mono text-xs"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    {formHasPassword
                      ? "رمز فعلی به‌صورت هش‌شده ذخیره شده و قابل مشاهده نیست؛ خالی گذاشتن آن رمز را تغییر نمی‌دهد."
                      : "بدون رمز، برگه منتشر می‌شود ولی متنش نمایش داده نمی‌شود."}
                  </p>
                </div>
              )}
              <div className="grid gap-2">
                <Label htmlFor="page-locale">زبان</Label>
                <select
                  id="page-locale"
                  value={formLocale}
                  onChange={(e) => setFormLocale(e.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="fa">فارسی</option>
                  <option value="en">English</option>
                  <option value="ar">العربية</option>
                </select>
              </div>
              {/* A page could not carry a custom term at all before: the link
                  table's foreign key pointed at blog_posts. Only mounted for a
                  saved page, because there is no id to attach terms to yet. */}
              {formPageId && (
                <div className="grid gap-2 sm:col-span-2">
                  <Label className="inline-flex items-center gap-1 text-xs">
                    <Tag className="h-3.5 w-3.5" /> تاکسونومی‌های سفارشی
                  </Label>
                  <PostTermsPicker postId={formPageId} objectType="cms_page" />
                </div>
              )}
              <div className="grid gap-2">
                <Label htmlFor="page-parent">برگه‌ی والد</Label>
                <select
                  id="page-parent"
                  value={formParentId}
                  onChange={(e) => setFormParentId(e.target.value)}
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">بدون والد (صفحه‌ی سطح اول)</option>
                  {pages
                    // A page cannot be its own parent; the server rejects the
                    // cycle, but offering it here would just be a way to make a
                    // mistake and then read a validation error.
                    .filter((p) => p.id !== formPageId && p.status !== "archived")
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title}
                      </option>
                    ))}
                </select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="page-order">ترتیب میان هم‌والدین</Label>
                <Input
                  id="page-order"
                  type="number"
                  dir="ltr"
                  value={formMenuOrder}
                  onChange={(e) => setFormMenuOrder(e.target.value)}
                />
                <p className="text-[11px] text-muted-foreground">
                  عدد کوچک‌تر زودتر نمایش داده می‌شود.
                </p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="page-sched-pub">انتشار زمان‌بندی‌شده</Label>
                <Input
                  id="page-sched-pub"
                  type="datetime-local"
                  dir="ltr"
                  value={formSchedPub}
                  onChange={(e) => setFormSchedPub(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="page-sched-unpub">لغو انتشار زمان‌بندی‌شده</Label>
                <Input
                  id="page-sched-unpub"
                  type="datetime-local"
                  dir="ltr"
                  value={formSchedUnpub}
                  onChange={(e) => setFormSchedUnpub(e.target.value)}
                />
              </div>
            </div>
            <label className="flex cursor-pointer items-center gap-3 text-sm">
              <input
                type="checkbox"
                checked={formAllowComments}
                onChange={(e) => setFormAllowComments(e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              <span>امکان ارسال دیدگاه روی این صفحه</span>
            </label>
            {formAllowComments ? (
              <p className="-mt-2 text-xs text-muted-foreground">
                پس از انتشار، بخش دیدگاه‌ها در انتهای صفحه‌ی فروشگاه نمایش داده می‌شود. برای صفحات
                قانونی و سیاست‌ها این گزینه را خاموش نگه دارید.
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditorOpen(false)}>
              انصراف
            </Button>
            <Button onClick={handleSave} disabled={saving || !formTitle.trim()}>
              {saving ? "در حال ذخیره..." : "ذخیره"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* الگوهای بلوک: خروجی رندرشده به انتهای متن فعلی صفحه اضافه می‌شود. */}
      <BlockPatternPicker
        open={patternPickerOpen}
        onOpenChange={setPatternPickerOpen}
        onInsert={(html) =>
          setFormBody((prev) => (prev.trim() ? `${prev}\n\n${html}` : html))
        }
      />

      {/* Revision history dialog */}
      <QuickEditPageDialog
        page={quickEditPage}
        open={quickEditOpen}
        onOpenChange={setQuickEditOpen}
        onSaved={fetchPages}
      />

      <Dialog open={revOpen} onOpenChange={setRevOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>تاریخچه نسخه‌ها — {revPage?.title}</DialogTitle>
            <DialogDescription>
              نسخه فعلی:{" "}
              {revPage ? toPersianDigits(String(revPage.revision_number)) : "—"} — با
              بازگردانی، یک نسخه جدید از وضعیت بازگردانده‌شده ساخته می‌شود و هیچ نسخه‌ای
              پاک نمی‌شود.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[50vh] space-y-2 overflow-y-auto">
            {revLoading ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                در حال بارگذاری...
              </p>
            ) : revisions.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                نسخه‌ای ثبت نشده است.
              </p>
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
                      {toPersianDigits(
                        new Date(rev.created_at).toLocaleString("fa-IR"),
                      )}{" "}
                      · وضعیت: {rev.status}
                    </p>
                  </div>
                  {rev.revision_number !== revPage?.revision_number && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs"
                      disabled={restoring !== null}
                      onClick={() => handleRestore(rev.revision_number)}
                    >
                      {restoring === rev.revision_number
                        ? "در حال بازگردانی..."
                        : "بازگردانی"}
                    </Button>
                  )}
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      <CmsPreviewDialog
        pageId={previewPageId}
        open={previewPageId !== null}
        onOpenChange={(open) => {
          if (!open) setPreviewPageId(null);
        }}
      />
    </div>
  );
}
