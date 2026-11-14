"use client";

import React, {
  Suspense,
  useState,
  useEffect,
  useMemo,
  useRef,
} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Package,
  PackageCheck,
  Plus,
  Search,
  Edit,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ImageIcon,
  Layers,
  ExternalLink,
  RefreshCw,
  X,
  ChevronUp,
  ChevronDown,
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
import { formatPrice, toPersianDigits, toEnglishDigits, cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import apiClient from "@/lib/api/client";
import { useAdminQuery } from "@/lib/api/admin-query";

const PRODUCTS_QUERY_KEY = "admin-products" as const;
import { fetchProductAccessories, fetchProductById, type ApiProductAccessory } from "@/lib/api/services";
import {
  AttributesEditor,
  type ProductAttributeDraft,
} from "@/components/admin/product-attributes-editor";
import {
  VariationManager,
  variationDraftsToPayload,
  draftsFromDetail,
  type VariationManagerValue,
} from "@/components/admin/variation-manager";
import { ProductAddonsEditor } from "@/components/admin/product-addons-editor";
import { Boxes as BoxesIcon } from "lucide-react";
import { MediaPicker } from "@/components/admin/media-picker";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import type { BulkAction } from "@/components/admin/list-engine";
import { adminBulkApi } from "@/lib/api/bulk-operations";

/* ------------------------------------------------------------------ */
/*  Type Definitions                                                   */
/* ------------------------------------------------------------------ */

interface CategoryOption {
  id: string;
  name: string;
  slug: string;
  parentId?: string | null;
  depth?: number;
}

interface AdminProduct {
  id: string;
  name: string;
  /** The storefront URL's slug. Carried so the admin bar's contextual
   *  "edit product" link (which arrives with the slug) can find the row. */
  slug?: string;
  description: string;
  categoryId: string;
  category: string;
  brand: string;
  price: number;
  compareAtPrice?: number | null;
  sku: string;
  weight?: number; // in grams
  imageUrl?: string;
  imageAlt?: string;
  stock: number;
  /** false = untracked/unlimited (ledger stock null): the product's
   *  availability comes from `stockStatus`, NOT from the count — a manually
   *  available product must never render ناموجود just because nothing is
   *  counted (WooCommerce manage-stock parity). */
  stockTracked: boolean;
  stockStatus: "instock" | "outofstock";
  lowStockThreshold: number | null;
  status: "active" | "draft" | "archived" | "out_of_stock";
  /** The raw publish status from the server (active/draft/archived) — kept
   *  separate from the display `status`, which folds "stock === 0" into
   *  "out_of_stock" and must NEVER be sent back in a PATCH (the backend
   *  rejects it with 422). */
  rawStatus: "active" | "draft" | "archived";
  createdAt: string;
}

/**
 * A random internal SKU for the "generate" button. Ambiguous glyphs
 * (0/O, 1/I/L) are excluded so a human can read the code aloud. The backend
 * still enforces uniqueness and will reject the rare collision with a 409.
 */
function makeRandomSku(): string {
  const alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  let suffix = "";
  for (let i = 0; i < 6; i++) {
    suffix += alphabet[bytes[i]! % alphabet.length];
  }
  return `SKU-${suffix}`;
}


/* ------------------------------------------------------------------ */
/*  Main Admin Products Page Component                                 */
/* ------------------------------------------------------------------ */

export default function AdminProductsPage() {
  // useSearchParams (inside) opts the subtree out of static prerendering; the
  // Suspense boundary is what keeps the build from failing on it. Same pattern
  // as admin/media.
  return (
    <Suspense
      fallback={
        <div className="animate-pulse space-y-4 px-6 py-8">
          <div className="h-8 w-56 rounded-lg bg-muted/70" />
          <div className="h-64 rounded-2xl border border-border bg-card" />
        </div>
      }
    >
      <AdminProductsPageInner />
    </Suspense>
  );
}

function AdminProductsPageInner() {
  const { toast } = useToast();

  // Starts empty, never seeded from a demo list: a fabricated row is
  // indistinguishable from a real one once it is on screen.

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");

  // Dynamic Categories from Backend (synced with /admin/categories).
  // The backend caps page_size at 1000 and the catalogue holds thousands of
  // categories after imports, so a single request would silently drop the
  // rest — and the modal could not offer the category the operator just made.
  // Page through everything.
  const { data: categoriesData, reload: reloadCategories } = useAdminQuery({
    queryKey: ["admin-categories"],
    queryFn: async () => {
      const PAGE = 1000;
      const all: any[] = [];
      let page = 1;
      for (;;) {
        const res = await apiClient.get("/catalog/categories", {
          params: { page, page_size: PAGE },
        });
        const items = Array.isArray(res.data?.items)
          ? res.data.items
          : Array.isArray(res.data)
            ? res.data
            : [];
        all.push(...items);
        const meta = res.data?.meta ?? {};
        if (items.length === 0 || page >= (meta.total_pages ?? page)) break;
        page += 1;
      }
      return all.map((c: any) => ({
        id: String(c.id),
        name: String(c.name),
        slug: String(c.slug || ""),
        parentId: c.parent_id ? String(c.parent_id) : null,
        depth: typeof c.depth === "number" ? c.depth : 0,
      })) as CategoryOption[];
    },
    fallbackError: "دریافت فهرست دسته‌بندی‌ها ناموفق بود.",
  });
  const categories = categoriesData ?? [];

  // Form State
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    categoryId: "",
    category: "",
    brand: "",
    price: "",
    compareAtPrice: "",
    sku: "",
    weight: "",
    imageUrl: "",
    imageAlt: "",
    // Empty by design: an unnoticed prefilled "10" shipped products with a
    // stock the operator never chose. WooCommerce parity: the explicit
    // "manage stock" switch decides — OFF = untracked/unlimited, ON = the
    // typed quantity is tracked (with a low-stock alert threshold).
    stock: "",
    manageStock: false,
    lowStockThreshold: "",
    // WooCommerce "Stock status" parity: manual availability when stock
    // management is OFF. ON = counted, this flag is ignored.
    stockStatus: "instock" as "instock" | "outofstock",
    // WooCommerce "Allow backorders?" parity (manage stock ON).
    backorderAllowed: false,
    // WooCommerce "Global unique id" parity (GTIN/UPC/EAN barcode).
    barcode: "",
    status: "active" as AdminProduct["status"],
    // Warehouse relevance: digital goods hide SKU/weight/stock entirely.
    productType: "physical" as "physical" | "digital",
    // USD source prices (Nobitex updater). Empty = not managed by the sweep.
    // On the CREATE path these attach to the nested variant; on EDIT they are
    // applied to the product's first variant, because the backend derives the
    // Toman price from them on every sweep.
    usdPrice: "",
    usdSalePrice: "",
  });

  // Keep newly created quick-categories selectable immediately before the full refetch lands
  const allCategoryOptions = useMemo(() => {
    if (formData.categoryId && !categories.some((c) => c.id === formData.categoryId)) {
      return [
        {
          id: formData.categoryId,
          name: formData.category || "دسته‌بندی جدید",
          slug: "",
          depth: 0,
        },
        ...categories,
      ];
    }
    return categories;
  }, [categories, formData.categoryId, formData.category]);
  // Modal State (Add / Edit)
  const [isProductModalOpen, setIsProductModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<AdminProduct | null>(null);
  // Product Add-ons editor dialog state (WooCommerce Product Add-ons parity)
  const [addonsEditorOpen, setAddonsEditorOpen] = useState(false);
  const [isDeletingId, setIsDeletingId] = useState<string | null>(null);

  // Quick Category Add modal state (inline from product form)
  const [isQuickCatOpen, setIsQuickCatOpen] = useState(false);
  const [quickCatName, setQuickCatName] = useState("");
  const [quickCatSlug, setQuickCatSlug] = useState("");
  const [quickCatParentId, setQuickCatParentId] = useState("");
  const [isSavingQuickCat, setIsSavingQuickCat] = useState(false);

  const handleQuickAddCategory = async () => {
    if (!quickCatName.trim()) return;
    setIsSavingQuickCat(true);
    try {
      const res = await apiClient.post<{ id: string }>("/catalog/categories", {
        name: quickCatName.trim(),
        slug: quickCatSlug.trim() || undefined,
        parent_id: quickCatParentId || null,
      });
      const newId = String(res.data?.id);
      setFormData((prev) => ({
        ...prev,
        categoryId: newId,
        category: quickCatName.trim(),
      }));
      void reloadCategories();
      toast({
        title: "دسته‌بندی افزوده شد",
        description: `دسته‌بندی «${quickCatName.trim()}» ایجاد و انتخاب شد.`,
      });
      setQuickCatName("");
      setQuickCatSlug("");
      setQuickCatParentId("");
      setIsQuickCatOpen(false);
    } catch {
      toast({
        title: "خطا در ایجاد دسته‌بندی",
        description: "امکان ثبت دسته‌بندی جدید وجود نداشت.",
        variant: "destructive",
      });
    } finally {
      setIsSavingQuickCat(false);
    }
  };

  const [isSubmitting, setIsSubmitting] = useState(false);
  // The inventory quantity the EDIT modal was opened with — sent back on
  // save as `original_stock` so a concurrent ledger change rejects the save
  // instead of clobbering it (WooCommerce `_original_stock` parity).
  const editingOriginalStockRef = useRef<number | null>(null);
  // The SKU the EDIT modal was opened with — distinguishes "cleared the code"
  // (send null -> remove) from "left untouched" (send nothing).
  const editingOriginalSkuRef = useRef<string | null>(null);
  // WooCommerce parity: the admin sees a low-stock alert on the products
  // page — fed by the inventory ledger's real thresholds (GET /inventory/low-stock).
  const [lowStockAlerts, setLowStockAlerts] = useState<
    Array<{
      variant_id: string;
      available: number;
      low_stock_threshold: number;
      product_id?: string | null;
      product_name?: string | null;
      sku?: string | null;
    }> | null
  >(null);
  // Interactive low-stock panel (owner feedback on the count-only banner):
  // search inside the alert, show ALL flagged items in a scrollable list,
  // edit each one directly, and optionally filter the main table to just
  // these products.
  const [lowStockSearch, setLowStockSearch] = useState("");
  const [onlyLowStock, setOnlyLowStock] = useState(false);
  const [lowStockNames, setLowStockNames] = useState<Record<string, string>>({});
  const [productsVersion, setProductsVersion] = useState(0);
  // Collapsible low-stock panel: the owner can fold the list away to a slim
  // one-line bar and reopen it whenever needed.
  const [lowStockOpen, setLowStockOpen] = useState(true);

  // Accessories (cross-sell) editor state — loaded when editing a product.
  const [accessoryIds, setAccessoryIds] = useState<string[]>([]);
  const [accessoryOptions, setAccessoryOptions] = useState<ApiProductAccessory[]>([]);
  // First variant of the product being edited — the edit path applies USD
  // prices with a variant PATCH (the product PATCH carries no USD fields).
  const [primaryVariantId, setPrimaryVariantId] = useState<string | null>(null);

  // Specification sheet + tags. Loaded when editing; empty when creating.
  const [attributeDrafts, setAttributeDrafts] = useState<ProductAttributeDraft[]>([]);
  // Variation manager (woo-variation-swatches parity): one product, N
  // purchasable options on the same page.
  const [variation, setVariation] = useState<VariationManagerValue>({
    attributeId: null,
    drafts: [],
  });
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
      // The list endpoint defaults to page_size=20. The admin table owns
      // client-side search/filter/select across the whole catalogue, so the
      // page must hold every product — otherwise "20 of 3,822" is shown and
      // a product outside the first page is invisible and unfindable. The
      // backend caps page_size at 100, so page through until has_next=false.
      const PAGE = 100;
      const items: any[] = [];
      let page = 1;
      for (;;) {
        const res = await apiClient.get("/catalog/products", {
          params: { page, page_size: PAGE },
        });
        const chunk = Array.isArray(res.data?.items) ? res.data.items : [];
        items.push(...chunk);
        const meta = res.data?.meta ?? {};
        if (!meta.has_next || chunk.length === 0 || page >= (meta.total_pages ?? page)) break;
        page += 1;
      }
      return items.map((p: any): AdminProduct => ({
        id: String(p.id),
        name: p.title || p.name,
        slug: p.slug || "",
        description: p.description || "",
        categoryId: p.category_id ? String(p.category_id) : "",
        category: p.category_name || p.category?.name || "—",
        brand: p.brand?.name || p.brand || "—",
        price: p.price ?? 0,
        compareAtPrice: p.original_price || p.compare_at_price || null,
        sku: p.sku || "",
        weight: p.weight ?? 0,
        imageUrl: p.thumbnail || p.images?.[0]?.url || p.images?.[0] || "",
        imageAlt: p.images?.[0]?.alt_text || "",
        // `?? 0`, not `?? 10`: a missing stock field means "not reported",
        // and inventing 10 puts phantom inventory on screen. A NULL stock
        // means untracked/unlimited — availability then comes from
        // stock_status, never from a coerced 0.
        stock: p.stock ?? p.stock_count ?? 0,
        stockTracked: (p.stock ?? p.stock_count) != null,
        stockStatus: p.stock_status === "outofstock" ? "outofstock" : "instock",
        lowStockThreshold: p.low_stock_threshold ?? null,
        status:
          p.is_active === false
            ? "draft"
            : (p.stock ?? p.stock_count) == null
              ? // Untracked: manual availability (وضعیت عرضه) decides.
                p.stock_status === "outofstock"
                ? "out_of_stock"
                : "active"
              : (p.stock ?? p.stock_count ?? 0) === 0
                ? "out_of_stock"
                : "active",
        // Raw publish status for the edit PATCH — see rawStatus on the type.
        rawStatus: p.status === "draft" || p.status === "archived" ? p.status : "active",
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
    // "فقط این‌ها" از پنل هشدار کمبود: جدول به کالاهای زیر آستانه محدود شود.
    const lowStockProductIds =
      onlyLowStock && lowStockAlerts
        ? new Set(
            lowStockAlerts
              .map((a) => a.product_id)
              .filter((id): id is string => Boolean(id)),
          )
        : null;
    return products.filter((item) => {
      if (lowStockProductIds && !lowStockProductIds.has(item.id)) return false;
      // 1. Search Query
      const query = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !query ||
        item.name.toLowerCase().includes(query) ||
        item.sku.toLowerCase().includes(query) ||
        item.brand.toLowerCase().includes(query) ||
        // Slug too: the admin bar's contextual "edit product" link arrives
        // with the storefront URL's slug, and a filter that only matched
        // names would show an empty list for a product that plainly exists.
        (item.slug ?? "").toLowerCase().includes(query);

      // 2. Category Filter
      const matchesCategory =
        selectedCategory === "all" ||
        selectedCategory === "همه دسته‌بندی‌ها" ||
        item.categoryId === selectedCategory ||
        item.category === selectedCategory;

      // 3. Status Filter — untracked products match by their manual
      // availability (stockStatus), not by a coerced zero count.
      const itemInStock = item.stockTracked
        ? item.stock > 0
        : item.stockStatus === "instock";
      const itemOutOfStock = item.stockTracked
        ? item.stock === 0
        : item.stockStatus === "outofstock";
      const matchesStatus =
        selectedStatus === "all" ||
        (selectedStatus === "in_stock" && itemInStock) ||
        (selectedStatus === "out_of_stock" && itemOutOfStock) ||
        item.status === selectedStatus;

      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [products, searchQuery, selectedCategory, selectedStatus, onlyLowStock, lowStockAlerts]);

  /* ---------------------------------------------------------------- */
  /*  Bulk actions (DataTable's built-in selection — same bar as the   */
  /*  orders/users lists, with the select-all checkbox in the header)  */
  /* ---------------------------------------------------------------- */

  /**
   * Bulk publish / unpublish / feature. Only the fields the backend
   * validates are sent — nothing money-related is in this payload.
   *
   * The endpoint answers with a count, not a per-row result: a count below
   * the selection size means some ids matched no product, and saying
   * "done" without that would be a lie about how much was changed.
   */
  const runBulkPatch = async (
    rows: AdminProduct[],
    patch: { is_active?: boolean; is_featured?: boolean },
    label: string,
  ) => {
    try {
      const result = await adminBulkApi.bulkUpdateProducts(
        rows.map((p) => ({ id: p.id, ...patch })),
      );
      if (result.updated < rows.length) {
        toast({
          title: "انجام شد با خطا",
          description: `موفق: ${toPersianDigits(String(result.updated))} — ناموفق: ${toPersianDigits(String(rows.length - result.updated))}`,
          variant: "destructive",
        });
      } else {
        toast({
          title: `${label} انجام شد`,
          description: `${toPersianDigits(String(result.updated))} محصول`,
        });
      }
      await reloadProducts();
          setProductsVersion((v) => v + 1);
      return true;
    } catch {
      toast({ title: "عملیات گروهی ناموفق بود", variant: "destructive" });
      return false;
    }
  };

  const productBulkActions: BulkAction<AdminProduct>[] = [
    {
      id: "activate",
      label: "فعال‌سازی",
      confirm: (rows) => `${toPersianDigits(String(rows.length))} محصول فعال شود؟`,
      onRun: (rows) => runBulkPatch(rows, { is_active: true }, "فعال‌سازی"),
    },
    {
      id: "deactivate",
      label: "غیرفعال‌سازی",
      confirm: (rows) => `${toPersianDigits(String(rows.length))} محصول غیرفعال شود؟`,
      onRun: (rows) => runBulkPatch(rows, { is_active: false }, "غیرفعال‌سازی"),
    },
    {
      id: "feature",
      label: "ویژه",
      confirm: (rows) => `${toPersianDigits(String(rows.length))} محصول ویژه شود؟`,
      onRun: (rows) => runBulkPatch(rows, { is_featured: true }, "انتخاب به‌عنوان ویژه"),
    },
    {
      id: "unfeature",
      label: "حذف از ویژه‌ها",
      confirm: (rows) => `${toPersianDigits(String(rows.length))} محصول از ویژه‌ها حذف شود؟`,
      onRun: (rows) => runBulkPatch(rows, { is_featured: false }, "حذف از ویژه‌ها"),
    },
    {
      id: "delete",
      label: "حذف",
      variant: "destructive",
      confirm: (rows) =>
        `${toPersianDigits(String(rows.length))} محصول به‌طور کامل از کاتالوگ حذف می‌شوند. این عمل غیرقابل بازگشت است.`,
      onRun: async (rows) => {
        try {
          const result = await adminBulkApi.bulkDeleteProducts(rows.map((p) => p.id));
          if (result.deleted < rows.length) {
            toast({
              title: "حذف کامل نشد",
              description: `حذف‌شده: ${toPersianDigits(String(result.deleted))} — ناموفق: ${toPersianDigits(String(rows.length - result.deleted))}`,
              variant: "destructive",
            });
          } else {
            toast({
              title: "محصولات حذف شدند",
              description: `${toPersianDigits(String(result.deleted))} محصول`,
            });
          }
          await reloadProducts();
          setProductsVersion((v) => v + 1);
          return true;
        } catch {
          toast({ title: "حذف گروهی ناموفق بود", variant: "destructive" });
          return false;
        }
      },
    },
  ];

  /* ---------------------------------------------------------------- */
  /*  Modal Open / Form Handlers                                       */
  /* ---------------------------------------------------------------- */

  /**
   * ?new=1 opens the add dialog.
   *
   * The admin bar links here rather than to a route that does not exist, so the
   * parameter has to actually do something — a link that lands on the plain
   * page is a button that silently does nothing.
   *
   * The guard flag is what stops the loop: without it, opening the dialog (or
   * any re-render) would re-run the effect and reset a half-filled form.
   */
  const newParam = useSearchParams()?.get("new");
  // `?search=` seeds the filter box. The admin bar's contextual "ویرایش محصول"
  // link lands here with the slug, so the operator sees the product they were
  // looking at instead of the full catalogue. Read once on mount: re-seeding
  // on every render would fight the operator's typing.
  const searchParam = useSearchParams()?.get("search");
  useEffect(() => {
    if (searchParam) setSearchQuery(searchParam);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [deepLinkConsumed, setDeepLinkConsumed] = useState(false);
  useEffect(() => {
    if (newParam !== "1" || deepLinkConsumed) return;
    setDeepLinkConsumed(true);
    handleOpenAddModal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newParam, deepLinkConsumed]);

  useEffect(() => {
    apiClient
      .get("/inventory/low-stock?page_size=200")
      .then((res) => setLowStockAlerts(res.data ?? []))
      .catch(() => setLowStockAlerts([]));
  }, [productsVersion]);

  const handleOpenAddModal = () => {
    setEditingProduct(null);
    const firstCat = categories[0];
    setFormData({
      name: "",
      description: "",
      categoryId: firstCat?.id || "",
      category: firstCat?.name || "",
      brand: "",
      price: "",
      compareAtPrice: "",
      // All optional warehouse fields start EMPTY: no invented SKU, no fake
      // 200 g weight, no silent "10 in stock". The operator types what is
      // true; what is left empty stays untracked/unlimited (digital-friendly).
      sku: "",
      weight: "",
      imageUrl: "",
      imageAlt: "",
      stock: "",
      manageStock: false,
      lowStockThreshold: "",
      stockStatus: "instock",
      backorderAllowed: false,
      barcode: "",
      status: "active",
      productType: "physical",
      usdPrice: "",
      usdSalePrice: "",
    });
    setAttributeDrafts([]);
    setTagIds([]);
    setVariation({ attributeId: null, drafts: [] });
    setIsProductModalOpen(true);
  };

  const handleOpenEditModal = (product: AdminProduct) => {
    setEditingProduct(product);
    setFormData({
      name: product.name,
      description: product.description,
      categoryId: product.categoryId || "",
      category: product.category,
      brand: product.brand,
      price: String(product.price),
      compareAtPrice: product.compareAtPrice ? String(product.compareAtPrice) : "",
      sku: product.sku,
      weight: product.weight ? String(product.weight) : "",
      imageUrl: product.imageUrl || "",
      imageAlt: product.imageAlt || "",
      // stock === 0 with nothing typed is ambiguous (real zero vs untracked),
      // so the detail fetch below refines manageStock/stock from the actual
      // inventory record (available: number = tracked, null = untracked).
      stock: String(product.stock ?? ""),
      manageStock: false,
      lowStockThreshold: "",
      stockStatus: "instock",
      backorderAllowed: false,
      barcode: "",
      // Raw publish status — the display `status` may say "out_of_stock"
      // (a stock-derived label) which the backend would reject with 422.
      // Whitelisted again here: any stale row whose rawStatus is missing or
      // non-standard must render a real option in the publish-status Select
      // (a blank combobox is how the operator ends up re-saving a status
      // they never chose) instead of an empty box.
      status: (["active", "draft", "archived"] as const).includes(
        product.rawStatus as "active" | "draft" | "archived",
      )
        ? (product.rawStatus as "active" | "draft" | "archived")
        : "active",
      productType: "physical",
      usdPrice: "",
      usdSalePrice: "",
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
    setVariation({ attributeId: null, drafts: [] });
    // The first variant id is needed to apply USD prices on save (the edit
    // path patches the variant directly — the product PATCH has no variant
    // fields). The detail response carries the USD values as strings.
    setPrimaryVariantId(null);
    fetchProductById(product.id)
      .then((detail) => {
        if (detail.category_id) {
          const cId = String(detail.category_id);
          const cName = detail.category?.name || categories.find((c) => c.id === cId)?.name || "";
          setFormData((prev) => ({
            ...prev,
            categoryId: cId,
            category: cName || prev.category,
          }));
        }
        setAttributeDrafts(
          (detail.product_attributes ?? []).map((pa) => ({
            attributeId: pa.attribute_id,
            value: pa.attribute_value_id,
            valueLabel: pa.attribute_value ?? "",
          })),
        );
        setTagIds((detail.tags ?? []).map((t) => t.id));
        // Variation manager prefill: groups + variants → editable rows.
        setVariation(
          draftsFromDetail(
            detail.variation_attributes ?? [],
            detail.variants ?? [],
            formData.productType === "digital" ? "digital" : "physical",
            detail.images ?? [],
          ),
        );
        const firstVariant = detail.variants?.[0];
        if (firstVariant) {
          setPrimaryVariantId(firstVariant.id);
          setFormData((prev) => ({
            ...prev,
            // The list payload carries no variant SKU — showing the field
            // empty here would make a save with the generate button look
            // like it "reset" the code. Show the real current SKU.
            sku: firstVariant.sku ?? "",
            // WooCommerce parity: the ledger's track_inventory flag IS the
            // switch. Deriving it from `typeof available === "number"` was
            // wrong — the detail mapper folds the manual وضعیت عرضه into
            // available, so an untracked product saved as ناموجود came back
            // with available=0 and the switch flipped itself on.
            manageStock: firstVariant.track_inventory === true,
            stock:
              firstVariant.track_inventory === true &&
              typeof firstVariant.available === "number"
                ? String(firstVariant.available)
                : "",
            lowStockThreshold:
              firstVariant.track_inventory === true &&
              typeof firstVariant.low_stock_threshold === "number"
                ? String(firstVariant.low_stock_threshold)
                : "",
            backorderAllowed: firstVariant.backorder_allowed === true,
            barcode: firstVariant.barcode ?? "",
            usdPrice: firstVariant.usd_price ?? "",
            usdSalePrice: firstVariant.usd_sale_price ?? "",
          }));
          // Guard input: the ledger quantity at editor-open time (tracked
          // only — untracked products have no meaningful open-time count).
          editingOriginalStockRef.current =
            firstVariant.track_inventory === true &&
            typeof firstVariant.available === "number"
              ? firstVariant.available
              : null;
          editingOriginalSkuRef.current = firstVariant.sku ?? null;
        }
        // WooCommerce "Stock status" parity — manual availability lives on
        // the product, used only when stock management is OFF.
        setFormData((prev) => ({
          ...prev,
          stockStatus: detail.stock_status === "outofstock" ? "outofstock" : "instock",
        }));
        // Product type drives the warehouse-field visibility: digital goods
        // hide SKU/weight/stock in the editor as they do on create.
        const detailType = String(detail.product_type || "simple");
        setFormData((prev) => ({
          ...prev,
          productType: detailType === "digital" ? "digital" : "physical",
        }));
      })
      .catch(() => {
        // Left empty; the spec tab simply shows no rows for this product.
      });
    setIsProductModalOpen(true);
  };

  const handleSubmitProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    // Only name and price are truly required; SKU and stock are optional by
    // design (digital goods have neither).
    const hasVariationPrices = variation.drafts.some(
      (d) => Number(d.price) > 0,
    );
    if (!formData.name.trim() || (!formData.price.trim() && !hasVariationPrices)) {
      toast({
        title: "اطلاعات ناقص است",
        description: "لطفاً نام محصول و قیمت فروش (یا قیمت گزینه‌ها) را تکمیل نمایید.",
        variant: "destructive",
      });
      return;
    }
    const isDigital = formData.productType === "digital";

    const numericPrice = parseInt(formData.price.replace(/\D/g, ""), 10) || 0;
    const numericCompareAt = formData.compareAtPrice
      ? parseInt(formData.compareAtPrice.replace(/\D/g, ""), 10)
      : null;
    // Stock semantics (WooCommerce manage-stock parity): the switch decides.
    // ON = tracked stock (empty quantity = tracked at 0, i.e. visible but
    // not buyable yet); OFF = untracked/unlimited (sent as null).
    const numericStock = formData.manageStock
      ? parseInt(formData.stock.replace(/\D/g, ""), 10) || 0
      : null;
    const lowStockThreshold =
      formData.manageStock && formData.lowStockThreshold
        ? parseInt(formData.lowStockThreshold.replace(/\D/g, ""), 10) || null
        : null;
    const numericWeight = !isDigital && formData.weight
      ? parseInt(formData.weight.replace(/\D/g, ""), 10) || 0
      : null;
    // Manual stock status only applies when stock management is OFF.
    const productStockStatus = formData.manageStock
      ? undefined
      : formData.stockStatus;
    // USD prices: null = "not managed by the sweep" (the API's clear value).
    const parseUsd = (text: string): number | null => {
      const n = Number(text.replace(/[^\d.]/g, ""));
      return Number.isFinite(n) && n > 0 ? n : null;
    };
    const usdPrice = parseUsd(formData.usdPrice);
    const usdSalePrice = parseUsd(formData.usdSalePrice);

    setIsSubmitting(true);
    try {
      let savedProductId = editingProduct?.id;
      if (editingProduct) {
        // Edit flow
        await apiClient.patch(`/catalog/products/${editingProduct.id}`, {
          name: formData.name,
          category_id: formData.categoryId || undefined,
          status: formData.status,
          is_active: formData.status === "active",
          product_type: isDigital ? "digital" : "simple",
          ...(productStockStatus ? { stock_status: productStockStatus } : {}),
          description: formData.description,
          weight: numericWeight,
          // Both are full replacement sets server-side: an empty list clears
          // them, omitting the field leaves them alone. They are always sent
          // so that clearing the editor actually clears the product.
          // Spec-sheet rows + the variation manager's checked values are ONE
          // association table server-side; merge with dedupe so saving one
          // editor never wipes the other.
          attributes: variationDraftsToPayload(
            variation.drafts,
            attributeDrafts.map((d) => ({
              attribute_id: d.attributeId,
              attribute_value_id: d.value,
            })),
          ).associations,
          // Rows with id patch, rows without create, dropped rows soft-retire
          // server-side. Omitted entirely when the manager is untouched.
          ...(variation.drafts.length > 0
            ? {
                variants: variationDraftsToPayload(variation.drafts, [])
                  .variants,
              }
            : {}),
          tag_ids: tagIds,
        });

        // USD source prices live on the VARIANT, and the product PATCH above
        // has no variant fields. Always sent (empty text sends 0 = clear,
        // the backend's "not managed" value), so clearing the editor really
        // takes the variant out of the automatic sweep.
        if (editingProduct) {
          // The detail fetch that fills primaryVariantId races a fast save:
          // if it has not landed yet, resolve the variant id here so the SKU/
          // USD patch below can never silently no-op.
          let variantIdForPatch = primaryVariantId;
          if (!variantIdForPatch) {
            try {
              const detailRes = await apiClient.get(
                `/catalog/products/${editingProduct.id}`,
              );
              variantIdForPatch =
                String(detailRes.data?.variants?.[0]?.id ?? "") || null;
              if (variantIdForPatch) setPrimaryVariantId(variantIdForPatch);
            } catch {
              /* leave null — the patch below is skipped and stays cosmetic */
            }
          }
          if (variantIdForPatch) {
            const trimmedSku = formData.sku.trim();
            try {
              await apiClient.patch(`/catalog/variants/${variantIdForPatch}`, {
                // Only send a SKU when the operator actually typed/generated
                // one and it differs from the current code — an empty field
                // means "keep the existing SKU".
                ...(editingOriginalSkuRef.current && !trimmedSku
                  ? { sku: null }
                  : trimmedSku && trimmedSku !== editingOriginalSkuRef.current
                    ? { sku: trimmedSku }
                    : {}),
                // Threshold applies only while stock management is on. A
                // cleared field sends null = the owner turned the alert OFF
                // for this product (backend stores NULL = never alert).
                ...(formData.manageStock
                  ? { low_stock_threshold: lowStockThreshold }
                  : {}),
                // Stock edit (WooCommerce parity): the typed quantity plus
                // the quantity the editor opened with — the backend rejects
                // the save when the ledger moved since (concurrent guard).
                ...(formData.manageStock
                  ? {
                      stock: numericStock ?? 0,
                      ...(editingOriginalStockRef.current !== null
                        ? { original_stock: editingOriginalStockRef.current }
                        : {}),
                    }
                  : {}),
                usd_price: usdPrice ?? 0,
                usd_sale_price: usdSalePrice ?? 0,
              });
            } catch {
              toast({
                title: "ذخیره‌ی SKU یا قیمت دلاری ناموفق بود",
                description: "محصول بروزرسانی شد اما تغییر SKU با خطا مواجه شد.",
                variant: "destructive",
              });
            }
          }
        }

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

        const matchedCat = categories.find((c) => c.id === formData.categoryId);
        setLocalProducts((prev) =>
          prev.map((p) =>
            p.id === editingProduct.id
              ? {
                  ...p,
                  name: formData.name,
                  description: formData.description,
                  categoryId: formData.categoryId,
                  category: matchedCat?.name || formData.category,
                  brand: formData.brand,
                  price: numericPrice,
                  compareAtPrice: numericCompareAt,
                  sku: formData.sku.trim(),
                  weight: numericWeight ?? 0,
                  imageUrl: formData.imageUrl,
                  stock: numericStock ?? 0,
                  // Out-of-stock only applies to *tracked* stock; null =
                  // untracked/unlimited stays buyable.
                  status:
                    numericStock !== null && numericStock === 0
                      ? "out_of_stock"
                      : formData.status,
                }
              : p
          )
        );

        toast({
          title: "محصول بروزرسانی شد",
          description: `اطلاعات «${formData.name}» ذخیره گردید.`,
          variant: "success",
        });
        // The optimistic local update races the query sync effect: with the
        // list now holding the whole catalogue, a background refetch (or the
        // next query mount) would repaint stale rows. Refetch once so the
        // table reflects the server's state — category moves included.
        void reloadProducts().then(() => {
          // The create path also refreshes the low-stock banner.
          setProductsVersion((v) => v + 1);
        });
      } else {
        // Add flow — use selected categoryId directly from dynamic categories
        const catId = formData.categoryId || categories[0]?.id;
        if (!catId) {
          toast({
            title: "دسته‌بندی نامعتبر",
            description: "لطفاً ابتدا از بخش دسته‌بندی‌ها یک دسته ایجاد نمایید.",
            variant: "destructive",
          });
          setIsSubmitting(false);
          return;
        }

        const created = await apiClient.post<{ id: string }>("/catalog/products", {
          name: formData.name,
          category_id: catId,
          status: formData.status,
          is_active: formData.status === "active",
          product_type: isDigital ? "digital" : "simple",
          ...(productStockStatus ? { stock_status: productStockStatus } : {}),
          description: formData.description,
          weight: numericWeight,
          tag_ids: tagIds,
          images: formData.imageUrl
            ? [{
                url: formData.imageUrl,
                is_primary: true,
                position: 0,
                alt_text: formData.imageAlt || formData.name || null,
              }]
            : [],
          // Spec-sheet rows + the variation manager's checked values are ONE
          // association table server-side; merge with dedupe.
          attributes: variationDraftsToPayload(
            variation.drafts,
            attributeDrafts
              .filter((d) => d.value)
              .map((d) => ({
                attribute_id: d.attributeId,
                attribute_value_id: d.value,
              })),
          ).associations,
          // A priced variation set REPLACES the single anonymous variant —
          // that is the whole point: one product page, N purchasable options.
          variants: hasVariationPrices
            ? variationDraftsToPayload(variation.drafts, []).variants
            : [
                {
                  // Empty SKU → the backend generates a unique internal one.
                  sku: formData.sku.trim() || undefined,
                  price: numericPrice,
                  compare_at_price: numericCompareAt || null,
                  is_active: true,
                  // manageStock ON → tracked at the typed count; OFF → null =
                  // untracked/unlimited (always buyable).
                  stock: numericStock,
                  // Low-stock alert threshold; undefined = store default (5).
                  low_stock_threshold: lowStockThreshold ?? undefined,
                  // WooCommerce "Allow backorders?" + global barcode (GTIN/EAN).
                  backorder_allowed: formData.manageStock
                    ? formData.backorderAllowed
                    : undefined,
                  barcode:
                    !isDigital && formData.barcode.trim()
                      ? formData.barcode.trim()
                      : undefined,
                  // USD source prices — when set, the automatic USD→Toman
                  // sweep owns the variant's Toman price from the first run.
                  usd_price: usdPrice,
                  usd_sale_price: usdSalePrice,
                },
              ],
        });

        savedProductId = String(created.data?.id ?? crypto.randomUUID());
        const catName = categories.find((c) => c.id === catId)?.name || formData.category;
        const newProduct: AdminProduct = {
          id: savedProductId,
          name: formData.name,
          description: formData.description,
          lowStockThreshold: lowStockThreshold,
          categoryId: catId,
          category: catName,
          brand: formData.brand || "متفرقه",
          price: numericPrice,
          compareAtPrice: numericCompareAt,
          sku: formData.sku.trim(),
          rawStatus: "active",
          weight: numericWeight ?? 0,
          imageUrl: formData.imageUrl,
          stock: numericStock ?? 0,
          stockTracked: numericStock !== null,
          stockStatus: productStockStatus === "outofstock" ? "outofstock" : "instock",
          // Out-of-stock only applies to *tracked* physical stock; unlimited
          // (null) and digital goods follow the manual وضعیت عرضه.
          status:
            numericStock !== null && numericStock === 0
              ? "out_of_stock"
              : productStockStatus === "outofstock"
                ? "out_of_stock"
                : formData.status,
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

  const renderStockBadge = (product: AdminProduct) => {
    // Untracked (مدیریت موجودی خاموش): WooCommerce stock-status parity —
    // the operator's manual وضعیت عرضه IS the availability; there is no
    // count to show.
    if (!product.stockTracked) {
      return product.stockStatus === "outofstock" ? (
        <Badge variant="destructive" className="gap-1 whitespace-nowrap text-[11px]">
          <XCircle className="h-3 w-3" />
          ناموجود
        </Badge>
      ) : (
        <Badge variant="success" className="gap-1 whitespace-nowrap text-[11px]">
          <CheckCircle2 className="h-3 w-3" />
          موجود
        </Badge>
      );
    }
    if (product.stock === 0) {
      return (
        <Badge variant="destructive" className="gap-1 whitespace-nowrap text-[11px]">
          <XCircle className="h-3 w-3" />
          ناموجود
        </Badge>
      );
    }
    // Same threshold as the low-stock banner/filter — the product's own
    // value from the inventory ledger, not a hardcode.
    if (product.lowStockThreshold != null && product.stock <= product.lowStockThreshold) {
      return (
        <Badge variant="warning" className="gap-1 whitespace-nowrap text-[11px]">
          <AlertTriangle className="h-3 w-3" />
          رو به اتمام ({toPersianDigits(product.stock)})
        </Badge>
      );
    }
    return (
      <Badge variant="success" className="gap-1 whitespace-nowrap text-[11px]">
        <CheckCircle2 className="h-3 w-3" />
        موجود ({toPersianDigits(product.stock)})
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
      key: "image",
      header: "تصویر",
      className: "w-[56px] xl:w-[80px]",
      render: (product) => (
        <div className="relative flex h-10 w-10 xl:h-12 xl:w-12 shrink-0 items-center justify-center overflow-hidden rounded-lg border bg-muted">
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
      // ONE-LINE name (owner directive — a wrapped two-line name was called
      // out twice): truncate with tooltip, no min-width forcing the cell
      // wide. The cell shrinks; the full name stays on hover via title.
      className: "max-w-[220px] xl:max-w-[280px]",
      render: (product) => (
        <div className="min-w-0">
          <p
            className="truncate font-semibold text-foreground"
            title={product.name}
          >
            {product.name}
          </p>
          <span
            className="block truncate text-[11px] text-muted-foreground"
            title={product.brand ? `برند: ${product.brand}` : undefined}
          >
            برند: {product.brand}
            {product.weight ? ` · ${toPersianDigits(product.weight)} گرم` : ""}
          </span>
        </div>
      ),
    },
    {
      key: "sku",
      header: "کد انبار (SKU)",
      className: "font-mono text-xs text-muted-foreground",
      // Owner directive: SKU must ALWAYS be visible (it was hidden below
      // 1536px and read as "the SKU column is gone"). The table has
      // overflow-x-auto, so on narrow screens it scrolls instead of
      // squeezing anything out.
      render: (product) => <span dir="auto">{product.sku}</span>,
    },
    {
      key: "category",
      header: "دسته‌بندی",
      // Same tier as SKU: at 1280 (with the sidebar) the 9-column table
      // overflowed its card ~130px; hiding both low-glance columns lets the
      // whole table fit without horizontal scrolling.
      hideBelow: "2xl",
      render: (product) => (
        // inline-block (not Badge's inline-flex): flex containers break
        // `truncate` clipping in narrow cells and the text escapes the pill.
        <div className="inline-block max-w-full truncate rounded-full border border-transparent bg-secondary px-2.5 py-1 text-xs font-normal text-secondary-foreground">
          {product.category}
        </div>
      ),
    },
    {
      key: "price",
      header: "قیمت فروش",
      render: (product) => (
        <div className="space-y-0.5">
          <span className="font-bold text-foreground block font-mono truncate" title={formatPrice(product.price)}>
            {formatPrice(product.price)}
          </span>
          {product.compareAtPrice && product.compareAtPrice > product.price && (
            <span className="text-xs text-muted-foreground line-through block font-mono truncate">
              {formatPrice(product.compareAtPrice)}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "stock",
      header: "وضعیت موجودی",
      render: (product) =>
        renderStockBadge(product),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (product) => renderStatusBadge(product.status),
    },
    {
      key: "actions",
      header: <span className="sr-only">عملیات</span>,
      className: "min-w-[112px]",
      // The action buttons stay pinned to the card's edge while the table
      // scrolls — they were the columns poking out of the card borders.
      stickyEdge: true,
      columnLabel: "عملیات",
      render: (product) => (
        // Owner directive: the three action icons stay on ONE line in every
        // viewport (no wrap-to-second-line). The min-width on the column +
        // the table's horizontal scroll absorb narrow screens instead.
        <div className="flex items-center justify-center gap-1 whitespace-nowrap">
          {/* WordPress-parity «نمایش»: open the item's public storefront page
              in a new tab straight from the list row. */}
          {product.slug && (
            <Button
              asChild
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              title={`نمایش «${product.name}» در فروشگاه`}
            >
              <a
                href={`/products/${product.slug}`}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`نمایش ${product.name} در فروشگاه`}
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          )}
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
        <Card className="flex items-center justify-between gap-2 p-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Package className="h-5 w-5" />
          </div>
          <p className="text-[11px] leading-tight text-muted-foreground">کل محصولات</p>
          <p className="text-lg font-bold text-foreground font-mono">
              {toPersianDigits(products.length)}
            </p>
        </Card>

        <Card className="flex items-center justify-between gap-2 p-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <p className="text-[11px] leading-tight text-muted-foreground">کالاهای موجود</p>
          <p className="text-lg font-bold text-emerald-600 font-mono">
              {toPersianDigits(products.filter((p) => (p.stockTracked ? p.stock > 0 : p.stockStatus === "instock")).length)}
            </p>
        </Card>

        <Card className="flex items-center justify-between gap-2 p-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
            <XCircle className="h-5 w-5" />
          </div>
          <p className="text-[11px] leading-tight text-muted-foreground">ناموجود در انبار</p>
          <p className="text-lg font-bold text-destructive font-mono">
              {toPersianDigits(products.filter((p) => (p.stockTracked ? p.stock === 0 : p.stockStatus === "outofstock")).length)}
            </p>
        </Card>

        <Card className="flex items-center justify-between gap-2 p-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-950 dark:text-blue-400">
            <Layers className="h-5 w-5" />
          </div>
          <p className="text-[11px] leading-tight text-muted-foreground">دسته‌بندی‌های فعال</p>
          <p className="text-lg font-bold text-blue-600 font-mono">
              {toPersianDigits(new Set(products.map((p) => p.category)).size)}
            </p>
        </Card>
      </div>

      {/* Filters and Search Bar */}
      <Card className="p-3">
        {/* Owner: the three filters pack to the RIGHT edge (RTL start) with
            a normal gap — justify-between stretched them across the full
            card width and left dead space between each control. */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative w-full sm:w-[220px]">
            <Search className="absolute right-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="جستجو در محصولات..."
              className="ps-9"
            />
          </div>

          {/* Category Filter */}
          <div className="w-full sm:w-[220px]">
            <Select value={selectedCategory} onValueChange={setSelectedCategory}>
              <SelectTrigger>
                <SelectValue placeholder="دسته‌بندی" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">همه دسته‌بندی‌ها</SelectItem>
                {categories.map((cat) => (
                  <SelectItem key={cat.id} value={cat.id}>
                    {cat.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Status Filter */}
          <div className="w-full sm:w-[220px]">
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

        {/* Active low-stock filter chip (set from the amber panel's toggle) */}
        {/* Reset Filter indicator */}
        {/* The low-stock chip lives INSIDE the applied-filters row (owner:
            standalone it had zero spacing and collided with the search box). */}
        {(onlyLowStock ||
          searchQuery ||
          selectedCategory !== "همه دسته‌بندی‌ها" ||
          selectedStatus !== "all") && (
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border/60 pt-2 text-xs text-muted-foreground">
            <div className="flex flex-wrap items-center gap-2">
              {onlyLowStock && (
                <Badge
                  variant="secondary"
                  className="gap-1 rounded-lg text-xs font-normal"
                >
                  <span>فقط کالاهای رو به اتمام</span>
                  <X
                    className="h-3 w-3 cursor-pointer hover:text-red-500"
                    onClick={() => setOnlyLowStock(false)}
                  />
                </Badge>
              )}
              <span>
                فیلترهای اعمال شده ({toPersianDigits(filteredProducts.length)} محصول یافت شد)
              </span>
            </div>
            <Button
              variant="link"
              size="sm"
              className="h-auto p-0 text-xs text-primary"
              onClick={() => {
                setSearchQuery("");
                setSelectedCategory("همه دسته‌بندی‌ها");
                setSelectedStatus("all");
                setOnlyLowStock(false);
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

      {/* WooCommerce parity: low-stock alert on the products page — fed by
          the inventory ledger's real thresholds (GET /inventory/low-stock). */}
      {/* Low-stock panel (WooCommerce low-stock email parity, interactive):
          lists EVERY flagged item in a scrollable, searchable list; each row
          jumps straight to its edit modal; a toggle filters the main table
          down to just these products. */}
      {lowStockAlerts && lowStockAlerts.length > 0 && (
        <div
          role="alert"
          className="rounded-2xl border border-amber-500/40 bg-amber-500/5 text-xs text-amber-700 dark:text-amber-400"
        >
          <div
            className={cn(
              "flex items-center justify-between gap-2 px-4 py-3",
              lowStockOpen && "border-b border-amber-500/20",
            )}
          >
            <button
              type="button"
              className="flex min-w-0 items-center gap-2 text-start"
              onClick={() => setLowStockOpen((v) => !v)}
              aria-expanded={lowStockOpen}
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span className="truncate font-bold">
                {toPersianDigits(lowStockAlerts.length)} کالا به آستانه‌ی کمبود
                موجودی رسیده است
              </span>
              {!lowStockOpen && (
                <span className="hidden text-amber-600/80 dark:text-amber-500/80 sm:inline">
                  — برای دیدن لیست باز کنید
                </span>
              )}
            </button>
            <div className="flex shrink-0 items-center gap-2">
              <Button
                variant={onlyLowStock ? "default" : "outline"}
                size="sm"
                className="h-7 rounded-lg px-2.5 text-[11px] font-bold"
                onClick={() => setOnlyLowStock((v) => !v)}
              >
                {onlyLowStock ? "نمایش همه کالاها" : "فقط این کالاها در جدول"}
              </Button>
              {/* Collapsible (owner request): fold the list away to a slim
                  bar, reopen anytime — the chevron toggles it. */}
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 rounded-lg"
                onClick={() => setLowStockOpen((v) => !v)}
                aria-label={lowStockOpen ? "بستن هشدار کمبود موجودی" : "باز کردن هشدار کمبود موجودی"}
                aria-expanded={lowStockOpen}
              >
                {lowStockOpen ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          {lowStockOpen && (
          <>
          <div className="px-4 pt-3">
            <div className="relative max-w-[280px]">
              <Search className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={lowStockSearch}
                onChange={(e) => setLowStockSearch(e.target.value)}
                placeholder="جست‌وجو در کالاهای رو به اتمام…"
                className="h-8 rounded-lg bg-background pe-3 ps-8 text-xs"
                aria-label="جست‌وجو در کالاهای رو به اتمام"
              />
            </div>
          </div>

          {/* Owner-approved banner layout: a fixed 3-column grid where each
              row spans its cell — name at the cell's right edge, the count
              badge and the restock button aligned at the cell's left edge.
              (A chip-flow experiment here was rejected by the owner.) */}
          <ul className="mt-2 grid max-h-72 grid-cols-1 gap-x-5 gap-y-0.5 overflow-y-auto px-2 pb-2 md:grid-cols-3">
            {lowStockAlerts
              .filter((a) => {
                const q = lowStockSearch.trim().toLowerCase();
                if (!q) return true;
                return (
                  (a.product_name ?? "").toLowerCase().includes(q) ||
                  (a.sku ?? "").toLowerCase().includes(q)
                );
              })
              .map((a) => {
                const target =
                  a.product_id != null
                    ? localProducts.find((p) => p.id === a.product_id)
                    : undefined;
                const out = a.available <= 0;
                return (
                  <li
                    key={a.variant_id}
                    className="flex items-center gap-2 rounded-xl px-2.5 py-1.5 hover:bg-amber-500/10"
                  >
                    <span className="min-w-0 flex-1 font-semibold text-foreground/90">
                      {a.product_name || "کالا"}
                    </span>
                    <div className="flex shrink-0 items-center gap-2">
                      <span
                        className={cn(
                          "inline-flex h-7 items-center rounded-full px-2.5 text-[10px] font-bold",
                          out
                            ? "bg-red-500/15 text-red-600 dark:text-red-400"
                            : "bg-amber-500/20 text-amber-700 dark:text-amber-400",
                        )}
                      >
                        {out
                          ? "ناموجود"
                          : `${toPersianDigits(a.available)} عدد باقی مانده`}
                      </span>
                      {target && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 gap-1.5 rounded-lg px-2 text-[11px] font-bold"
                          onClick={() => handleOpenEditModal(target)}
                        >
                          <Edit className="h-3 w-3" />
                          تکمیل موجودی
                        </Button>
                      )}
                    </div>
                  </li>
                );
              })}
          </ul>
          </>
          )}
        </div>
      )}

      {/* Products Table — selection (select-all checkbox + bulk bar) comes
          from DataTable's `selectable`, same as the orders/users lists. */}
      <DataTable<AdminProduct>
        columns={productColumns}
        rows={filteredProducts}
        rowKey={(p) => p.id}
        pageSize={50}
        columnVisibilityKey="admin.products.columns"
        // Small floor only: below ~640px the wrapper scrolls (unavoidable at
        // phone widths); at 884/1280 the table compresses and fits instead.
        minWidth="640px"
        selectable
        bulkActions={productBulkActions}
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
                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
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
                onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                placeholder="توضیحات تفصیلی، ویژگی‌های کلیدی، مشخصات فنی..."
                rows={3}
              />
            </div>

            {/* Category & Brand */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label>دسته‌بندی کالا</Label>
                  <button
                    type="button"
                    onClick={() => setIsQuickCatOpen(true)}
                    className="text-xs text-primary hover:underline flex items-center gap-0.5 font-medium"
                  >
                    <Plus className="h-3 w-3" />
                    دسته‌بندی جدید
                  </button>
                </div>
                <Select
                  value={formData.categoryId}
                  onValueChange={(val) => {
                    if (!val) return;
                    const found = allCategoryOptions.find((c) => c.id === val);
                    setFormData((prev) => ({
                      ...prev,
                      categoryId: val,
                      category: found?.name || prev.category,
                    }));
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="انتخاب دسته‌بندی" />
                  </SelectTrigger>
                  <SelectContent className="max-h-60 overflow-y-auto">
                    {allCategoryOptions.map((cat) => (
                      <SelectItem key={cat.id} value={cat.id}>
                        {(cat.depth || 0) > 0 ? "— ".repeat(cat.depth || 0) : ""}{cat.name}
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
                  onChange={(e) => setFormData((prev) => ({ ...prev, brand: e.target.value }))}
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
                    const raw = toEnglishDigits(e.target.value).replace(/\D/g, "");
                    setFormData((prev) => ({ ...prev, price: raw }));
                  }}
                  placeholder="مثلاً: ۱۲,۵۰۰,۰۰۰"
                  dir="auto"
                  className="font-mono text-start font-bold"
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
                    const raw = toEnglishDigits(e.target.value).replace(/\D/g, "");
                    setFormData((prev) => ({ ...prev, compareAtPrice: raw }));
                  }}
                  placeholder="اختیاری: مثلاً ۱۴,۰۰۰,۰۰۰"
                  dir="auto"
                  className="font-mono text-start"
                />
              </div>
            </div>

            {/* USD source prices — Nobitex updater. When set, the automatic
                sweep derives the Toman price from these on every run and the
                fields above become read-only inputs of that engine. */}
            <div className="space-y-2 rounded-lg border border-border bg-muted/30 p-3">
              <div className="flex items-center justify-between gap-2">
                <Label className="text-sm">قیمت دلاری (به‌روزرسانی خودکار از نرخ نوبیتکس)</Label>
                <Link
                  href="/admin/currency"
                  className="text-xs text-primary underline-offset-4 hover:underline"
                >
                  تنظیمات نرخ
                </Link>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="prodUsdPrice" className="text-xs text-muted-foreground">
                    قیمت پایه (دلار)
                  </Label>
                  <Input
                    id="prodUsdPrice"
                    inputMode="decimal"
                    value={formData.usdPrice}
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (!/^\d{0,10}(\.\d{0,2})?$/.test(raw)) return;
                      setFormData((prev) => ({ ...prev, usdPrice: raw }));
                    }}
                    placeholder="اختیاری: مثلاً 9.99"
                    dir="auto"
                    className="font-mono text-start"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="prodUsdSalePrice" className="text-xs text-muted-foreground">
                    قیمت ویژه (دلار)
                  </Label>
                  <Input
                    id="prodUsdSalePrice"
                    inputMode="decimal"
                    value={formData.usdSalePrice}
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (!/^\d{0,10}(\.\d{0,2})?$/.test(raw)) return;
                      setFormData((prev) => ({ ...prev, usdSalePrice: raw }));
                    }}
                    placeholder="اختیاری: مثلاً 7.99"
                    dir="auto"
                    className="font-mono text-start"
                  />
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground">
                با ثبت قیمت دلاری، قیمت تومانی این کالا در هر اجرای به‌روزرسانی از نرخ لحظه‌ای
                محاسبه و جایگزین می‌شود (با قیمت ویژه، به‌صورت قیمت خط‌خورده). خالی گذاشتن یعنی
                کالا تحت مدیریت خودکار نیست.
              </p>
            </div>

            {/* Product type — decides whether warehouse fields exist at all */}
            <div className="space-y-1.5">
              <Label>نوع کالا</Label>
              <Select
                value={formData.productType}
                onValueChange={(val: "physical" | "digital") =>
                  setFormData((prev) => ({ ...prev, productType: val }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب نوع کالا" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="physical">کالای فیزیکی (دارای انبار)</SelectItem>
                  <SelectItem value="digital">کالای دیجیتال (اشتراک، لایسنس، دانلود)</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-[11px] text-muted-foreground">
                کالای دیجیتال بدون کد انبار، وزن و شمارش موجودی عرضه می‌شود — مثل اشتراک‌ها و لایسنس‌ها.
              </p>
            </div>

            {/* Stock management — WooCommerce inventory-tab parity: an
                explicit switch decides whether stock is counted at all.
                OFF = untracked/unlimited supply; ON = tracked quantity with
                a low-stock alert threshold. Works for BOTH product types
                (digital goods can still be a counted batch, e.g. 100 licenses). */}
            <div className="rounded-2xl border border-border bg-card p-4 space-y-3">
              <label className="flex items-center justify-between cursor-pointer">
                <span className="flex items-center gap-2 text-sm font-bold text-foreground">
                  <PackageCheck className="h-4 w-4 text-emerald-500" />
                  مدیریت موجودی
                </span>
                <Switch
                  checked={formData.manageStock}
                  onCheckedChange={(checked: boolean) =>
                    setFormData((prev) => ({
                      ...prev,
                      manageStock: checked,
                      // Reset stale numbers when switching modes so an old
                      // quantity can never silently re-enable tracking.
                      stock: checked ? prev.stock : "",
                      lowStockThreshold: checked ? prev.lowStockThreshold : "",
                    }))
                  }
                  aria-label="مدیریت موجودی"
                />
              </label>
              <p className="text-[11px] text-muted-foreground">
                {formData.manageStock
                  ? "موجودی شمرده می‌شود. آستانه‌ی هشدار را پر کنید تا هنگام کمبود مطلع شوید؛ خالی یعنی بدون هشدار."
                  : "این کالا بدون شمارش انبار عرضه می‌شود؛ وضعیت آن را دستی مشخص کنید."}
              </p>
              {!formData.manageStock && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">وضعیت عرضه:</span>
                  {(["instock", "outofstock"] as const).map((st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() =>
                        setFormData((prev) => ({ ...prev, stockStatus: st }))
                      }
                      className={cn(
                        "rounded-full px-3 py-1 text-xs font-bold transition-colors",
                        formData.stockStatus === st
                          ? st === "instock"
                            ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                            : "bg-red-500/15 text-red-600 dark:text-red-400"
                          : "bg-muted text-muted-foreground hover:bg-muted/70",
                      )}
                    >
                      {st === "instock" ? "موجود" : "ناموجود"}
                    </button>
                  ))}
                </div>
              )}
              {formData.manageStock && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="prodStock">تعداد موجودی</Label>
                    <Input
                      id="prodStock"
                      value={formData.stock}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          stock: toEnglishDigits(e.target.value).replace(/\D/g, ""),
                        }))
                      }
                      placeholder="مثلاً: ۱۰۰ — صفر یعنی فعلاً ناموجود"
                      dir="auto"
                      className="font-mono text-start"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="prodLowStock">آستانه‌ی هشدار کمبود (اختیاری)</Label>
                    <Input
                      id="prodLowStock"
                      value={formData.lowStockThreshold}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          lowStockThreshold: toEnglishDigits(e.target.value).replace(/\D/g, ""),
                        }))
                      }
                      placeholder="خالی = بدون هشدار"
                      dir="auto"
                      className="font-mono text-start"
                    />
                  </div>
                </div>
              )}
              {formData.manageStock && (
                <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                  <Checkbox
                    checked={formData.backorderAllowed}
                    onCheckedChange={(checked: boolean | "indeterminate") =>
                      setFormData((prev) => ({
                        ...prev,
                        backorderAllowed: checked === true,
                      }))
                    }
                  />
                  اجازه‌ی پیش‌خرید: پس از صفر شدن موجودی هم قابل خرید بماند
                </label>
              )}
            </div>

            {/* SKU & Weight — physical only. Digital goods skip the warehouse
                code and weight entirely (WooCommerce virtual parity). */}
            {formData.productType === "digital" ? (
              <div className="flex items-start gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-xs text-emerald-700 dark:text-emerald-400">
                <PackageCheck className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  کالای دیجیتال: کد انبار و وزن ندارد. برای عرضه‌ی محدود
                  (مثلاً ۱۰۰ لایسنس) از سوییچ «مدیریت موجودی» استفاده کنید.
                </span>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <Label htmlFor="prodSku">کد انبار (SKU)</Label>
                  <div className="flex gap-1.5">
                    <Input
                      id="prodSku"
                      value={formData.sku}
                      onChange={(e) => setFormData((prev) => ({ ...prev, sku: e.target.value }))}
                      placeholder="مثلاً: SAM-A54-256"
                      dir="auto"
                      className="font-mono text-start"
                    />
                    {/* Owner: some products DO need a code, but nobody should
                        have to invent one by hand — one click generates it. */}
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="shrink-0 rounded-xl border-border"
                      title="تولید کد تصادفی"
                      aria-label="تولید کد تصادفی SKU"
                      onClick={() =>
                        setFormData((prev) => ({ ...prev, sku: makeRandomSku() }))
                      }
                    >
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    اختیاری — خالی یعنی بدون کد انبار. در ویرایش، پاک‌کردنش کد
                    فعلی را حذف می‌کند.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="prodWeight">وزن تقریبی (گرم)</Label>
                  <Input
                    id="prodWeight"
                    value={formData.weight}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        weight: toEnglishDigits(e.target.value).replace(/\D/g, ""),
                      }))
                    }
                    placeholder="اختیاری"
                    dir="auto"
                    className="font-mono text-start"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="prodBarcode">بارکد / شناسه جهانی</Label>
                  <Input
                    id="prodBarcode"
                    value={formData.barcode}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, barcode: e.target.value }))
                    }
                    placeholder="GTIN/EAN/UPC"
                    dir="auto"
                    className="font-mono text-start"
                  />
                </div>
              </div>
            )}

            {/* Product image — media library, same swap as the blog cover */}
            <div className="space-y-1.5">
              <Label htmlFor="prodImage">تصویر محصول</Label>
              <MediaPicker
                value={formData.imageUrl}
                onChange={(url) => setFormData((prev) => ({ ...prev, imageUrl: url }))}
                label="تصویر محصول"
              />
              <Input
                value={formData.imageAlt}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, imageAlt: e.target.value }))
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
                onValueChange={(val: any) => setFormData((prev) => ({ ...prev, status: val }))}
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

            {/* woo-variation-swatches parity: purchasable options on ONE
                product page — 60/325/660 UC shape — instead of N duplicate
                products diluting SEO across N links. */}
            <VariationManager
              value={variation}
              onChange={setVariation}
              productType={
                formData.productType === "digital" ? "digital" : "physical"
              }
            />

            <DialogFooter className="pt-4">
              {editingProduct && (
                <Button
                  type="button"
                  variant="outline"
                  className="gap-2"
                  onClick={() => setAddonsEditorOpen(true)}
                >
                  <BoxesIcon className="h-4 w-4 text-primary" />
                  فیلدهای سفارشی محصول
                </Button>
              )}
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
      {/* MODAL: Product Add-ons Editor (WooCommerce Product Add-ons)    */}
      {/* ============================================================== */}
      <ProductAddonsEditor
        productId={editingProduct?.id ?? null}
        productName={editingProduct?.name ?? ""}
        open={addonsEditorOpen}
        onOpenChange={setAddonsEditorOpen}
      />

      {/* ============================================================== */}
      {/* MODAL: Quick Add Category (Inline from Product Form)           */}
      {/* ============================================================== */}
      <Dialog open={isQuickCatOpen} onOpenChange={setIsQuickCatOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>افزودن سریع دسته‌بندی</DialogTitle>
            <DialogDescription>
              دسته‌بندی جدید ایجاد شده و بلافاصله برای این محصول انتخاب می‌شود.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label className="text-xs font-medium">عنوان دسته‌بندی *</Label>
              <Input
                value={quickCatName}
                onChange={(e) => setQuickCatName(e.target.value)}
                placeholder="مثال: قاب و محافظ صفحه"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs font-medium">نامک (Slug)</Label>
              <Input
                value={quickCatSlug}
                onChange={(e) => setQuickCatSlug(e.target.value)}
                placeholder="مثال: phone-cases"
                dir="auto"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs font-medium">دسته‌بندی والد</Label>
              {/* Radix items can't carry an empty value, so the root option
                  round-trips through the "__root__" sentinel. */}
              <Select
                value={quickCatParentId || "__root__"}
                onValueChange={(v) => setQuickCatParentId(v === "__root__" ? "" : v)}
              >
                <SelectTrigger className="w-full" aria-label="دسته‌بندی والد">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__root__">بدون والد (دسته اصلی)</SelectItem>
                  {categories.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {(c.depth || 0) > 0 ? "— ".repeat(c.depth || 0) : ""}{c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:justify-start">
            <Button onClick={handleQuickAddCategory} disabled={isSavingQuickCat || !quickCatName.trim()}>
              {isSavingQuickCat ? "در حال ثبت..." : "افزودن و انتخاب"}
            </Button>
            <Button variant="outline" onClick={() => setIsQuickCatOpen(false)}>
              انصراف
            </Button>
          </DialogFooter>
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
