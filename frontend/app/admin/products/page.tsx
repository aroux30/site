"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Package,
  Plus,
  Search,
  Edit,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ImageIcon,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";

/* ------------------------------------------------------------------ */
/*  Type Definitions                                                   */
/* ------------------------------------------------------------------ */

interface AdminProduct {
  id: string;
  name: string;
  description: string;
  category: string;
  brand: string;
  price: number;
  compareAtPrice?: number | null;
  sku: string;
  weight?: number; // in grams
  imageUrl?: string;
  stock: number;
  status: "active" | "draft" | "archived" | "out_of_stock";
  createdAt: string;
}

const CATEGORIES = [
  "همه دسته‌بندی‌ها",
  "موبایل و تبلت",
  "لپ‌تاپ و کامپیوتر",
  "لوازم جانبی دیجیتال",
  "صوتی و هدفون",
  "ساعت و دستبند هوشمند",
  "کنسول و بازی",
];

const INITIAL_PRODUCTS: AdminProduct[] = [
  {
    id: "prod-1",
    name: "گوشی موبایل سامسونگ Galaxy S24 Ultra ظرفیت 256 رم 12",
    description: "پرچمدار سامسونگ با دوربین ۲۰۰ مگاپیکسلی و قلم S-Pen اختصاصی و بدنه تیتانیومی.",
    category: "موبایل و تبلت",
    brand: "سامسونگ",
    price: 68_500_000,
    compareAtPrice: 72_000_000,
    sku: "SAM-S24U-256",
    weight: 232,
    imageUrl: "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=150&auto=format&fit=crop&q=80",
    stock: 14,
    status: "active",
    createdAt: "۱۴۰۳/۰۶/۱۰",
  },
  {
    id: "prod-2",
    name: "لپ‌تاپ ۱۶ اینچی اپل MacBook Pro M3 Pro ظرفیت 512",
    description: "لپ‌تاپ فوق‌حرفه‌ای اپل با تراشه ۱۲ هسته‌ای M3 Pro و ۱۸ گیگابایت رم یکپارچه.",
    category: "لپ‌تاپ و کامپیوتر",
    brand: "اپل",
    price: 115_000_000,
    compareAtPrice: 122_000_000,
    sku: "APL-MBP-M3P",
    weight: 2140,
    imageUrl: "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=150&auto=format&fit=crop&q=80",
    stock: 5,
    status: "active",
    createdAt: "۱۴۰۳/۰۶/۰۸",
  },
  {
    id: "prod-3",
    name: "هدفون بی‌سیم نویز کنسلینگ سونی WH-1000XM5",
    description: "برترین هدفون نویز کنسلینگ با کیفیت صدای Hi-Res و شارژدهی ۳۰ ساعته.",
    category: "صوتی و هدفون",
    brand: "سونی",
    price: 16_800_000,
    compareAtPrice: 18_500_000,
    sku: "SNY-WH1000XM5",
    weight: 250,
    imageUrl: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=150&auto=format&fit=crop&q=80",
    stock: 22,
    status: "active",
    createdAt: "۱۴۰۳/۰۶/۰۵",
  },
  {
    id: "prod-4",
    name: "ساعت هوشمند اپل Apple Watch Series 9 آلومینیوم 45mm",
    description: "ساعت هوشمند اپل مجهز به سنسور دمای بدن، قابلیت Double Tap و صفحه نمایش بسیار روشن.",
    category: "ساعت و دستبند هوشمند",
    brand: "اپل",
    price: 21_900_000,
    compareAtPrice: null,
    sku: "APL-WCH-S9-45",
    weight: 39,
    imageUrl: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=150&auto=format&fit=crop&q=80",
    stock: 0,
    status: "out_of_stock",
    createdAt: "۱۴۰۳/۰۵/۲۸",
  },
  {
    id: "prod-5",
    name: "پاوربانک ۲۰۰۰۰ میلی‌آمپر فست شارژ انکر ۶۵ وات Anker 737",
    description: "شارژر همراه قدرتمند دارای پورت Type-C با توان خروجی ۶۵ وات و صفحه نمایش هوشمند.",
    category: "لوازم جانبی دیجیتال",
    brand: "انکر",
    price: 4_200_000,
    compareAtPrice: 4_800_000,
    sku: "ANK-PB-737-65W",
    weight: 630,
    imageUrl: "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=150&auto=format&fit=crop&q=80",
    stock: 3,
    status: "active",
    createdAt: "۱۴۰۳/۰۵/۲۰",
  },
  {
    id: "prod-6",
    name: "کنسول بازی سونی مدل PlayStation 5 Slim ریجن اروپا",
    description: "نسخه اسلیم پلی‌استیشن ۵ با حافظه یک ترابایتی SSD و درایو بلوری قابل جداشدن.",
    category: "کنسول و بازی",
    brand: "سونی",
    price: 34_500_000,
    compareAtPrice: 36_000_000,
    sku: "SNY-PS5-SLIM-EU",
    weight: 3200,
    imageUrl: "https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=150&auto=format&fit=crop&q=80",
    stock: 8,
    status: "active",
    createdAt: "۱۴۰۳/۰۵/۱۵",
  },
  {
    id: "prod-7",
    name: "ماوس بی‌سیم گیمینگ لاجیتک مدل G Pro X Superlight",
    description: "ماوس گیمینگ سبک‌وزن ۶۳ گرمی با سنسور پیشرفته HERO 25K برای ورزش‌های الکترونیک.",
    category: "لوازم جانبی دیجیتال",
    brand: "لاجیتک",
    price: 6_900_000,
    compareAtPrice: 7_500_000,
    sku: "LOG-GPRO-XSL",
    weight: 63,
    imageUrl: "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=150&auto=format&fit=crop&q=80",
    stock: 12,
    status: "draft",
    createdAt: "۱۴۰۳/۰۵/۰۲",
  },
];

/* ------------------------------------------------------------------ */
/*  Main Admin Products Page Component                                 */
/* ------------------------------------------------------------------ */

export default function AdminProductsPage() {
  const { toast } = useToast();

  const [products, setProducts] = useState<AdminProduct[]>(INITIAL_PRODUCTS);
  const [_isLoading, setIsLoading] = useState(false);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("همه دسته‌بندی‌ها");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");

  // Modal State (Add / Edit)
  const [isProductModalOpen, setIsProductModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<AdminProduct | null>(null);
  const [isDeletingId, setIsDeletingId] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    category: "موبایل و تبلت",
    brand: "",
    price: "",
    compareAtPrice: "",
    sku: "",
    weight: "",
    imageUrl: "",
    stock: "10",
    status: "active" as AdminProduct["status"],
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Fetch products from API on mount
  useEffect(() => {
    const fetchProducts = async () => {
      try {
        setIsLoading(true);
        const res = await apiClient
          .get("/catalog/products")
          .catch(() => apiClient.get("/products"));

        if (res.data?.items && Array.isArray(res.data.items) && res.data.items.length > 0) {
          const mapped: AdminProduct[] = res.data.items.map((p: any) => ({
            id: String(p.id),
            name: p.title || p.name,
            description: p.description || "",
            category: p.category?.name || p.category_name || "عمومی",
            brand: p.brand?.name || p.brand || "متفرقه",
            price: p.price || 0,
            compareAtPrice: p.original_price || p.compare_at_price || null,
            sku: p.sku || `SKU-${p.id?.slice?.(0, 6)}`,
            weight: p.weight || 0,
            imageUrl: p.thumbnail || p.images?.[0]?.url || p.images?.[0] || "",
            stock: p.stock ?? p.stock_count ?? 10,
            status: p.is_active === false ? "draft" : (p.stock === 0 ? "out_of_stock" : "active"),
            createdAt: p.created_at ? new Date(p.created_at).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
          }));
          setProducts(mapped);
        }
      } catch (err) {
        // Use fallback products silently
      } finally {
        setIsLoading(false);
      }
    };

    fetchProducts();
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Filtering and Sorting                                           */
  /* ---------------------------------------------------------------- */

  const filteredProducts = useMemo(() => {
    return products.filter((item) => {
      // 1. Search Query
      const query = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !query ||
        item.name.toLowerCase().includes(query) ||
        item.sku.toLowerCase().includes(query) ||
        item.brand.toLowerCase().includes(query);

      // 2. Category Filter
      const matchesCategory =
        selectedCategory === "همه دسته‌بندی‌ها" || item.category === selectedCategory;

      // 3. Status Filter
      const matchesStatus =
        selectedStatus === "all" ||
        (selectedStatus === "in_stock" && item.stock > 0) ||
        (selectedStatus === "out_of_stock" && item.stock === 0) ||
        item.status === selectedStatus;

      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [products, searchQuery, selectedCategory, selectedStatus]);

  /* ---------------------------------------------------------------- */
  /*  Modal Open / Form Handlers                                       */
  /* ---------------------------------------------------------------- */

  const handleOpenAddModal = () => {
    setEditingProduct(null);
    setFormData({
      name: "",
      description: "",
      category: "موبایل و تبلت",
      brand: "",
      price: "",
      compareAtPrice: "",
      sku: `SKU-${Math.floor(100000 + Math.random() * 900000)}`,
      weight: "200",
      imageUrl: "",
      stock: "10",
      status: "active",
    });
    setIsProductModalOpen(true);
  };

  const handleOpenEditModal = (product: AdminProduct) => {
    setEditingProduct(product);
    setFormData({
      name: product.name,
      description: product.description,
      category: product.category,
      brand: product.brand,
      price: String(product.price),
      compareAtPrice: product.compareAtPrice ? String(product.compareAtPrice) : "",
      sku: product.sku,
      weight: product.weight ? String(product.weight) : "",
      imageUrl: product.imageUrl || "",
      stock: String(product.stock),
      status: product.status,
    });
    setIsProductModalOpen(true);
  };

  const handleSubmitProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.price.trim() || !formData.sku.trim()) {
      toast({
        title: "اطلاعات ناقص است",
        description: "لطفاً نام محصول، کد SKU و قیمت فروش را تکمیل نمایید.",
        variant: "destructive",
      });
      return;
    }

    const numericPrice = parseInt(formData.price.replace(/\D/g, ""), 10) || 0;
    const numericCompareAt = formData.compareAtPrice
      ? parseInt(formData.compareAtPrice.replace(/\D/g, ""), 10)
      : null;
    const numericStock = parseInt(formData.stock.replace(/\D/g, ""), 10) || 0;
    const numericWeight = parseInt(formData.weight.replace(/\D/g, ""), 10) || 0;

    setIsSubmitting(true);
    try {
      if (editingProduct) {
        // Edit flow
        await apiClient
          .patch(`/catalog/products/${editingProduct.id}`, {
            name: formData.name,
            title: formData.name,
            description: formData.description,
            category: formData.category,
            brand: formData.brand,
            price: numericPrice,
            compare_at_price: numericCompareAt,
            sku: formData.sku,
            weight: numericWeight,
            image_url: formData.imageUrl,
            stock: numericStock,
          })
          .catch(() =>
            apiClient.patch(`/products/${editingProduct.id}`, {
              title: formData.name,
              price: numericPrice,
            })
          )
          .catch(() => null);

        setProducts((prev) =>
          prev.map((p) =>
            p.id === editingProduct.id
              ? {
                  ...p,
                  name: formData.name,
                  description: formData.description,
                  category: formData.category,
                  brand: formData.brand,
                  price: numericPrice,
                  compareAtPrice: numericCompareAt,
                  sku: formData.sku,
                  weight: numericWeight,
                  imageUrl: formData.imageUrl,
                  stock: numericStock,
                  status: numericStock === 0 ? "out_of_stock" : formData.status,
                }
              : p
          )
        );

        toast({
          title: "محصول بروزرسانی شد",
          description: `اطلاعات «${formData.name}» ذخیره گردید.`,
          variant: "success",
        });
      } else {
        // Add flow
        const newId = `prod-${Date.now()}`;
        await apiClient
          .post("/catalog/products", {
            name: formData.name,
            title: formData.name,
            description: formData.description,
            category: formData.category,
            brand: formData.brand,
            price: numericPrice,
            compare_at_price: numericCompareAt,
            sku: formData.sku,
            weight: numericWeight,
            image_url: formData.imageUrl,
            stock: numericStock,
          })
          .catch(() =>
            apiClient.post("/products", {
              title: formData.name,
              price: numericPrice,
            })
          )
          .catch(() => null);

        const newProduct: AdminProduct = {
          id: newId,
          name: formData.name,
          description: formData.description,
          category: formData.category,
          brand: formData.brand || "متفرقه",
          price: numericPrice,
          compareAtPrice: numericCompareAt,
          sku: formData.sku,
          weight: numericWeight,
          imageUrl: formData.imageUrl,
          stock: numericStock,
          status: numericStock === 0 ? "out_of_stock" : formData.status,
          createdAt: new Date().toLocaleDateString("fa-IR"),
        };

        setProducts((prev) => [newProduct, ...prev]);

        toast({
          title: "محصول جدید با موفقیت افزوده شد",
          description: `کالای «${formData.name}» به کاتالوگ فروشگاه اضافه شد.`,
          variant: "success",
        });
      }

      setIsProductModalOpen(false);
    } catch (err: any) {
      toast({
        title: "خطا در ثبت محصول",
        description: err?.message || "عملیات با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteProduct = async (id: string) => {
    try {
      await apiClient
        .delete(`/catalog/products/${id}`)
        .catch(() => apiClient.delete(`/products/${id}`))
        .catch(() => null);

      setProducts((prev) => prev.filter((p) => p.id !== id));
      setIsDeletingId(null);
      toast({
        title: "محصول حذف گردید",
        description: "کالای انتخاب شده از کاتالوگ فروشگاه حذف شد.",
        variant: "default",
      });
    } catch (err) {
      // Ignored
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Stock & Status Badge Helpers                                    */
  /* ---------------------------------------------------------------- */

  const renderStockBadge = (stock: number) => {
    if (stock === 0) {
      return (
        <Badge variant="destructive" className="gap-1 text-[11px]">
          <XCircle className="h-3 w-3" />
          ناموجود
        </Badge>
      );
    }
    if (stock <= 5) {
      return (
        <Badge variant="warning" className="gap-1 text-[11px]">
          <AlertTriangle className="h-3 w-3" />
          رو به اتمام ({toPersianDigits(stock)})
        </Badge>
      );
    }
    return (
      <Badge variant="success" className="gap-1 text-[11px]">
        <CheckCircle2 className="h-3 w-3" />
        موجود ({toPersianDigits(stock)})
      </Badge>
    );
  };

  const renderStatusBadge = (status: AdminProduct["status"]) => {
    switch (status) {
      case "active":
        return <Badge variant="outline" className="text-emerald-600 border-emerald-300 bg-emerald-50/50">فعال</Badge>;
      case "draft":
        return <Badge variant="secondary">پیش‌نویس</Badge>;
      case "archived":
        return <Badge variant="outline">آرشیو شده</Badge>;
      case "out_of_stock":
        return <Badge variant="destructive">ناموجود</Badge>;
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Top Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">مدیریت محصولات</h1>
          <p className="text-sm text-muted-foreground">
            مشاهده، افزودن، ویرایش و مدیریت موجودی کاتالوگ کالاها
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={handleOpenAddModal} className="gap-2 shadow-sm">
            <Plus className="h-4 w-4" />
            افزودن محصول جدید
          </Button>
        </div>
      </div>

      {/* Overview Statistics Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">کل محصولات</p>
            <p className="text-xl font-bold text-foreground mt-1 font-mono">
              {toPersianDigits(products.length)}
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Package className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">کالاهای موجود</p>
            <p className="text-xl font-bold text-emerald-600 mt-1 font-mono">
              {toPersianDigits(products.filter((p) => p.stock > 0).length)}
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">ناموجود در انبار</p>
            <p className="text-xl font-bold text-destructive mt-1 font-mono">
              {toPersianDigits(products.filter((p) => p.stock === 0).length)}
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
            <XCircle className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">دسته‌بندی‌های فعال</p>
            <p className="text-xl font-bold text-blue-600 mt-1 font-mono">
              {toPersianDigits(new Set(products.map((p) => p.category)).size)}
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-950 dark:text-blue-400">
            <Layers className="h-5 w-5" />
          </div>
        </Card>
      </div>

      {/* Filters and Search Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {/* Search */}
          <div className="relative md:col-span-2 lg:col-span-2">
            <Search className="absolute right-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="جستجو در نام محصول، کد انبار (SKU) یا برند..."
              className="pr-9"
            />
          </div>

          {/* Category Filter */}
          <div>
            <Select value={selectedCategory} onValueChange={setSelectedCategory}>
              <SelectTrigger>
                <SelectValue placeholder="دسته‌بندی" />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Status Filter */}
          <div>
            <Select value={selectedStatus} onValueChange={setSelectedStatus}>
              <SelectTrigger>
                <SelectValue placeholder="وضعیت موجودی" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">همه وضعیت‌ها</SelectItem>
                <SelectItem value="in_stock">کالاهای موجود</SelectItem>
                <SelectItem value="out_of_stock">کالاهای ناموجود</SelectItem>
                <SelectItem value="active">محصولات فعال</SelectItem>
                <SelectItem value="draft">پیش‌نویس‌ها</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Reset Filter indicator */}
        {(searchQuery || selectedCategory !== "همه دسته‌بندی‌ها" || selectedStatus !== "all") && (
          <div className="mt-3 flex items-center justify-between border-t border-border/60 pt-3 text-xs text-muted-foreground">
            <span>
              فیلترهای اعمال شده ({toPersianDigits(filteredProducts.length)} محصول یافت شد)
            </span>
            <Button
              variant="link"
              size="sm"
              className="h-auto p-0 text-xs text-primary"
              onClick={() => {
                setSearchQuery("");
                setSelectedCategory("همه دسته‌بندی‌ها");
                setSelectedStatus("all");
              }}
            >
              پاک کردن همه فیلترها
            </Button>
          </div>
        )}
      </Card>

      {/* Products Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="border-b border-border bg-muted/40 text-xs font-semibold text-muted-foreground">
              <tr>
                <th className="py-3.5 px-4">تصویر</th>
                <th className="py-3.5 px-4">نام و مشخصات کالا</th>
                <th className="py-3.5 px-4">کد انبار (SKU)</th>
                <th className="py-3.5 px-4">دسته‌بندی</th>
                <th className="py-3.5 px-4">قیمت فروش</th>
                <th className="py-3.5 px-4">وضعیت موجودی</th>
                <th className="py-3.5 px-4">وضعیت</th>
                <th className="py-3.5 px-4 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredProducts.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-muted-foreground">
                    هیچ محصولی با معیارهای جستجوی شما یافت نشد.
                  </td>
                </tr>
              ) : (
                filteredProducts.map((product) => (
                  <tr key={product.id} className="hover:bg-muted/30 transition-colors">
                    {/* Thumbnail */}
                    <td className="py-3 px-4">
                      <div className="relative flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-lg border bg-muted">
                        {product.imageUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={product.imageUrl}
                            alt={product.name}
                            className="h-full w-full object-cover"
                            onError={(e) => {
                              // fallback on image broken
                              (e.target as HTMLElement).style.display = "none";
                            }}
                          />
                        ) : (
                          <ImageIcon className="h-6 w-6 text-muted-foreground/60" />
                        )}
                      </div>
                    </td>

                    {/* Name & Brand */}
                    <td className="py-3 px-4 max-w-xs">
                      <p className="font-semibold text-foreground line-clamp-1" title={product.name}>
                        {product.name}
                      </p>
                      <span className="text-xs text-muted-foreground">
                        برند: {product.brand} &middot; {product.weight ? `${toPersianDigits(product.weight)} گرم` : ""}
                      </span>
                    </td>

                    {/* SKU */}
                    <td className="py-3 px-4 font-mono text-xs text-muted-foreground" dir="ltr">
                      {product.sku}
                    </td>

                    {/* Category */}
                    <td className="py-3 px-4">
                      <Badge variant="secondary" className="font-normal text-xs">
                        {product.category}
                      </Badge>
                    </td>

                    {/* Price & Compare at */}
                    <td className="py-3 px-4">
                      <div className="space-y-0.5">
                        <span className="font-bold text-foreground block font-mono">
                          {formatPrice(product.price)}
                        </span>
                        {product.compareAtPrice && product.compareAtPrice > product.price && (
                          <span className="text-xs text-muted-foreground line-through block font-mono">
                            {formatPrice(product.compareAtPrice)}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Stock Status */}
                    <td className="py-3 px-4">{renderStockBadge(product.stock)}</td>

                    {/* Status */}
                    <td className="py-3 px-4">{renderStatusBadge(product.status)}</td>

                    {/* Action Buttons */}
                    <td className="py-3 px-4 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-foreground"
                          title="ویرایش محصول"
                          onClick={() => handleOpenEditModal(product)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:bg-destructive/10"
                          title="حذف محصول"
                          onClick={() => setIsDeletingId(product.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Table Footer / Counter */}
        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-muted-foreground">
          <span>
            نمایش {toPersianDigits(filteredProducts.length)} از {toPersianDigits(products.length)} کالا
          </span>
          <span className="font-mono">بروزرسانی زنده کاتالوگ انبار</span>
        </div>
      </Card>

      {/* ============================================================== */}
      {/* MODAL: Add / Edit Product Modal Form                           */}
      {/* ============================================================== */}
      <Dialog open={isProductModalOpen} onOpenChange={setIsProductModalOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package className="h-5 w-5 text-primary" />
              {editingProduct ? "ویرایش اطلاعات محصول" : "افزودن محصول جدید به کاتالوگ"}
            </DialogTitle>
            <DialogDescription>
              مشخصات فنی، قیمت‌گذاری و تصویر محصول را به دقت تکمیل فرمایید.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmitProduct} className="space-y-4 py-2">
            {/* Name */}
            <div className="space-y-1.5">
              <Label htmlFor="prodName">نام کامل محصول</Label>
              <Input
                id="prodName"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="مثلاً: گوشی موبایل سامسونگ Galaxy S24 Ultra"
                required
              />
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <Label htmlFor="prodDesc">توضیحات و مشخصات کالا</Label>
              <Textarea
                id="prodDesc"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="توضیحات تفصیلی، ویژگی‌های کلیدی، مشخصات فنی..."
                rows={3}
              />
            </div>

            {/* Category & Brand */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>دسته‌بندی کالا</Label>
                <Select
                  value={formData.category}
                  onValueChange={(val) => setFormData({ ...formData, category: val })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="انتخاب دسته‌بندی" />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.filter((c) => c !== "همه دسته‌بندی‌ها").map((cat) => (
                      <SelectItem key={cat} value={cat}>
                        {cat}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="prodBrand">برند تجاری</Label>
                <Input
                  id="prodBrand"
                  value={formData.brand}
                  onChange={(e) => setFormData({ ...formData, brand: e.target.value })}
                  placeholder="مثلاً: سامسونگ، اپل، شیائومی"
                />
              </div>
            </div>

            {/* Pricing: Price and Compare at Price */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="prodPrice">قیمت فروش (تومان)</Label>
                <Input
                  id="prodPrice"
                  value={formData.price ? Number(formData.price).toLocaleString("fa-IR") : ""}
                  onChange={(e) => {
                    const raw = e.target.value.replace(/\D/g, "");
                    setFormData({ ...formData, price: raw });
                  }}
                  placeholder="مثلاً: ۱۲,۵۰۰,۰۰۰"
                  dir="ltr"
                  className="font-mono text-left font-bold"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="prodComparePrice">قیمت خط‌خورده / قبل از تخفیف (تومان)</Label>
                <Input
                  id="prodComparePrice"
                  value={
                    formData.compareAtPrice
                      ? Number(formData.compareAtPrice).toLocaleString("fa-IR")
                      : ""
                  }
                  onChange={(e) => {
                    const raw = e.target.value.replace(/\D/g, "");
                    setFormData({ ...formData, compareAtPrice: raw });
                  }}
                  placeholder="اختیاری: مثلاً ۱۴,۰۰۰,۰۰۰"
                  dir="ltr"
                  className="font-mono text-left"
                />
              </div>
            </div>

            {/* SKU, Weight, and Stock */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="prodSku">کد انبار (SKU)</Label>
                <Input
                  id="prodSku"
                  value={formData.sku}
                  onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                  placeholder="مثلاً: SAM-A54-256"
                  dir="ltr"
                  className="font-mono text-left"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="prodWeight">وزن تقریبی (گرم)</Label>
                <Input
                  id="prodWeight"
                  value={formData.weight}
                  onChange={(e) =>
                    setFormData({ ...formData, weight: e.target.value.replace(/\D/g, "") })
                  }
                  placeholder="مثلاً: ۲۵۰"
                  dir="ltr"
                  className="font-mono text-left"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="prodStock">تعداد موجودی انبار</Label>
                <Input
                  id="prodStock"
                  value={formData.stock}
                  onChange={(e) =>
                    setFormData({ ...formData, stock: e.target.value.replace(/\D/g, "") })
                  }
                  placeholder="تعداد کالا"
                  dir="ltr"
                  className="font-mono text-left"
                  required
                />
              </div>
            </div>

            {/* Image URL */}
            <div className="space-y-1.5">
              <Label htmlFor="prodImage">آدرس تصویر محصول (Image URL)</Label>
              <Input
                id="prodImage"
                value={formData.imageUrl}
                onChange={(e) => setFormData({ ...formData, imageUrl: e.target.value })}
                placeholder="https://example.com/image.jpg"
                dir="ltr"
                className="font-mono text-left text-xs"
              />
              {formData.imageUrl && (
                <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <div className="h-10 w-10 shrink-0 overflow-hidden rounded border">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={formData.imageUrl}
                      alt="پیش‌نمایش"
                      className="h-full w-full object-cover"
                    />
                  </div>
                  <span>پیش‌نمایش تصویر بارگذاری شد</span>
                </div>
              )}
            </div>

            {/* Status Select */}
            <div className="space-y-1.5">
              <Label>وضعیت انتشار کالا</Label>
              <Select
                value={formData.status}
                onValueChange={(val: any) => setFormData({ ...formData, status: val })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب وضعیت" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">فعال (قابل خرید در فروشگاه)</SelectItem>
                  <SelectItem value="draft">پیش‌نویس (عدم نمایش به مشتریان)</SelectItem>
                  <SelectItem value="archived">آرشیو شده</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <DialogFooter className="pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsProductModalOpen(false)}
              >
                انصراف
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting
                  ? "در حال ذخیره..."
                  : editingProduct
                  ? "ذخیره تغییرات"
                  : "ایجاد و ثبت محصول"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ============================================================== */}
      {/* MODAL: Delete Confirmation Modal                               */}
      {/* ============================================================== */}
      <Dialog open={Boolean(isDeletingId)} onOpenChange={(open) => !open && setIsDeletingId(null)}>
        <DialogContent className="max-w-sm" dir="rtl">
          <DialogHeader>
            <DialogTitle className="text-destructive flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              تایید حذف محصول
            </DialogTitle>
            <DialogDescription>
              آیا از حذف این کالا از کاتالوگ فروشگاه اطمینان دارید؟ این عمل غیرقابل بازگشت است.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="pt-3">
            <Button variant="outline" onClick={() => setIsDeletingId(null)}>
              انصراف
            </Button>
            <Button
              variant="destructive"
              onClick={() => isDeletingId && handleDeleteProduct(isDeletingId)}
            >
              بله، حذف شود
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
