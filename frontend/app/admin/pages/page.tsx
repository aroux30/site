"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
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
} from "@/lib/api/content";
import { useAdminQuery } from "@/lib/api/admin-query";

const PAGES_QUERY_KEY = "admin-cms-pages" as const;

const statusLabels: Record<CmsPageStatus, { label: string; className: string }> = {
  published: { label: "منتشر شده", className: "text-emerald-600" },
  draft: { label: "پیش‌نویس", className: "text-amber-600" },
  archived: { label: "بایگانی", className: "text-muted-foreground" },
};

export default function AdminCMSPagesPage() {
  const { toast } = useToast();
  const [search, setSearch] = useState("");
  const [localeFilter, setLocaleFilter] = useState<string>("all");
  const [showTrashed, setShowTrashed] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  // create/edit dialog
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<CmsPage | null>(null);
  const [formTitle, setFormTitle] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formBody, setFormBody] = useState("");
  const [patternPickerOpen, setPatternPickerOpen] = useState(false);
  const [formStatus, setFormStatus] = useState<CmsPageStatus>("draft");
  const [formLocale, setFormLocale] = useState("fa");
  const [formExcerpt, setFormExcerpt] = useState("");
  const [formSeoTitle, setFormSeoTitle] = useState("");
  const [formSeoDescription, setFormSeoDescription] = useState("");
  const [formSchedPub, setFormSchedPub] = useState("");
  const [formSchedUnpub, setFormSchedUnpub] = useState("");
  const [saving, setSaving] = useState(false);

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

  const openCreate = () => {
    setEditing(null);
    setFormTitle("");
    setFormSlug("");
    setFormBody("");
    setFormStatus("draft");
    setFormLocale("fa");
    setFormExcerpt("");
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
    setFormExcerpt(page.excerpt ?? "");
    setFormSeoTitle(page.seo_title ?? "");
    setFormSeoDescription(page.seo_description ?? "");
    setFormSchedPub(page.scheduled_publish_at ? page.scheduled_publish_at.slice(0, 16) : "");
    setFormSchedUnpub(page.scheduled_unpublish_at ? page.scheduled_unpublish_at.slice(0, 16) : "");
    setEditorOpen(true);
  };

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
        excerpt: formExcerpt.trim() || null,
        seo_title: formSeoTitle.trim() || null,
        seo_description: formSeoDescription.trim() || null,
        scheduled_publish_at: formSchedPub ? new Date(formSchedPub).toISOString() : null,
        scheduled_unpublish_at: formSchedUnpub ? new Date(formSchedUnpub).toISOString() : null,
      };
      if (editing) {
        await cmsPagesAdminApi.updatePage(editing.id, payload);
        toast({ title: "صفحه به‌روزرسانی شد" });
      } else {
        await cmsPagesAdminApi.createPage(payload);
        toast({ title: "صفحه جدید ایجاد شد" });
      }
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
            <Button variant="outline" size="sm" asChild className="h-8 gap-1.5 text-xs">
              {/* Drafts 404 on the storefront; preview goes through the admin API. */}
              <Link
                href={`/api/v1/content/admin/pages/by-slug/${page.slug}`}
                target="_blank"
              >
                <ExternalLink className="h-3.5 w-3.5" /> پیش‌نمایش
              </Link>
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
      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
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
                className="text-left"
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
                <option value="published">منتشر شده</option>
                <option value="archived">بایگانی</option>
              </select>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
    </div>
  );
}
