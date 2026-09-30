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
  CheckSquare,
  Square,
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
import { useAdminQuery } from "@/lib/api/admin-query";

const PRODUCTS_QUERY_KEY = "admin-products" as const;
import { fetchProductAccessories, fetchProductById, type ApiProductAccessory } from "@/lib/api/services";
import {
  AttributesEditor,
  type ProductAttributeDraft,
} from "@/components/admin/product-attributes-editor";
import { MediaPicker } from "@/components/admin/media-picker";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { adminBulkApi } from "@/lib/api/bulk-operations";

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
  imageAlt?: string;
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


/* ------------------------------------------------------------------ */
/*  Main Admin Products Page Component                                 */
/* ------------------------------------------------------------------ */

export default function AdminProductsPage() {
  const { toast } = useToast();

  // Starts empty, never seeded from a demo list: a fabricated row is
  // indistinguishable from a real one once it is on screen.

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
    imageAlt: "",
    stock: "10",
    status: "active" as AdminProduct["status"],
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Accessories (cross-sell) editor state — loaded when editing a product.
  const [accessoryIds, setAccessoryIds] = useState<string[]>([]);
  const [accessoryOptions, setAccessoryOptions] = useState<ApiProductAccessory[]>([]);

  // Specification sheet + tags. Loaded when editing; empty when creating.
  const [attributeDrafts, setAttributeDrafts] = useState<ProductAttributeDraft[]>([]);
  const [tagIds, setTagIds] = useState<string[]>([]);

  // Fetch products from API. An empty catalogue and a failed request must
  // look different: an operator cannot tell "we have no products" from "the
  // API is down". The list is exactly what the server returned — never a
  // stand-in — and the failure is a message, not an empty table.
  const {
    data: productsData,
    loading: isLoading,
    error: loadError,
    reload: reloadProducts,
  } = useAdminQuery({
    queryKey: [PRODUCTS_QUERY_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/catalog/products");
      const items = Array.isArray(res.data?.items) ? res.data.items : [];
      return items.map((p: any): AdminProduct => ({
        id: String(p.id),
        name: p.title || p.name,
        description: p.description || "",
        category: p.category?.name || p.category_name || "—",
        brand: p.brand?.name || p.brand || "—",
        price: p.price ?? 0,
        compareAtPrice: p.original_price || p.compare_at_price || null,
        sku: p.sku || "",
        weight: p.weight ?? 0,
        imageUrl: p.thumbnail || p.images?.[0]?.url || p.images?.[0] || "",
        imageAlt: p.images?.[0]?.alt_text || "",
        // `?? 0`, not `?? 10`: a missing stock field means "not reported",
        // and inventing 10 puts phantom inventory on screen.
        stock: p.stock ?? p.stock_count ?? 0,
        status:
          p.is_active === false
            ? "draft"
            : (p.stock ?? p.stock_count ?? 0) === 0
              ? "out_of_stock"
              : "active",
        createdAt: p.created_at ? new Date(p.created_at).toLocaleDateString("fa-IR") : "—",
      }));
    },
    fallbackError: "دریافت فهرست محصولات با خطا مواجه شد.",
  });
  const [localProducts, setLocalProducts] = useState<AdminProduct[]>([]);
  // Sync the local state from query, keeping the optimistic-update behaviour
  // that the edit and delete handlers currently rely on.
  React.useEffect(() => {
    if (productsData) setLocalProducts(productsData);
  }, [productsData]);
  const products = localProducts;

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
  /*  Bulk selection                                                   */
  /* ---------------------------------------------------------------- */

  // Selection is CLEARED, not preserved, whenever the page set changes. The
  // backend bulk endpoint only accepts the four fields it validates; a
  // selection carried across a filter change would silently target rows the
  // operator can no longer see, and "I selected 3, 40 are gone" is not a
  // recoverable mistake. Clearing makes the selection always mean "the rows
  // currently on screen".
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkDeleteTarget, setBulkDeleteTarget] = useState<string[] | null>(null);

  React.useEffect(() => {
    setSelected(new Set());
  }, [productsData]);

  // A filter change hides rows without changing `productsData`, so the
  // selection is reconciled against the visible set here as well.
  React.useEffect(() => {
    const visible = new Set(filteredProducts.map((p) => p.id));
    setSelected((prev) => {
      const next = new Set([...prev].filter((id) => visible.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [filteredProducts]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allVisibleSelected =
    filteredProducts.length > 0 && filteredProducts.every((p) => selected.has(p.id));

  const toggleSelectAllVisible = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) filteredProducts.forEach((p) => next.delete(p.id));
      else filteredProducts.forEach((p) => next.add(p.id));
      return next;
    });
  };

  /**
   * Bulk publish / unpublish / feature. Only the fields the backend
   * validates are sent — nothing money-related is in this payload.
   *
   * The endpoint answers with a count, not a per-row result: a count below
   * the selection size means some ids matched no product, and saying
   * "done" without that would be a lie about how much was changed.
   */
  const runBulkUpdate = async (
    action: "activate" | "deactivate" | "feature" | "unfeature",
  ) => {
    if (selected.size === 0) return;
    const labels: Record<typeof action, string> = {
      activate: "فعال‌سازی",
      deactivate: "غیرفعال‌سازی",
      feature: "انتخاب به‌عنوان ویژه",
      unfeature: "حذف از ویژه‌ها",
    };
    if (!confirm(`${toPersianDigits(String(selected.size))} محصول — ${labels[action]}؟`)) return;

    setBulkBusy(true);
    try {
      const patch =
        action === "activate"
          ? { is_active: true }
          : action === "deactivate"
            ? { is_active: false }
            : action === "feature"
              ? { is_featured: true }
              : { is_featured: false };

      const ids = [...selected];
      const result = await adminBulkApi.bulkUpdateProducts(ids.map((id) => ({ id, ...patch })));
      if (result.updated < ids.length) {
        toast({
          title: "انجام شد با خطا",
          description: `موفق: ${toPersianDigits(String(result.updated))} — ناموفق: ${toPersianDigits(String(ids.length - result.updated))}`,
          variant: "destructive",
        });
      } else {
        toast({
          title: `${labels[action]} انجام شد`,
          description: `${toPersianDigits(String(result.updated))} محصول`,
        });
      }
      setSelected(new Set());
      await reloadProducts();
    } catch {
      toast({ title: "عملیات گروهی ناموفق بود", variant: "destructive" });
    } finally {
      setBulkBusy(false);
    }
  };

  const confirmBulkDelete = async () => {
    if (!bulkDeleteTarget || bulkDeleteTarget.length === 0) return;
    setBulkBusy(true);
    try {
      const result = await adminBulkApi.bulkDeleteProducts(bulkDeleteTarget);
      if (result.deleted < bulkDeleteTarget.length) {
        toast({
          title: "حذف کامل نشد",
          description: `حذف‌شده: ${toPersianDigits(String(result.deleted))} — ناموفق: ${toPersianDigits(String(bulkDeleteTarget.length - result.deleted))}`,
          variant: "destructive",
        });
      } else {
        toast({ title: "محصولات حذف شدند", description: `${toPersianDigits(String(result.deleted))} محصول` });
      }
      setSelected(new Set());
      setBulkDeleteTarget(null);
      await reloadProducts();
    } catch {
      toast({ title: "حذف گروهی ناموفق بود", variant: "destructive" });
    } finally {
      setBulkBusy(false);
    }
  };

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
      imageAlt: "",
      stock: "10",
      status: "active",
    });
    setAttributeDrafts([]);
    setTagIds([]);
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
      imageAlt: product.imageAlt || "",
      stock: String(product.stock),
      status: product.status,
    });
    // Load current accessories for this product and the candidate pool.
    setAccessoryIds([]);
    setAccessoryOptions([]);
    fetchProductAccessories(product.id).then((acc) => {
      setAccessoryIds(acc.map((a) => a.id));
      setAccessoryOptions(acc);
    });
    // The list endpoint does not carry attributes or tags; the detail one does.
    // Until it lands the editor shows empty rather than inventing a state.
    setAttributeDrafts([]);
    setTagIds([]);
    fetchProductById(product.id)
      .then((detail) => {
        setAttributeDrafts(
          (detail.product_attributes ?? []).map((pa) => ({
            attributeId: pa.attribute_id,
            value: pa.attribute_value_id,
            valueLabel: pa.attribute_value ?? "",
          })),
        );
        setTagIds((detail.tags ?? []).map((t) => t.id));
      })
      .catch(() => {
        // Left empty; the spec tab simply shows no rows for this product.
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
      let savedProductId = editingProduct?.id;
      if (editingProduct) {
        // Edit flow
        await apiClient.patch(`/catalog/products/${editingProduct.id}`, {
          name: formData.name,
          description: formData.description,
          weight: numericWeight || null,
          // Both are full replacement sets server-side: an empty list clears
          // them, omitting the field leaves them alone. They are always sent
          // so that clearing the editor actually clears the product.
          attributes: attributeDrafts.map((d) => ({
            attribute_id: d.attributeId,
            attribute_value_id: d.value,
          })),
          tag_ids: tagIds,
        });

        // The edit path has no nested image field, so a changed image is
        // applied through the dedicated image route.
        if (formData.imageUrl) {
          try {
            await apiClient.post(`/catalog/products/${editingProduct.id}/images`, {
              url: formData.imageUrl,
              is_primary: true,
              position: 0,
              alt_text: formData.imageAlt || formData.name || null,
            });
          } catch {
            toast({
              title: "تصویر ذخیره نشد",
              description: "محصول بروزرسانی شد اما ثبت تصویر با خطا مواجه شد.",
              variant: "destructive",
            });
          }
        }

        setLocalProducts((prev) =>
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
        // Add flow — resolve category_id to satisfy backend ProductCreate schema
        let catId: string | undefined;
        try {
          const catRes = await apiClient.get<{ items: Array<{ id: string; name: string }> }>("/catalog/categories");
          const cats = catRes.data?.items || (Array.isArray(catRes.data) ? catRes.data : []);
          const match = cats.find((c) => c.name === formData.category || formData.category.includes(c.name));
          catId = match?.id || cats[0]?.id;
        } catch {
          // ignore
        }
        if (!catId) catId = crypto.randomUUID();

        const created = await apiClient.post<{ id: string }>("/catalog/products", {
          name: formData.name,
          category_id: catId,
          description: formData.description,
          weight: numericWeight || null,
          tag_ids: tagIds,
          images: formData.imageUrl
            ? [{
                url: formData.imageUrl,
                is_primary: true,
                position: 0,
                alt_text: formData.imageAlt || formData.name || null,
              }]
            : [],
          attributes: attributeDrafts
            .filter((d) => d.value)
            .map((d) => ({
              attribute_id: d.attributeId,
              attribute_value_id: d.value,
            })),
          variants: [
            {
              sku: formData.sku,
              price: numericPrice,
              compare_at_price: numericCompareAt || null,
              is_active: true,
            },
          ],
        });

        savedProductId = String(created.data?.id ?? crypto.randomUUID());
        const newProduct: AdminProduct = {
          id: savedProductId,
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

        setLocalProducts((prev) => [newProduct, ...prev]);

        toast({
          title: "محصول جدید با موفقیت افزوده شد",
          description: `کالای «${formData.name}» به کاتالوگ فروشگاه اضافه شد.`,
          variant: "success",
        });
      }

      // Persist the accessory (cross-sell) set after the product exists.
      if (savedProductId) {
        try {
          await apiClient.put(`/catalog/products/${savedProductId}/accessories`, {
            accessory_ids: accessoryIds,
          });
        } catch {
          toast({
            title: "کالاهای مکمل ذخیره نشد",
            description: "محصول ذخیره شد اما به‌روزرسانی کالاهای مکمل با خطا مواجه شد.",
            variant: "destructive",
          });
        }
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
      await apiClient.delete(`/catalog/products/${id}`);

      setLocalProducts((prev) => prev.filter((p) => p.id !== id));
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

  const productColumns: DataTableColumn<AdminProduct>[] = [
    {
      key: "select",
      header: "",
      className: "w-10",
      render: (product) => (
        <button
          onClick={() => toggleSelect(product.id)}
          aria-label={selected.has(product.id) ? "برداشتن انتخاب" : "انتخاب"}
          className="text-muted-foreground hover:text-foreground"
        >
          {selected.has(product.id) ? (
            <CheckSquare className="h-4 w-4 text-primary" />
          ) : (
            <Square className="h-4 w-4" />
          )}
        </button>
      ),
    },
    {
      key: "image",
      header: "تصویر",
      render: (product) => (
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
      ),
    },
    {
      key: "name",
      header: "نام و مشخصات کالا",
      className: "max-w-xs",
      render: (product) => (
        <div>
          <p className="font-semibold text-foreground line-clamp-1" title={product.name}>
            {product.name}
          </p>
          <span className="text-xs text-muted-foreground">
            برند: {product.brand} &middot;{" "}
            {product.weight ? `${toPersianDigits(product.weight)} گرم` : ""}
          </span>
        </div>
      ),
    },
    {
      key: "sku",
      header: "کد انبار (SKU)",
      className: "font-mono text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (product) => <span dir="ltr">{product.sku}</span>,
    },
    {
      key: "category",
      header: "دسته‌بندی",
      hideOnMobile: true,
      render: (product) => (
        <Badge variant="secondary" className="font-normal text-xs">
          {product.category}
        </Badge>
      ),
    },
    {
      key: "price",
      header: "قیمت فروش",
      render: (product) => (
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
      ),
    },
    {
      key: "stock",
      header: "وضعیت موجودی",
      render: (product) => renderStockBadge(product.stock),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (product) => renderStatusBadge(product.status),
    },
    {
      key: "actions",
      header: <span className="sr-only">عملیات</span>,
      className: "text-center",
      render: (product) => (
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
      ),
    },
  ];

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
              className="ps-9"
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

      {/* A failed load is shown as a failure, not as an empty table: "the API
          is down" and "you have no products" call for different actions. */}
      {loadError && !isLoading && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm"
        >
          <span className="text-destructive">
            دریافت فهرست محصولات با خطا مواجه شد: {loadError}
          </span>
          <Button variant="outline" size="sm" onClick={() => void reloadProducts()}>
            تلاش مجدد
          </Button>
        </div>
      )}

      {/* Bulk actions — shown only while something is selected, so a
          mis-click with an empty selection is impossible. */}
      {selected.size > 0 && (
        <Card className="p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {toPersianDigits(String(selected.size))} محصول انتخاب شده:
            </span>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulkUpdate("activate")}>
              فعال‌سازی
            </Button>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulkUpdate("deactivate")}>
              غیرفعال‌سازی
            </Button>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulkUpdate("feature")}>
              ویژه
            </Button>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulkUpdate("unfeature")}>
              حذف از ویژه‌ها
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={bulkBusy}
              onClick={() => setBulkDeleteTarget([...selected])}
            >
              حذف
            </Button>
            <Button size="sm" variant="ghost" disabled={bulkBusy} onClick={() => setSelected(new Set())}>
              لغو انتخاب
            </Button>
          </div>
        </Card>
      )}

      {/* Products Table */}
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleSelectAllVisible}
          disabled={filteredProducts.length === 0}
          className="text-xs text-muted-foreground"
        >
          {allVisibleSelected ? "برداشتن انتخاب همه" : "انتخاب همه نمایش‌داده‌شده‌ها"}
        </Button>
      </div>
      <DataTable<AdminProduct>
        columns={productColumns}
        rows={filteredProducts}
        rowKey={(p) => p.id}
        emptyMessage={
          loadError
            ? "فهرست محصولات بارگذاری نشد."
            : "هیچ محصولی با معیارهای جستجوی شما یافت نشد."
        }
      />

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

            {/* Product image — media library, same swap as the blog cover */}
            <div className="space-y-1.5">
              <Label htmlFor="prodImage">تصویر محصول</Label>
              <MediaPicker
                value={formData.imageUrl}
                onChange={(url) => setFormData({ ...formData, imageUrl: url })}
                label="تصویر محصول"
              />
              <Input
                value={formData.imageAlt}
                onChange={(e) =>
                  setFormData({ ...formData, imageAlt: e.target.value })
                }
                placeholder={
                  formData.name
                    ? `متن جایگزین تصویر (پیشنهاد: ${formData.name})`
                    : "متن جایگزین تصویر"
                }
                aria-label="متن جایگزین تصویر محصول"
              />
              <p className="text-[11px] text-muted-foreground">
                توضیح تصویر برای صفحه‌خوان‌ها و جست‌وجوی تصویر. خالی ماندنش یعنی
                صفحه‌خوان تصویر را «تصویر» می‌خواند.
              </p>
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

            {/* Accessories (cross-sell) — Odoo accessory_product_ids concept */}
            <div className="space-y-2 border-t border-border pt-4">
              <Label>کالاهای مکمل (پیشنهاد در صفحه محصول و سبد)</Label>
              <p className="text-xs text-muted-foreground">
                این کالاها در کنار محصول به‌عنوان پیشنهاد خرید نمایش داده می‌شوند.
              </p>
              <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-border p-2">
                {products
                  .filter((p) => !editingProduct || p.id !== editingProduct.id)
                  .map((p) => {
                    const checked = accessoryIds.includes(p.id);
                    return (
                      <label
                        key={p.id}
                        className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted"
                      >
                        <input
                          type="checkbox"
                          className="h-4 w-4 accent-primary"
                          checked={checked}
                          onChange={(e) => {
                            setAccessoryIds((prev) =>
                              e.target.checked
                                ? [...prev, p.id]
                                : prev.filter((id) => id !== p.id)
                            );
                          }}
                        />
                        <span className="flex-1 truncate">{p.name}</span>
                        <span className="text-xs text-muted-foreground">
                          {formatPrice(p.price)}
                        </span>
                      </label>
                    );
                  })}
                {products.length <= 1 && (
                  <p className="px-2 py-3 text-center text-xs text-muted-foreground">
                    کالای دیگری برای انتخاب وجود ندارد.
                  </p>
                )}
              </div>
              {accessoryIds.length > 0 && (
                <p className="text-xs text-primary">
                  {toPersianDigits(accessoryIds.length)} کالای مکمل انتخاب شده
                </p>
              )}
            </div>

            {/* Specification sheet + tags — the storefront's spec tab and
                faceted filters read exactly these two tables. */}
            <AttributesEditor
              value={attributeDrafts}
              onChange={setAttributeDrafts}
              tagIds={tagIds}
              onTagIdsChange={setTagIds}
            />

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
      {/* MODAL: Bulk Delete Confirmation Modal                        */}
      {/* ============================================================== */}
      {/* The count is in the title, not the body: "delete these products"
          with no number is how a 3-row cleanup becomes a 300-row one. */}
      <Dialog open={Boolean(bulkDeleteTarget)} onOpenChange={(open) => !open && setBulkDeleteTarget(null)}>
        <DialogContent className="max-w-sm" dir="rtl">
          <DialogHeader>
            <DialogTitle className="text-destructive flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              تایید حذف {toPersianDigits(String(bulkDeleteTarget?.length ?? 0))} محصول
            </DialogTitle>
            <DialogDescription>
              {toPersianDigits(String(bulkDeleteTarget?.length ?? 0))} محصول انتخاب‌شده به‌طور کامل از
              کاتالوگ حذف می‌شوند. این عمل غیرقابل بازگشت است.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="pt-3">
            <Button variant="outline" onClick={() => setBulkDeleteTarget(null)}>
              انصراف
            </Button>
            <Button variant="destructive" disabled={bulkBusy} onClick={confirmBulkDelete}>
              بله، همه حذف شوند
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
