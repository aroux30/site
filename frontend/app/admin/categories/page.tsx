"use client";

import React, { useState } from "react";
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
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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

const CATEGORIES_QUERY_KEY = "admin-categories" as const;

interface CategoryItem {
  id: string;
  name: string;
  slug: string;
  parent?: string;
  products_count: number;
  is_active: boolean;
}

export default function AdminCategoriesPage() {
  const [search, setSearch] = useState("");
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  // Karta categoryFields builder (Sprint 1.7)
  const [fieldsCategoryId, setFieldsCategoryId] = useState("");
  const [fieldDefs, setFieldDefs] = useState<Array<{ id: string; field_key: string; label: string; field_type: string; is_required: boolean }>>([]);
  const [fKey, setFKey] = useState("");
  const [fLabel, setFLabel] = useState("");
  const [fType, setFType] = useState("text");
  const [fRequired, setFRequired] = useState(false);
  const [fOptions, setFOptions] = useState("");
  const [fieldBuilderError, setFieldBuilderError] = useState<string | null>(null);

  // The list used to be seeded with seven hardcoded categories and the catch
  // block was empty — so a failed request rendered invented rows, complete
  // with fabricated product counts, and the operator could not tell. The
  // query now owns the list and a failure surfaces as an error instead.
  const {
    data,
    loading,
    error,
  } = useAdminQuery({
    queryKey: [CATEGORIES_QUERY_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/catalog/categories");
      return Array.isArray(res.data?.items) ? (res.data.items as CategoryItem[]) : [];
    },
    fallbackError: "دریافت فهرست دسته‌بندی‌ها ناموفق بود",
  });
  const categories: CategoryItem[] = data ?? [];
  const runMutation = useAdminMutation();

  const handleAddCategory = async () => {
    if (!newName.trim() || !newSlug.trim()) return;
    await runMutation(
      () =>
        apiClient.post("/catalog/categories", {
          name: newName.trim(),
          slug: newSlug.trim(),
        }),
      {
        fallbackError: "ایجاد دسته‌بندی ناموفق بود",
        invalidateKeys: [[CATEGORIES_QUERY_KEY]],
      },
    );
    setNewName("");
    setNewSlug("");
    setIsAddOpen(false);
  };

  const handleLoadFields = async (categoryId: string) => {
    setFieldsCategoryId(categoryId);
    if (!categoryId) return;
    try {
      const res = await apiClient.get(`/catalog/categories/${categoryId}/custom-fields`);
      setFieldDefs(Array.isArray(res.data) ? res.data : []);
    } catch {
      setFieldDefs([]);
    }
  };

  const handleCreateField = async () => {
    setFieldBuilderError(null);
    if (!fieldsCategoryId) {
      setFieldBuilderError("لطفاً یک دسته‌بندی را انتخاب کنید.");
      return;
    }
    const cleanKey = fKey.trim().toLowerCase();
    if (!cleanKey) {
      setFieldBuilderError("کلید فیلد الزامی است.");
      return;
    }
    if (!/^[a-z0-9_]+$/.test(cleanKey)) {
      setFieldBuilderError("کلید فیلد فقط می‌تواند شامل حروف انگلیسی، اعداد و زیرخط باشد.");
      return;
    }
    if (fieldDefs.some((f) => f.field_key.toLowerCase() === cleanKey)) {
      setFieldBuilderError(`کلید فیلد «${cleanKey}» برای این دسته‌بندی تکراری است.`);
      return;
    }
    const cleanLabel = fLabel.trim();
    if (!cleanLabel) {
      setFieldBuilderError("برچسب فیلد الزامی است.");
      return;
    }
    if (cleanLabel.length > 200) {
      setFieldBuilderError("برچسب فیلد نمی‌تواند بیشتر از ۲۰۰ کاراکتر باشد.");
      return;
    }
    const parsedOptions =
      fType === "select" && fOptions.trim()
        ? fOptions.split(",").map((o) => o.trim()).filter(Boolean)
        : null;
    if (fType === "select" && (!parsedOptions || parsedOptions.length === 0)) {
      setFieldBuilderError("برای فیلدهای انتخابی، حداقل یک گزینه با کاما الزامی است.");
      return;
    }

    try {
      await apiClient.post(`/catalog/categories/${fieldsCategoryId}/custom-fields`, {
        field_key: cleanKey,
        label: cleanLabel,
        field_type: fType,
        is_required: fRequired,
        options: parsedOptions,
      });
      setFKey("");
      setFLabel("");
      setFRequired(false);
      setFOptions("");
      setFieldBuilderError(null);
      handleLoadFields(fieldsCategoryId);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "خطا در ایجاد فیلد سفارشی. لطفاً ورودی‌ها را بررسی کنید.";
      setFieldBuilderError(msg);
    }
  };

  const handleDeleteField = async (fieldId: string) => {
    try {
      await apiClient.delete(`/catalog/custom-fields/${fieldId}`);
      handleLoadFields(fieldsCategoryId);
    } catch {
      // ignore
    }
  };

  const filteredCategories = categories.filter(
    (c) => c.name.includes(search) || c.slug.toLowerCase().includes(search.toLowerCase())
  );

  const categoryColumns: DataTableColumn<CategoryItem>[] = [
    {
      key: "name",
      header: "عنوان دسته",
      className: "font-medium text-foreground",
      render: (c) => (
        <div className="flex items-center gap-2">
          <FolderTree className="h-4 w-4 text-primary" />
          {c.name}
        </div>
      ),
    },
    {
      key: "slug",
      header: "نامک (Slug)",
      className: "font-mono text-xs text-muted-foreground",
      render: (c) => c.slug,
    },
    {
      key: "parent",
      header: "دسته والد",
      className: "text-sm text-muted-foreground",
      hideOnMobile: true,
      render: (c) => c.parent || "—",
    },
    {
      key: "count",
      header: "تعداد محصولات",
      className: "text-center",
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
      render: (c) => (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
          <CheckCircle2 className="h-3.5 w-3.5" /> فعال
        </span>
      ),
    },
    {
      key: "actions",
      header: <span className="sr-only">عملیات</span>,
      className: "text-center",
      render: (c) => (
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" aria-label={`ویرایش دسته ${c.name}`}>
          <Edit2 className="h-3.5 w-3.5" />
        </Button>
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

        <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="h-4 w-4" /> افزودن دسته‌بندی
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>ایجاد دسته‌بندی جدید</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">عنوان دسته‌بندی</label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="مثال: ساعت هوشمند"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">نامک انگلیسی (Slug)</label>
                <Input
                  value={newSlug}
                  onChange={(e) => setNewSlug(e.target.value)}
                  placeholder="مثال: smart-watches"
                  className="font-mono text-sm"
                />
              </div>
            </div>
            <DialogFooter className="gap-2 sm:justify-start">
              <Button onClick={handleAddCategory}>ثبت دسته‌بندی</Button>
              <Button variant="outline" onClick={() => setIsAddOpen(false)}>
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

      {/* Categories Table */}
      <DataTable<CategoryItem>
        columns={categoryColumns}
        rows={filteredCategories}
        rowKey={(c) => c.id}
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
        <select
          className="w-full max-w-xs rounded-lg border border-border bg-background px-3 py-2 text-sm"
          value={fieldsCategoryId}
          onChange={(e) => handleLoadFields(e.target.value)}
        >
          <option value="">دسته‌بندی را انتخاب کنید…</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        {fieldsCategoryId && (
          <div className="space-y-3">
            <div className="rounded-lg border border-border p-3 space-y-2">
              {fieldDefs.length === 0 ? (
                <p className="text-xs text-muted-foreground">برای این دسته فیلدی تعریف نشده است.</p>
              ) : (
                fieldDefs.map((f) => (
                  <div key={f.id} className="flex items-center justify-between text-xs">
                    <span className="font-mono" dir="ltr">
                      {f.field_key}
                    </span>
                    <span>{f.label}</span>
                    <Badge variant="outline">{f.field_type}</Badge>
                    {f.is_required && <Badge variant="secondary">اجباری</Badge>}
                    <Button size="sm" variant="ghost" onClick={() => handleDeleteField(f.id)}>
                      حذف
                    </Button>
                  </div>
                ))
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Input placeholder="کلید (player_id)" value={fKey} onChange={(e) => setFKey(e.target.value)} dir="ltr" />
              <Input placeholder="برچسب" value={fLabel} onChange={(e) => setFLabel(e.target.value)} />
              <select
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
                value={fType}
                onChange={(e) => setFType(e.target.value)}
              >
                <option value="text">متن</option>
                <option value="number">عدد</option>
                <option value="select">انتخابی</option>
              </select>
              <Input
                placeholder="گزینه‌ها با کاما (فقط انتخابی)"
                value={fOptions}
                onChange={(e) => setFOptions(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs">
                <input type="checkbox" checked={fRequired} onChange={(e) => setFRequired(e.target.checked)} />
                الزامی
              </label>
              <Button size="sm" onClick={handleCreateField}>
                <Plus className="h-4 w-4 ms-2" />
                افزودن فیلد
              </Button>
            </div>
            {fieldBuilderError && (
              <p className="text-xs font-medium text-red-500">{fieldBuilderError}</p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
