"use client";

import React, { useState, useEffect } from "react";
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

interface CategoryItem {
  id: string;
  name: string;
  slug: string;
  parent?: string;
  products_count: number;
  is_active: boolean;
}

const initialCategories: CategoryItem[] = [
  { id: "c-1", name: "کالای دیجیتال", slug: "digital-goods", products_count: 14, is_active: true },
  { id: "c-2", name: "موبایل و تبلت", slug: "phones-tablets", parent: "کالای دیجیتال", products_count: 8, is_active: true },
  { id: "c-3", name: "لپ‌تاپ و تجهیزات کامپیوتر", slug: "laptops", parent: "کالای دیجیتال", products_count: 6, is_active: true },
  { id: "c-4", name: "مد و پوشاک", slug: "apparel", products_count: 5, is_active: true },
  { id: "c-5", name: "خانه و آشپزخانه", slug: "home-kitchen", products_count: 7, is_active: true },
  { id: "c-6", name: "زیبایی و سلامت", slug: "beauty", products_count: 3, is_active: true },
  { id: "c-7", name: "کتاب و لوازم‌التحریر", slug: "books", products_count: 2, is_active: true },
];

export default function AdminCategoriesPage() {
  const [categories, setCategories] = useState<CategoryItem[]>(initialCategories);
  const [search, setSearch] = useState("");
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");

  useEffect(() => {
    async function loadCategories() {
      try {
        const res = await apiClient.get("/catalog/categories");
        if (res.data && Array.isArray(res.data.items)) {
          setCategories(res.data.items);
        }
      } catch (err) {
        // Fallback to initial local categories
      }
    }
    loadCategories();
  }, []);

  const handleAddCategory = () => {
    if (!newName.trim() || !newSlug.trim()) return;
    const newCat: CategoryItem = {
      id: `c-${Date.now()}`,
      name: newName.trim(),
      slug: newSlug.trim(),
      products_count: 0,
      is_active: true,
    };
    setCategories([newCat, ...categories]);
    setNewName("");
    setNewSlug("");
    setIsAddOpen(false);
  };

  const filteredCategories = categories.filter(
    (c) => c.name.includes(search) || c.slug.toLowerCase().includes(search.toLowerCase())
  );

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
            className="pr-9"
          />
        </div>
      </Card>

      {/* Categories Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3">عنوان دسته</th>
                <th className="px-4 py-3">نامک (Slug)</th>
                <th className="px-4 py-3">دسته والد</th>
                <th className="px-4 py-3 text-center">تعداد محصولات</th>
                <th className="px-4 py-3">وضعیت</th>
                <th className="px-4 py-3 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredCategories.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted-foreground">
                    دسته‌بندی یافت نشد.
                  </td>
                </tr>
              ) : (
                filteredCategories.map((c) => (
                  <tr key={c.id} className="transition-colors hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium text-foreground">
                      <div className="flex items-center gap-2">
                        <FolderTree className="h-4 w-4 text-primary" />
                        {c.name}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                      {c.slug}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {c.parent || "—"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Badge variant="secondary" className="gap-1">
                        <Package className="h-3 w-3" />
                        {toPersianDigits(c.products_count || 0)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
                        <CheckCircle2 className="h-3.5 w-3.5" /> فعال
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                        <Edit2 className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
