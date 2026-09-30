"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import Image from "next/image";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Search,
  Filter,
  SlidersHorizontal,
  X,
  Check,
  Package,
  ShoppingCart,
  ArrowUpDown,
  RotateCcw,
  Sparkles,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import { useCart } from "@/hooks/use-cart";
import { LiveSearchBar } from "@/components/search/live-search-bar";
import ContentResults from "@/components/search/content-results";
import { SearchResultsSkeleton } from "@/components/shared/skeleton-loaders";
import {
  normalizePersianSearch,
  type SearchSortOption,
} from "@/lib/search";
import {
  fetchProducts,
  fetchCategories,
  type ApiProduct,
  type ApiCategory,
  type ApiPaginationMeta,
} from "@/lib/api/services";

export default function SearchPage() {
  const { toast } = useToast();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { addToCart } = useCart();

  const rawQuery = searchParams.get("q") || "";
  const initialCategory = searchParams.get("category") || "all";
  const initialSort = (searchParams.get("sort") as SearchSortOption) || "newest";
  const initialInStock = searchParams.get("in_stock") === "true";
  const initialMinPrice = searchParams.get("min_price") ? Number(searchParams.get("min_price")) : undefined;
  const initialMaxPrice = searchParams.get("max_price") ? Number(searchParams.get("max_price")) : undefined;

  const [searchQuery, setSearchQuery] = useState(rawQuery);
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);
  const [selectedSort, setSelectedSort] = useState<SearchSortOption>(initialSort);
  const [inStockOnly, setInStockOnly] = useState(initialInStock);
  const [minPrice, setMinPrice] = useState<string>(initialMinPrice ? String(initialMinPrice) : "");
  const [maxPrice, setMaxPrice] = useState<string>(initialMaxPrice ? String(initialMaxPrice) : "");

  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [pagination, setPagination] = useState<ApiPaginationMeta | null>(null);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [apiError, setApiError] = useState<boolean>(false);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  // Sync state if query in URL changes
  useEffect(() => {
    setSearchQuery(rawQuery);
  }, [rawQuery]);

  // Load categories
  useEffect(() => {
    async function loadCats() {
      try {
        const res = await fetchCategories({ is_active: true, page_size: 50 });
        if (res.items) {
          setCategories(res.items);
        }
      } catch {
        // Keep empty if API fails
      }
    }
    loadCats();
  }, []);

  // Fetch products
  const loadProducts = useCallback(async () => {
    setIsLoading(true);
    setApiError(false);
    try {
      const normalized = normalizePersianSearch(searchQuery);
      const res = await fetchProducts({
        q: normalized || undefined,
        category_id: selectedCategory !== "all" ? selectedCategory : undefined,
        in_stock_only: inStockOnly || undefined,
        sort_by: selectedSort === "price_asc" || selectedSort === "price_desc" ? "price" : "created_at",
        sort_order: selectedSort === "price_asc" ? "asc" : "desc",
        page,
        page_size: 20,
      });

      if (res.items) {
        setProducts(res.items);
      }
      setPagination(res.meta ?? null);
    } catch {
      setProducts([]);
      setPagination(null);
      setApiError(true);
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, selectedCategory, inStockOnly, selectedSort, page]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  // Any filter change must land back on page 1: staying on page 5 of the old
  // result set while the new one has two pages shows an empty grid with no
  // indication that anything exists.
  useEffect(() => {
    setPage(1);
  }, [searchQuery, selectedCategory, inStockOnly, selectedSort, minPrice, maxPrice]);

  // Resolve a category's display name from the loaded categories list.
  const categoryName = useCallback(
    (categoryId: string) => categories.find((c) => c.id === categoryId)?.name || "",
    [categories],
  );

  // Client-side price filtering & sorting refinement.
  // The list API exposes a variant price range (min_price/max_price) — there is
  // no scalar price or stock on ProductResponse, so filtering uses min_price.
  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      const price = p.min_price ?? 0;
      const min = minPrice ? Number(minPrice) : null;
      const max = maxPrice ? Number(maxPrice) : null;

      if (min !== null && !isNaN(min) && price < min) return false;
      if (max !== null && !isNaN(max) && price > max) return false;
      if (selectedCategory !== "all" && p.category_id !== selectedCategory) return false;

      return true;
    }).sort((a, b) => {
      const aPrice = a.min_price ?? 0;
      const bPrice = b.min_price ?? 0;
      if (selectedSort === "price_asc") return aPrice - bPrice;
      if (selectedSort === "price_desc") return bPrice - aPrice;
      return 0; // Default newest
    });
  }, [products, minPrice, maxPrice, selectedCategory, selectedSort]);

  const handleApplyFilterUrl = () => {
    const params = new URLSearchParams();
    if (searchQuery.trim()) params.set("q", searchQuery.trim());
    if (selectedCategory !== "all") params.set("category", selectedCategory);
    if (selectedSort !== "newest") params.set("sort", selectedSort);
    if (inStockOnly) params.set("in_stock", "true");
    if (minPrice) params.set("min_price", minPrice);
    if (maxPrice) params.set("max_price", maxPrice);

    router.replace(`/search?${params.toString()}`);
  };

  const handleResetFilters = () => {
    setSelectedCategory("all");
    setSelectedSort("newest");
    setInStockOnly(false);
    setMinPrice("");
    setMaxPrice("");
    router.replace(`/search${searchQuery ? `?q=${encodeURIComponent(searchQuery)}` : ""}`);
  };

  const handleAddToCartClick = async (p: ApiProduct) => {
    try {
      await addToCart({
        productId: p.id,
        title: p.name,
        slug: p.slug,
        price: p.min_price || 0,
        originalPrice:
          p.max_price && p.max_price > (p.min_price || 0)
            ? p.max_price
            : undefined,
        image: p.primary_image_url || undefined,
      });
      toast({
        title: "به سبد خرید اضافه شد",
        description: `${p.name} با موفقیت در سبد ثبت گردید.`,
      });
    } catch {
      toast({
        title: "خطا",
        description: "امکان افزودن کالا به سبد خرید وجود نداشت.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl" dir="rtl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-6">
        <Link href="/" className="hover:text-foreground">خانه</Link>
        <span>/</span>
        <span className="text-foreground font-medium">جستجوی کالاها</span>
      </div>

      {/* Top Search Banner */}
      <div className="mb-8 rounded-3xl bg-gradient-to-l from-primary/10 via-card to-background p-6 border border-border">
        <div className="max-w-2xl mx-auto space-y-4 text-center">
          <h1 className="text-2xl md:text-3xl font-black text-foreground">
            جستجوی زنده و پیشرفته کالاها
          </h1>
          <p className="text-xs md:text-sm text-muted-foreground">
            پشتیبانی از نیم‌فاصله فارسی، فیلترهای آنی قیمت و دسته‌بندی با رهگیری سریع
          </p>
          <div className="pt-2">
            <LiveSearchBar
              placeholder="جستجوی نام کالا، برند یا مشخصات فنی..."
              onSearchSubmit={(q) => {
                setSearchQuery(q);
                router.push(`/search?q=${encodeURIComponent(q)}`);
              }}
            />
          </div>
        </div>
      </div>

      {/* Content results (blog posts + CMS pages). The product grid below only
          covers the catalogue, so without this a search for a support article
          or a policy page returned nothing at all. */}
      <ContentResults query={searchQuery} />

      {/* Main Grid Layout: Sidebar Filters + Results */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Desktop Sidebar Filters */}
        <div className="hidden lg:block space-y-6">
          <Card className="p-5 space-y-6">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <span className="flex items-center gap-2 font-bold text-sm text-foreground">
                <Filter className="h-4 w-4 text-primary" />
                فیلترهای جستجو
              </span>
              <button
                type="button"
                onClick={handleResetFilters}
                className="text-[11px] text-muted-foreground hover:text-destructive transition-colors flex items-center gap-1"
              >
                <RotateCcw className="h-3 w-3" />
                حذف فیلترها
              </button>
            </div>

            {/* Category Filter */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold">دسته‌بندی</Label>
              <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                <SelectTrigger aria-label="فیلتر دسته‌بندی" className="text-xs">
                  <SelectValue placeholder="همه دسته‌ها" />
                </SelectTrigger>
                <SelectContent dir="rtl">
                  <SelectItem value="all">همه دسته‌ها</SelectItem>
                  {categories.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* In-Stock Toggle */}
            <div className="flex items-center justify-between pt-2 border-t border-border/60">
              <span className="text-xs font-semibold text-foreground">فقط کالاهای موجود</span>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={inStockOnly}
                  onChange={(e) => setInStockOnly(e.target.checked)}
                  aria-label="فقط کالاهای موجود"
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
              </label>
            </div>

            {/* Price Range */}
            <div className="space-y-3 pt-2 border-t border-border/60">
              <Label className="text-xs font-semibold block">محدوده قیمت (تومان)</Label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[10px] text-muted-foreground block mb-1">از:</span>
                  <Input
                    type="number"
                    placeholder="مثلاً ۱۰۰,۰۰۰"
                    value={minPrice}
                    onChange={(e) => setMinPrice(e.target.value)}
                    dir="ltr"
                    className="text-xs font-mono"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-muted-foreground block mb-1">تا:</span>
                  <Input
                    type="number"
                    placeholder="مثلاً ۵۰,۰۰۰,۰۰۰"
                    value={maxPrice}
                    onChange={(e) => setMaxPrice(e.target.value)}
                    dir="ltr"
                    className="text-xs font-mono"
                  />
                </div>
              </div>
            </div>

            <Button
              onClick={handleApplyFilterUrl}
              className="w-full text-xs font-bold gap-1.5"
            >
              <Check className="h-3.5 w-3.5" />
              اعمال فیلترها
            </Button>
          </Card>
        </div>

        {/* Results Area */}
        <div className="lg:col-span-3 space-y-6">
          {/* Top Results Bar: Count & Sorting */}
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-xs">
              <span className="font-bold text-foreground">
                نتایج جستجو برای:
              </span>
              <span className="font-semibold text-primary">
                «{searchQuery || "همه محصولات"}»
              </span>
              <Badge variant="secondary" className="font-mono text-[11px] ms-2">
                {/* The server's total, not this page's row count: a cap at 60
                    made the badge read "60 کالا" for a catalogue of 5,000. */}
                {toPersianDigits(pagination?.total ?? filteredProducts.length)} کالا
              </Badge>
            </div>

            {/* Sorting */}
            <div className="flex items-center gap-2 text-xs">
              <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-muted-foreground whitespace-nowrap">مرتب‌سازی:</span>
              <Select value={selectedSort} onValueChange={(val: SearchSortOption) => setSelectedSort(val)}>
                <SelectTrigger aria-label="مرتب‌سازی نتایج جستجو" className="w-36 text-xs h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent dir="rtl">
                  <SelectItem value="newest">جدیدترین</SelectItem>
                  <SelectItem value="price_asc">ارزان‌ترین</SelectItem>
                  <SelectItem value="price_desc">گران‌ترین</SelectItem>
                  <SelectItem value="popular">محبوب‌ترین</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Product Grid */}
          {isLoading ? (
            <SearchResultsSkeleton count={6} />
          ) : apiError ? (
            <Card className="p-12 text-center space-y-4" role="alert" aria-live="assertive">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                <AlertTriangle className="h-8 w-8" />
              </div>
              <h3 className="text-base font-bold text-foreground">
                خطا در دریافت اطلاعات از سرور
              </h3>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto leading-relaxed">
                ارتباط با سرور برقرار نشد. لطفاً اتصال اینترنت خود را بررسی کرده و مجدداً تلاش کنید.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={loadProducts}
                className="text-xs gap-1.5"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                تلاش مجدد
              </Button>
            </Card>
          ) : filteredProducts.length === 0 ? (
            <Card className="p-12 text-center space-y-4">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <Package className="h-8 w-8" />
              </div>
              <h3 className="text-base font-bold text-foreground">
                هیچ کالایی مطابق با جستجوی شما یافت نشد!
              </h3>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto leading-relaxed">
                لطفاً املای کلمات را بررسی کنید، از کلمات کلیدی عام‌تر استفاده نمایید یا فیلترهای قیمت و دسته‌بندی را تغییر دهید.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleResetFilters}
                className="text-xs gap-1.5"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                حذف همه فیلترها
              </Button>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
              {filteredProducts.map((p) => {
                const price = p.min_price || 0;
                const originalPrice =
                  p.max_price && p.max_price > price ? p.max_price : undefined;
                const catName = categoryName(p.category_id);
                return (
                  <Card
                    key={p.id}
                    className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-card p-4 transition-all hover:shadow-lg hover:border-primary/40"
                  >
                    <div>
                      {/* Product Image */}
                      <Link href={`/products/${p.slug || p.id}`}>
                        <div className="relative mb-3 h-48 w-full overflow-hidden rounded-xl bg-muted/30">
                          {p.primary_image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={p.primary_image_url}
                              alt={p.name}
                              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                              <Package className="h-10 w-10" />
                            </div>
                          )}
                        </div>
                      </Link>

                      {/* Category & Title */}
                      <div className="space-y-1.5 mb-3">
                        {catName && (
                          <span className="text-[11px] text-muted-foreground block">
                            {catName}
                          </span>
                        )}
                        <Link href={`/products/${p.slug || p.id}`}>
                          <h3 className="text-sm font-bold text-foreground line-clamp-2 leading-snug group-hover:text-primary transition-colors">
                            {p.name}
                          </h3>
                        </Link>
                      </div>
                    </div>

                    {/* Price & Add to Cart Footer */}
                    <div className="pt-3 border-t border-border/50 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          {originalPrice && (
                            <span className="text-[11px] line-through text-muted-foreground block font-mono" dir="ltr">
                              {formatPrice(originalPrice)}
                            </span>
                          )}
                          <span className="text-sm font-black text-foreground font-mono" dir="ltr">
                            {formatPrice(price)}
                          </span>
                        </div>
                      </div>

                      <Button
                        size="sm"
                        onClick={() => handleAddToCartClick(p)}
                        className="w-full text-xs font-bold gap-1.5 rounded-xl h-9"
                      >
                        <ShoppingCart className="h-3.5 w-3.5" />
                        افزودن به سبد
                      </Button>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}

          {pagination && pagination.total_pages > 1 && !apiError && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1 || isLoading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="gap-1"
              >
                <ChevronRight className="w-4 h-4" />
                صفحه قبل
              </Button>
              <span className="text-sm text-muted-foreground px-4">
                صفحه {toPersianDigits(page)} از {toPersianDigits(pagination.total_pages)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= pagination.total_pages || isLoading}
                onClick={() => setPage((p) => Math.min(pagination.total_pages, p + 1))}
                className="gap-1"
              >
                صفحه بعد
                <ChevronLeft className="w-4 h-4" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
