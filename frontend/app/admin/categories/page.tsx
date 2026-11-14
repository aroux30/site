"use client";

import React, { useState, useMemo } from "react";
import { RemoteImage } from "@/components/shared/remote-image";
import {
  Tag,
  Search,
  Plus,
  FolderTree,
  Edit2,
  Trash2,
  CheckCircle2,
  XCircle,
  Package,
  ImageIcon,
  ArrowUpDown,
  FileText,
  ExternalLink,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { CategoryFieldsBuilder } from "@/components/admin/category-fields-builder";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import type { BulkAction } from "@/components/admin/list-engine";
import { MediaPicker } from "@/components/admin/media-picker";
import { useToast } from "@/components/ui/use-toast";
import { useConfirm } from "@/components/ui/confirm-dialog";

const CATEGORIES_QUERY_KEY = "admin-categories" as const;

/** Persian labels for the custom-order-field types (API keys are English). */
const FIELD_TYPE_LABELS: Record<string, string> = {
  text: "متن",
  number: "عدد",
  select: "انتخابی",
};

interface CategoryItem {
  id: string;
  name: string;
  slug: string;
  parent_id?: string | null;
  parent_name?: string | null;
  parent?: string;
  description?: string | null;
  image_url?: string | null;
  path?: string | null;
  depth?: number;
  position?: number;
  is_active: boolean;
  seo_title?: string | null;
  seo_description?: string | null;
  products_count: number;
}

export default function AdminCategoriesPage() {
  const [search, setSearch] = useState("");
  const confirm = useConfirm();
  const { toast } = useToast();
  const runMutation = useAdminMutation();

  // Add Category Modal State
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newParentId, setNewParentId] = useState("");
  const [newImageUrl, setNewImageUrl] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newPosition, setNewPosition] = useState("0");
  const [newIsActive, setNewIsActive] = useState(true);
  const [newSeoTitle, setNewSeoTitle] = useState("");
  const [newSeoDescription, setNewSeoDescription] = useState("");

  // Edit Category Modal State
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<CategoryItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editSlug, setEditSlug] = useState("");
  const [editParentId, setEditParentId] = useState("");
  const [editImageUrl, setEditImageUrl] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editPosition, setEditPosition] = useState("0");
  const [editIsActive, setEditIsActive] = useState(true);
  const [editSeoTitle, setEditSeoTitle] = useState("");
  const [editSeoDescription, setEditSeoDescription] = useState("");

  // Karta categoryFields builder (Sprint 1.7)
  // کاتالوگ فیلدهای سفارشی دسته — فرم‌ساز کامل به CategoryFieldsBuilder منتقل شد
  const [fieldsCategoryId, setFieldsCategoryId] = useState("");

  // Fetch all categories
  const {
    data,
    loading,
    error,
    reload: reloadCategories,
  } = useAdminQuery({
    queryKey: [CATEGORIES_QUERY_KEY],
    queryFn: async () => {
      const PAGE = 1000;
      const all: CategoryItem[] = [];
      let page = 1;
      for (;;) {
        const res = await apiClient.get("/catalog/categories", {
          params: { page, page_size: PAGE },
        });
        const chunk = Array.isArray(res.data?.items) ? (res.data.items as CategoryItem[]) : [];
        all.push(...chunk);
        const meta = res.data?.meta ?? {};
        if (chunk.length === 0 || page >= (meta.total_pages ?? page)) break;
        page += 1;
      }
      return all;
    },
    fallbackError: "دریافت فهرست دسته‌بندی‌ها ناموفق بود",
  });
  const categories: CategoryItem[] = data ?? [];

  // Fast map to resolve parent names instantly
  const parentLookup = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of categories) {
      map.set(c.id, c.name);
    }
    return map;
  }, [categories]);

  // Hierarchical list for parent dropdowns with indentation
  const hierarchyOptions = useMemo(() => {
    // Sort root categories first, followed by child categories
    return [...categories].sort((a, b) => {
      const depthDiff = (a.depth || 0) - (b.depth || 0);
      if (depthDiff !== 0) return depthDiff;
      return (a.position || 0) - (b.position || 0);
    });
  }, [categories]);

  // Form submit: Add Category
  const handleAddCategory = async () => {
    if (!newName.trim()) {
      toast({
        title: "اطلاعات ناقص",
        description: "عنوان دسته‌بندی الزامی است.",
        variant: "destructive",
      });
      return;
    }

    const payload = {
      name: newName.trim(),
      slug: newSlug.trim() || undefined,
      parent_id: newParentId.trim() ? newParentId.trim() : null,
      image_url: newImageUrl.trim() ? newImageUrl.trim() : null,
      description: newDescription.trim() ? newDescription.trim() : null,
      position: parseInt(newPosition, 10) || 0,
      is_active: newIsActive,
      seo_title: newSeoTitle.trim() ? newSeoTitle.trim() : null,
      seo_description: newSeoDescription.trim() ? newSeoDescription.trim() : null,
    };

    const res = await runMutation(
      () => apiClient.post("/catalog/categories", payload),
      {
        fallbackError: "ایجاد دسته‌بندی ناموفق بود",
      },
    );

    if (res.ok) {
      toast({
        title: "دسته‌بندی ایجاد شد",
        description: `دسته‌بندی «${newName.trim()}» با موفقیت افزوده شد.`,
      });
      void reloadCategories();
      // Reset form
      setNewName("");
      setNewSlug("");
      setNewParentId("");
      setNewImageUrl("");
      setNewDescription("");
      setNewPosition("0");
      setNewIsActive(true);
      setNewSeoTitle("");
      setNewSeoDescription("");
      setIsAddOpen(false);
    } else {
      toast({
        title: "خطا در ایجاد دسته‌بندی",
        description: res.error,
        variant: "destructive",
      });
    }
  };

  // Open Edit Modal
  const handleOpenEdit = (c: CategoryItem) => {
    setEditingCategory(c);
    setEditName(c.name);
    setEditSlug(c.slug);
    setEditParentId(c.parent_id || "");
    setEditImageUrl(c.image_url || "");
    setEditDescription(c.description || "");
    setEditPosition(String(c.position ?? 0));
    setEditIsActive(c.is_active ?? true);
    setEditSeoTitle(c.seo_title || "");
    setEditSeoDescription(c.seo_description || "");
    setIsEditOpen(true);
  };

  // Form submit: Save Edit
  const handleSaveEdit = async () => {
    if (!editingCategory || !editName.trim()) return;

    if (editParentId && editParentId === editingCategory.id) {
      toast({
        title: "خطای والد",
        description: "یک دسته‌بندی نمی‌تواند والد خودش باشد.",
        variant: "destructive",
      });
      return;
    }

    const payload = {
      name: editName.trim(),
      slug: editSlug.trim() || undefined,
      parent_id: editParentId ? editParentId : null,
      image_url: editImageUrl.trim() ? editImageUrl.trim() : null,
      description: editDescription.trim() ? editDescription.trim() : null,
      position: parseInt(editPosition, 10) || 0,
      is_active: editIsActive,
      seo_title: editSeoTitle.trim() ? editSeoTitle.trim() : null,
      seo_description: editSeoDescription.trim() ? editSeoDescription.trim() : null,
    };

    const res = await runMutation(
      () => apiClient.patch(`/catalog/categories/${editingCategory.id}`, payload),
      {
        fallbackError: "ویرایش دسته‌بندی ناموفق بود",
      },
    );

    if (res.ok) {
      toast({
        title: "دسته‌بندی بروزرسانی شد",
        description: `اطلاعات «${editName.trim()}» ذخیره گردید.`,
      });
      void reloadCategories();
      setIsEditOpen(false);
      setEditingCategory(null);
    } else {
      toast({
        title: "خطا در ویرایش دسته‌بندی",
        description: res.error,
        variant: "destructive",
      });
    }
  };

  // Delete Category
  const handleDeleteCategory = async (c: CategoryItem) => {
    const ok = await confirm({
      title: "حذف دسته‌بندی",
      description: `آیا از حذف دسته‌بندی «${c.name}» اطمینان دارید؟ در صورت اتصال محصولات یا زیردسته‌ها، حذف انجام نخواهد شد.`,
      confirmLabel: "حذف دسته‌بندی",
      destructive: true,
    });
    if (!ok) return;

    const res = await runMutation(
      () => apiClient.delete(`/catalog/categories/${c.id}`),
      {
        fallbackError: "حذف دسته‌بندی ناموفق بود. ممکن است کالاهایی به آن متصل باشند.",
      },
    );
    if (res.ok) {
      toast({
        title: "دسته‌بندی حذف شد",
        description: `دسته‌بندی «${c.name}» با موفقیت حذف گردید.`,
      });
      void reloadCategories();
    } else {
      toast({
        title: "حذف دسته‌بندی انجام نشد",
        description: res.error,
        variant: "destructive",
      });
    }
  };

  // Bulk delete — same select-all/bulk bar UX as the orders and products
  // lists. There is no bulk endpoint for categories, so each row goes through
  // the same single-delete route (which refuses a category that still has
  // products or children); the per-row outcomes are summed for the toast.
  const categoryBulkActions: BulkAction<CategoryItem>[] = [
    {
      id: "delete",
      label: "حذف",
      variant: "destructive",
      confirm: (rows) =>
        `${toPersianDigits(String(rows.length))} دسته‌بندی حذف می‌شوند. دسته‌هایی که محصول یا زیردسته داشته باشند حذف نمی‌شوند. ادامه می‌دهید؟`,
      onRun: async (rows) => {
        const results = await Promise.allSettled(
          rows.map((c) => apiClient.delete(`/catalog/categories/${c.id}`)),
        );
        const okCount = results.filter((r) => r.status === "fulfilled").length;
        const failCount = results.length - okCount;
        if (failCount > 0) {
          toast({
            title: "حذف کامل نشد",
            description: `حذف‌شده: ${toPersianDigits(String(okCount))} — ناموفق: ${toPersianDigits(String(failCount))} (دسته دارای محصول یا زیردسته حذف نمی‌شود)`,
            variant: "destructive",
          });
        } else {
          toast({
            title: "دسته‌بندی‌ها حذف شدند",
            description: `${toPersianDigits(String(okCount))} دسته‌بندی`,
          });
        }
        void reloadCategories();
        return okCount > 0;
      },
    },
  ];

  // فیلدهای سفارشی دسته: کامپوننت CategoryFieldsBuilder خودش load/save/delete/update دارد.
  const handleLoadFields = (categoryId: string) => setFieldsCategoryId(categoryId);

  const filteredCategories = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return categories;
    return categories.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.slug.toLowerCase().includes(q) ||
        (c.parent_name && c.parent_name.toLowerCase().includes(q))
    );
  }, [categories, search]);

  const categoryColumns: DataTableColumn<CategoryItem>[] = [
    {
      key: "image",
      header: "تصویر",
      // باریک (۴۸px): در چیدمان ۵۰-۵۰ جدول نیمهٔ صفحه است؛ بندانگشت ۳۲px
      className: "w-12 px-1.5 sm:px-2 lg:px-2",
      render: (c) => (
        <div className="flex items-center justify-center">
          {c.image_url ? (
            <div className="relative h-8 w-8 overflow-hidden rounded-lg border border-border bg-muted/40">
              <RemoteImage
                src={c.image_url}
                alt={c.name}
                fill
                className="object-cover"
                sizes="32px"
              />
            </div>
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-muted/20 text-muted-foreground">
              <ImageIcon className="h-3.5 w-3.5" />
            </div>
          )}
        </div>
      ),
    },
    {
      // One compact cell carries name + slug + parent (the old layout burned
      // a full-width mono slug column and a redundant parent column — the
      // tree prefix already shows the hierarchy — making the table sprawl
      // sideways with 65px rows).
      // درصدی نه پیکسلی ثابت: در چیدمان دوستونه (جدول ~۶۴۰px) و تک‌ستونه
      // (جدول ~۱۰۹۰px) هر دو درست می‌نشیند و بقیهٔ ستون‌ها نفس دارند.
      // بدون عرض ثابت: زیر tableLayout="fixed" این ستون بقیهٔ عرض را بعد
      // از ستون‌های درصدی می‌گیرد — در ۵۰-۵۰ (~۱۹۰px) و تمام‌عرض (~۴۰۰px)
      // هر دو درست می‌نشیند.
      key: "name",
      header: "عنوان دسته",
      render: (c) => {
        const depth = c.depth || 0;
        const resolvedParent =
          c.parent_name ||
          (c.parent_id ? parentLookup.get(c.parent_id) : null) ||
          c.parent;
        return (
          <div style={{ paddingInlineStart: `${Math.min(depth * 18, 54)}px` }}>
            <div className="flex items-center justify-center gap-2">
              {depth > 0 ? (
                <span className="text-muted-foreground/60 text-xs font-mono">└─</span>
              ) : (
                <FolderTree className="h-4 w-4 text-primary shrink-0" />
              )}
              <span className="font-semibold text-foreground line-clamp-1" title={c.name}>
                {c.name}
              </span>
            </div>
            <div className="mt-0.5 flex flex-wrap items-center justify-center gap-x-1.5 gap-y-0.5 text-[11px] text-muted-foreground">
              <span className="font-mono" dir="ltr">
                {c.slug}
              </span>
              {resolvedParent && (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="line-clamp-1">والد: {resolvedParent}</span>
                </>
              )}
            </div>
          </div>
        );
      },
    },
    {
      key: "count",
      header: "محصولات",
      className: "w-[15%] px-1.5 sm:px-1.5 lg:px-1.5",
      render: (c) => (
        <Badge variant="secondary" className="gap-1">
          <Package className="h-3 w-3" />
          {toPersianDigits(c.products_count || 0)}
        </Badge>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      className: "w-[16%] px-1.5 sm:px-1.5 lg:px-1.5",
      render: (c) =>
        c.is_active !== false ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
            <CheckCircle2 className="h-3.5 w-3.5" /> فعال
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600">
            <XCircle className="h-3.5 w-3.5" /> غیرفعال
          </span>
        ),
    },
    {
      key: "actions",
      header: <span className="sr-only">عملیات</span>,
      columnLabel: "عملیات",
      className: "w-[21%] px-1.5 sm:px-1.5 lg:px-1.5",
      render: (c) => (
        <div className="flex items-center justify-center gap-0.5">
          {/* WordPress-parity «نمایش»: open the category's pretty storefront
              archive (/category/<slug>) in a new tab straight from the row. */}
          <Button
            asChild
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
            title={`نمایش دسته ${c.name} در فروشگاه`}
          >
            <a
              href={`/category/${encodeURIComponent(c.slug)}`}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`نمایش دسته ${c.name} در فروشگاه`}
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            title={`ویرایش دسته ${c.name}`}
            aria-label={`ویرایش دسته ${c.name}`}
            onClick={() => handleOpenEdit(c)}
          >
            <Edit2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-destructive hover:bg-destructive/10"
            title={`حذف دسته ${c.name}`}
            aria-label={`حذف دسته ${c.name}`}
            onClick={() => void handleDeleteCategory(c)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">دسته‌بندی‌های فروشگاه</h1>
          <p className="text-sm text-muted-foreground">
            سازماندهی ساختار درختی و دسته‌بندی محصولات
          </p>
        </div>

        {/* Add Category Modal */}
        <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="h-4 w-4" /> افزودن دسته‌بندی
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>ایجاد دسته‌بندی جدید</DialogTitle>
            </DialogHeader>
            <Tabs defaultValue="general" className="w-full pt-2">
              <TabsList className="grid grid-cols-3 mb-4">
                <TabsTrigger value="general">اطلاعات عمومی</TabsTrigger>
                <TabsTrigger value="image">تصویر شاخص</TabsTrigger>
                <TabsTrigger value="seo">بهینه‌سازی سئو</TabsTrigger>
              </TabsList>

              {/* Tab 1: General */}
              <TabsContent value="general" className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">عنوان دسته‌بندی *</Label>
                    <Input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder="مثال: ساعت هوشمند"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">نامک انگلیسی (Slug)</Label>
                    <Input
                      value={newSlug}
                      onChange={(e) => setNewSlug(e.target.value)}
                      placeholder="مثال: smart-watches"
                      className="font-mono text-sm"
                      dir="ltr"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">دسته‌بندی والد</Label>
                    {/* Radix items can't carry an empty value, so the root
                        option round-trips through the "__root__" sentinel. */}
                    <Select
                      value={newParentId || "__root__"}
                      onValueChange={(v) => setNewParentId(v === "__root__" ? "" : v)}
                    >
                      <SelectTrigger className="w-full" aria-label="دسته‌بندی والد">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__root__">بدون والد (دسته اصلی - ریشه)</SelectItem>
                        {hierarchyOptions.map((cat) => (
                          <SelectItem key={cat.id} value={cat.id}>
                            {(cat.depth || 0) > 0 ? "— ".repeat(cat.depth || 0) : ""}{cat.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">ترتیب نمایش (Position)</Label>
                    <Input
                      type="number"
                      value={newPosition}
                      onChange={(e) => setNewPosition(e.target.value)}
                      placeholder="0"
                      dir="ltr"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">توضیحات دسته‌بندی</Label>
                  <Textarea
                    value={newDescription}
                    onChange={(e) => setNewDescription(e.target.value)}
                    placeholder="شرح کوتاه درباره محصولات این دسته..."
                    rows={3}
                  />
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <Checkbox
                    id="newIsActiveCheck"
                    checked={newIsActive}
                    onCheckedChange={(v) => setNewIsActive(v === true)}
                  />
                  <Label htmlFor="newIsActiveCheck" className="text-sm cursor-pointer">
                    دسته‌بندی فعال باشد و در سایت نمایش داده شود
                  </Label>
                </div>
              </TabsContent>

              {/* Tab 2: Image */}
              <TabsContent value="image" className="space-y-4">
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    تصویر شاخص یا آیکون اختصاصی دسته‌بندی را از کتابخانه مدیا انتخاب یا آپلود نمایید.
                  </p>
                  <MediaPicker
                    value={newImageUrl}
                    onChange={(url) => setNewImageUrl(url)}
                    label="تصویر شاخص دسته‌بندی"
                  />
                  {newImageUrl && (
                    <div className="flex items-center gap-3 pt-2">
                      <div className="relative h-16 w-16 overflow-hidden rounded-lg border border-border">
                        <RemoteImage
                          src={newImageUrl}
                          alt="Category preview"
                          fill
                          className="object-cover"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setNewImageUrl("")}
                        className="text-xs text-destructive hover:bg-destructive/10"
                      >
                        حذف تصویر
                      </Button>
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* Tab 3: SEO */}
              <TabsContent value="seo" className="space-y-4">
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">عنوان سئو (SEO Title)</Label>
                  <Input
                    value={newSeoTitle}
                    onChange={(e) => setNewSeoTitle(e.target.value)}
                    placeholder="خرید انواع... با بهترین قیمت و ضمانت | نام برند"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">توضیحات متا (Meta Description)</Label>
                  <Textarea
                    value={newSeoDescription}
                    onChange={(e) => setNewSeoDescription(e.target.value)}
                    placeholder="متن خلاصه جهت نمایش در نتایج جستجوی گوگل (حداکثر ۱۶۰ کاراکتر)"
                    rows={3}
                  />
                </div>
              </TabsContent>
            </Tabs>

            <DialogFooter className="gap-2 sm:justify-start pt-4 border-t border-border mt-4">
              <Button onClick={handleAddCategory}>ثبت دسته‌بندی</Button>
              <Button variant="outline" onClick={() => setIsAddOpen(false)}>
                انصراف
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit Category Modal */}
        <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>ویرایش دسته‌بندی</DialogTitle>
            </DialogHeader>
            <Tabs defaultValue="general" className="w-full pt-2">
              <TabsList className="grid grid-cols-3 mb-4">
                <TabsTrigger value="general">اطلاعات عمومی</TabsTrigger>
                <TabsTrigger value="image">تصویر شاخص</TabsTrigger>
                <TabsTrigger value="seo">بهینه‌سازی سئو</TabsTrigger>
              </TabsList>

              {/* Tab 1: General */}
              <TabsContent value="general" className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">عنوان دسته‌بندی *</Label>
                    <Input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder="مثال: ساعت هوشمند"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">نامک انگلیسی (Slug)</Label>
                    <Input
                      value={editSlug}
                      onChange={(e) => setEditSlug(e.target.value)}
                      placeholder="مثال: smart-watches"
                      className="font-mono text-sm"
                      dir="ltr"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">دسته‌بندی والد</Label>
                    <Select
                      value={editParentId || "__root__"}
                      onValueChange={(v) => setEditParentId(v === "__root__" ? "" : v)}
                    >
                      <SelectTrigger className="w-full" aria-label="دسته‌بندی والد">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__root__">بدون والد (دسته اصلی - ریشه)</SelectItem>
                        {hierarchyOptions
                          .filter((cat) => cat.id !== editingCategory?.id)
                          .map((cat) => (
                            <SelectItem key={cat.id} value={cat.id}>
                              {(cat.depth || 0) > 0 ? "— ".repeat(cat.depth || 0) : ""}{cat.name}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium">ترتیب نمایش (Position)</Label>
                    <Input
                      type="number"
                      value={editPosition}
                      onChange={(e) => setEditPosition(e.target.value)}
                      placeholder="0"
                      dir="ltr"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">توضیحات دسته‌بندی</Label>
                  <Textarea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="شرح کوتاه درباره محصولات این دسته..."
                    rows={3}
                  />
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <Checkbox
                    id="editIsActiveCheck"
                    checked={editIsActive}
                    onCheckedChange={(v) => setEditIsActive(v === true)}
                  />
                  <Label htmlFor="editIsActiveCheck" className="text-sm cursor-pointer">
                    دسته‌بندی فعال باشد و در سایت نمایش داده شود
                  </Label>
                </div>
              </TabsContent>

              {/* Tab 2: Image */}
              <TabsContent value="image" className="space-y-4">
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    تصویر شاخص یا آیکون اختصاصی دسته‌بندی را از کتابخانه مدیا انتخاب یا آپلود نمایید.
                  </p>
                  <MediaPicker
                    value={editImageUrl}
                    onChange={(url) => setEditImageUrl(url)}
                    label="تصویر شاخص دسته‌بندی"
                  />
                  {editImageUrl && (
                    <div className="flex items-center gap-3 pt-2">
                      <div className="relative h-16 w-16 overflow-hidden rounded-lg border border-border">
                        <RemoteImage
                          src={editImageUrl}
                          alt="Category preview"
                          fill
                          className="object-cover"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setEditImageUrl("")}
                        className="text-xs text-destructive hover:bg-destructive/10"
                      >
                        حذف تصویر
                      </Button>
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* Tab 3: SEO */}
              <TabsContent value="seo" className="space-y-4">
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">عنوان سئو (SEO Title)</Label>
                  <Input
                    value={editSeoTitle}
                    onChange={(e) => setEditSeoTitle(e.target.value)}
                    placeholder="خرید انواع... با بهترین قیمت و ضمانت | نام برند"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">توضیحات متا (Meta Description)</Label>
                  <Textarea
                    value={editSeoDescription}
                    onChange={(e) => setEditSeoDescription(e.target.value)}
                    placeholder="متن خلاصه جهت نمایش در نتایج جستجوی گوگل"
                    rows={3}
                  />
                </div>
              </TabsContent>
            </Tabs>

            <DialogFooter className="gap-2 sm:justify-start pt-4 border-t border-border mt-4">
              <Button onClick={handleSaveEdit}>ذخیره تغییرات</Button>
              <Button variant="outline" onClick={() => setIsEditOpen(false)}>
                انصراف
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filter */}
      <Card className="p-4">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="جستجو در دسته‌ها..."
            className="ps-9"
          />
        </div>
      </Card>

      {/* Categories Table — تمام‌عرض؛ کارت فیلدهای سفارشی پایینِ آن می‌آید
          (چیدمان عمودی به انتخاب صریح مالک: «مثل گذشته بالا پایینی»). */}
      <DataTable<CategoryItem>
        columns={categoryColumns}
        rows={filteredCategories}
        rowKey={(c) => c.id}
        pageSize={50}
        columnVisibilityKey="admin.categories.columns"
        tableLayout="fixed"
        selectable
        bulkActions={categoryBulkActions}
        emptyMessage="دسته‌بندی یافت نشد."
      />

      {/* Karta categoryFields builder (Sprint 1.7) */}
      <Card className="p-4 space-y-4">
        <div>
          <h3 className="text-sm font-bold">فیلدهای سفارشی سفارش (فرم‌ساز داینامیک)</h3>
          <p className="text-xs text-muted-foreground mt-1">
            برای هر دسته‌بندی، فیلدهای اطلاعاتی خرید (مثل شناسه بازیکن، سرور، ریجن) را تعریف کنید؛
            در فرم ثبت سفارش نمایش و همراه فاکتور ذخیره می‌شوند.
          </p>
        </div>
        <div className="max-w-xs space-y-1.5">
          <Label className="text-xs font-medium">دسته‌بندی</Label>
          <Select
            // Radix Select shows the placeholder ONLY for an undefined
            // value: a controlled "__none__" with no matching item rendered
            // an EMPTY trigger (the reported «کادر تهی» bug).
            value={fieldsCategoryId || undefined}
            onValueChange={(v) => handleLoadFields(v)}
          >
            <SelectTrigger className="w-full" aria-label="انتخاب دسته‌بندی برای فیلدهای سفارشی">
              <SelectValue placeholder="دسته‌بندی را انتخاب کنید…" />
            </SelectTrigger>
            <SelectContent>
              {categories.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {fieldsCategoryId && (
          <CategoryFieldsBuilder categoryId={fieldsCategoryId} />
        )}
      </Card>
    </div>
  );
}
