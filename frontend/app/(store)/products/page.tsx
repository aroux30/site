"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import Image from "next/image";
import { useSearchParams } from "next/navigation";
import {
  Search,
  SlidersHorizontal,
  X,
  Package,
  Check,
  ShoppingCart,
  ChevronRight,
  ChevronLeft,
  RotateCcw,
  Sparkles,
  Eye,
  ArrowLeftRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { formatPrice, toPersianDigits, cn } from "@/lib/utils";
import { playAddToCartChime } from "@/lib/audio-effects";
import { useCart } from "@/hooks/use-cart";
import { useFacetedSearch } from "@/hooks/use-faceted-search";
import { useToast } from "@/components/ui/use-toast";
import { useCompareStore } from "@/stores/compare-store";
import type { Product } from "@/types/product";
import { FacetedFilter } from "@/components/search/faceted-filter";
import { RemoteImage } from "@/components/shared/remote-image";
import type { FacetedSearchHit } from "@/lib/api/services";

/* -------------------------------------------------------------------------- */
/*         No fallback product data — fabricated demo products with           */
/*         fake prices must never be shown to real customers.                 */
/* -------------------------------------------------------------------------- */

const sortOptions = [
  { value: "relevance", label: "مرتبط‌ترین" },
  { value: "newest", label: "جدیدترین" },
  { value: "price_asc", label: "ارزان‌ترین" },
  { value: "price_desc", label: "گران‌ترین" },
  { value: "rating", label: "محبوب‌ترین" },
];

/* -------------------------------------------------------------------------- */
/*                               Product Card                                 */
/* -------------------------------------------------------------------------- */

function ProductCard({ product }: { product: FacetedSearchHit }) {
  const { addToCart } = useCart();
  const { toast } = useToast();
  const { isInCompare, toggleProduct } = useCompareStore();
  const [added, setAdded] = useState(false);
  const [quickViewOpen, setQuickViewOpen] = useState(false);

  const inCompare = isInCompare(product.id);

  const handleToggleCompare = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const compareItem: Product = {
      id: product.id,
      title: product.name,
      slug: product.slug,
      description: product.short_description || "",
      shortDescription: product.short_description || undefined,
      price: product.price || 0,
      originalPrice:
        product.compare_at_price && product.compare_at_price > (product.price || 0)
          ? product.compare_at_price
          : undefined,
      sku: product.id,
      stock: 10,
      isActive: product.is_active,
      isFeatured: product.is_featured,
      images: product.image_url
        ? [
            {
              id: "img-primary",
              url: product.image_url,
              alt: product.name,
              order: 1,
            },
          ]
        : [],
      thumbnail: product.image_url || undefined,
      categoryId: "cat-default",
      tags: [],
      variants: [],
      attributes: [],
      type: "کالای دیجیتال",
      rating: product.rating_average ?? 4.7,
      reviewCount: product.rating_count ?? 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    toggleProduct(compareItem);
  };

  const price = product.price || 0;
  const originalPrice =
    product.compare_at_price && product.compare_at_price > price
      ? product.compare_at_price
      : undefined;
  const discount =
    originalPrice && originalPrice > price
      ? Math.round(((originalPrice - price) / originalPrice) * 100)
      : null;

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await addToCart({
        productId: product.id,
        title: product.name,
        slug: product.slug,
        price,
        originalPrice,
        image: product.image_url || undefined,
      });
    } catch (err: unknown) {
      toast({
        title: "افزودن به سبد ناموفق بود",
        description: (err as { message?: string })?.message,
        variant: "destructive",
      });
      return;
    }
    playAddToCartChime();
    setAdded(true);
    setTimeout(() => setAdded(false), 1800);
  };

  return (
    <>
      <Card className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-card transition-all duration-300 hover:-translate-y-1 hover:shadow-xl">
        <Link href={`/products/${product.slug}`} className="flex flex-col h-full">
          {/* Product Image */}
          <div className="relative aspect-square overflow-hidden bg-muted/20 p-4">
            <RemoteImage
              src={product.image_url}
              alt={product.name}
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
              className="object-contain p-2 transition-transform duration-300 group-hover:scale-105"
            />

            {/* Quick View Button */}
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setQuickViewOpen(true);
              }}
              className="absolute bottom-3 left-3 z-10 flex h-8 w-8 items-center justify-center rounded-xl bg-background/90 backdrop-blur-md text-foreground shadow-sm opacity-0 transition-opacity duration-200 group-hover:opacity-100 hover:bg-background"
              title={"مشاهده سریع"}
              aria-label={"مشاهده سریع"}
            >
              <Eye className="h-4 w-4 text-muted-foreground hover:text-primary" />
            </button>

            {/* Compare Quick Toggle */}
            <button
              type="button"
              onClick={handleToggleCompare}
              className={cn(
                "absolute bottom-3 left-12 z-10 flex h-8 w-8 items-center justify-center rounded-xl bg-background/90 backdrop-blur-md shadow-sm transition-all duration-200 hover:bg-background",
                inCompare
                  ? "opacity-100 text-primary border border-primary/30"
                  : "opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-primary",
              )}
              title={inCompare ? "حذف از مقایسه" : "افزودن به مقایسه"}
              aria-label={inCompare ? "حذف از مقایسه" : "افزودن به مقایسه"}
            >
              <ArrowLeftRight className="h-4 w-4" />
            </button>

            {discount && discount > 0 && (
              <Badge
                variant="destructive"
                className="absolute top-3 right-3 rounded-full px-2.5 py-0.5 text-xs font-bold shadow-sm"
              >
                {toPersianDigits(discount)}{"٪"} {"تخفیف"}
              </Badge>
            )}

            {product.is_featured && (
              <Badge className="absolute bottom-3 right-3 bg-amber-500 hover:bg-amber-600 text-white rounded-full text-[10px] px-2 py-0.5 gap-1">
                <Sparkles className="h-2.5 w-2.5" />
                {"ویژه"}
              </Badge>
            )}
          </div>

        {/* Content Details */}
        <div className="flex flex-1 flex-col p-4">
          <h3 className="mb-2 line-clamp-2 min-h-[2.75rem] text-sm font-semibold leading-relaxed text-foreground group-hover:text-primary transition-colors">
            {product.name}
          </h3>

          {product.short_description && (
            <p className="mb-3 line-clamp-1 text-xs text-muted-foreground">
              {product.short_description}
            </p>
          )}

          {/* Price Container */}
          <div className="mt-auto flex flex-col gap-1 pt-2 border-t border-border/50">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-base font-extrabold text-foreground">
                {formatPrice(price)}
              </span>
              {originalPrice && (
                <span className="text-xs line-through text-muted-foreground">
                  {formatPrice(originalPrice)}
                </span>
              )}
            </div>
          </div>
        </div>
      </Link>

      {/* Add To Cart Button */}
      <div className="px-4 pb-4">
        <Button
          size="sm"
          onClick={handleAddToCart}
          className="w-full gap-2 rounded-xl transition-all"
          variant={added ? "secondary" : "default"}
        >
          {added ? (
            <>
              <Check className="h-4 w-4 text-emerald-600" />
              <span className="text-xs font-bold text-emerald-600">
                {"به سبد افزوده شد"}
              </span>
            </>
          ) : (
            <>
              <ShoppingCart className="h-4 w-4" />
              <span className="text-xs font-semibold">{"افزودن به سبد خرید"}</span>
            </>
          )}
        </Button>
      </div>
    </Card>

    {/* Quick View Modal */}
    <Dialog open={quickViewOpen} onOpenChange={setQuickViewOpen}>
      <DialogContent className="max-w-md rounded-3xl p-6">
        <DialogHeader>
          <DialogTitle className="text-base font-bold text-foreground">
            {product.name}
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            {product.short_description || "مشاهده سریع مشخصات و افزودن آنی به سبد خرید"}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col items-center gap-4 py-2">
          <div className="relative aspect-square w-48 overflow-hidden rounded-2xl bg-muted/20 p-3">
            <RemoteImage
              src={product.image_url}
              alt={product.name}
              sizes="192px"
              className="object-contain p-2"
            />
          </div>

          <div className="flex items-baseline justify-between w-full border-t border-border pt-3">
            <span className="text-xs text-muted-foreground font-medium">
              {"قیمت مصرف‌کننده:"}
            </span>
            <span className="text-base font-black text-primary">
              {formatPrice(price)}
            </span>
          </div>

          <div className="flex gap-2 w-full pt-2">
            <Button
              onClick={(e) => {
                handleAddToCart(e);
                setQuickViewOpen(false);
              }}
              className="flex-1 rounded-xl font-bold gap-2 text-xs"
            >
              <ShoppingCart className="h-4 w-4" />
              {"افزودن به سبد خرید"}
            </Button>
            <Link href={`/products/${product.slug}`} className="flex-1">
              <Button variant="outline" className="w-full rounded-xl text-xs">
                {"صفحه کامل کالا"}
              </Button>
            </Link>
          </div>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
}

function ProductSkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i} className="overflow-hidden rounded-2xl">
          <Skeleton className="aspect-square w-full" />
          <div className="p-4 space-y-3">
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-3 w-3/5" />
            <Skeleton className="h-5 w-2/5" />
            <Skeleton className="h-9 w-full rounded-xl mt-4" />
          </div>
        </Card>
      ))}
    </div>
  );
}

/**
 * Windowed pagination: always shows first/last page plus a sliding window
 * around the current page, with ellipsis markers in between.
 */
function getPageWindow(
  current: number,
  total: number,
): Array<number | "ellipsis-left" | "ellipsis-right"> {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

  const pages: Array<number | "ellipsis-left" | "ellipsis-right"> = [1];
  const windowStart = Math.max(2, current - 1);
  const windowEnd = Math.min(total - 1, current + 1);

  if (windowStart > 2) pages.push("ellipsis-left");
  for (let p = windowStart; p <= windowEnd; p++) pages.push(p);
  if (windowEnd < total - 1) pages.push("ellipsis-right");

  pages.push(total);
  return pages;
}

/* -------------------------------------------------------------------------- */
/*                               Main Content                                 */
/* -------------------------------------------------------------------------- */

function ProductsListContent() {
  const searchParams = useSearchParams();

  // Faceted search hook — manages state, URL sync, and API calls
  const {
    filters,
    facets,
    results,
    total,
    totalPages,
    page,
    isLoading,
    error,
    degraded,
    activeFiltersCount,
    setQueryText,
    applyQueryText,
    setCategory,
    setBrand,
    setPriceRange,
    setRating,
    toggleInStockOnly,
    toggleAttribute,
    setSort,
    setPage,
    resetFilters,
    refetch,
  } = useFacetedSearch();

  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    applyQueryText(filters.q);
  };

  // The FacetedFilter component (shared between desktop sidebar and mobile sheet)
  const FilterSidebarContent = (
    <>
      {/* Search Filter */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-bold text-foreground">{"جستجو در نتایج"}</h3>
        <form onSubmit={handleSearchSubmit} className="relative">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder={"نام یا مدل کالا..."}
            value={filters.q}
            onChange={(e) => setQueryText(e.target.value)}
            className="h-10 ps-9 text-xs rounded-xl"
          />
        </form>
      </div>

      {/* Faceted Filters */}
      <FacetedFilter
        facets={facets}
        filters={filters}
        activeFiltersCount={activeFiltersCount}
        onCategoryChange={setCategory}
        onBrandChange={setBrand}
        onPriceRangeChange={setPriceRange}
        onRatingChange={setRating}
        onInStockToggle={toggleInStockOnly}
        onAttributeToggle={toggleAttribute}
        onResetFilters={resetFilters}
      />
    </>
  );

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Top Header & Breadcrumb */}
      <div className="mb-6 flex flex-col gap-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link href="/" className="hover:text-primary transition-colors">
            {"صفحه اصلی"}
          </Link>
          <ChevronLeft className="h-3.5 w-3.5" />
          <span className="text-foreground font-medium">{"فروشگاه محصولات"}</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <h1 className="text-2xl font-black text-foreground">
            {"لیست تمام محصولات"}
          </h1>
          <span className="text-xs sm:text-sm text-muted-foreground">
            {"نمایش"} {toPersianDigits(results.length)} {"کالا از مجموع"}{" "}
            {toPersianDigits(total)} {"محصول"}
          </span>
        </div>
      </div>

      {/* Action Bar (Mobile Filter Trigger, Active Chips, Sort) */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl border border-border bg-card p-3 shadow-sm">
        {/* Mobile Filter Button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => setMobileFilterOpen(true)}
          className="lg:hidden gap-2 rounded-xl"
        >
          <SlidersHorizontal className="h-4 w-4 text-primary" />
          <span>{"فیلترها"}</span>
          {activeFiltersCount > 0 && (
            <Badge className="h-5 w-5 rounded-full p-0 flex items-center justify-center text-[10px]">
              {toPersianDigits(activeFiltersCount)}
            </Badge>
          )}
        </Button>

        {/* Active Filter Chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          {filters.q && (
            <Badge
              variant="secondary"
              className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
            >
              <span>{"جستجو:"} {filters.q}</span>
              <X
                className="h-3 w-3 cursor-pointer hover:text-red-500"
                onClick={() => applyQueryText("")}
              />
            </Badge>
          )}
          {filters.category && (
            <Badge
              variant="secondary"
              className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
            >
              <span>{"دسته:"} {filters.category}</span>
              <X
                className="h-3 w-3 cursor-pointer hover:text-red-500"
                onClick={() => setCategory(null)}
              />
            </Badge>
          )}
          {filters.brand && (
            <Badge
              variant="secondary"
              className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
            >
              <span>{"برند:"} {filters.brand}</span>
              <X
                className="h-3 w-3 cursor-pointer hover:text-red-500"
                onClick={() => setBrand(null)}
              />
            </Badge>
          )}
          {(filters.minPrice !== null || filters.maxPrice !== null) && (
            <Badge
              variant="secondary"
              className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
            >
              <span>{"محدوده قیمت"}</span>
              <X
                className="h-3 w-3 cursor-pointer hover:text-red-500"
                onClick={() => setPriceRange(null, null)}
              />
            </Badge>
          )}
          {filters.minRating !== null && (
            <Badge
              variant="secondary"
              className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
            >
              <span>{"امتیاز:"} {toPersianDigits(filters.minRating)}+ {"ستاره"}</span>
              <X
                className="h-3 w-3 cursor-pointer hover:text-red-500"
                onClick={() => setRating(null)}
              />
            </Badge>
          )}
          {filters.inStockOnly && (
            <Badge
              variant="secondary"
              className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
            >
              <span>{"فقط موجود"}</span>
              <X
                className="h-3 w-3 cursor-pointer hover:text-red-500"
                onClick={toggleInStockOnly}
              />
            </Badge>
          )}
          {Object.entries(filters.attributes).map(([attr, vals]) =>
            vals.map((val) => (
              <Badge
                key={`${attr}-${val}`}
                variant="secondary"
                className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
              >
                <span>{attr}: {val}</span>
                <X
                  className="h-3 w-3 cursor-pointer hover:text-red-500"
                  onClick={() => toggleAttribute(attr, val)}
                />
              </Badge>
            )),
          )}
        </div>

        {/* Sort Dropdown */}
        <div className="flex items-center gap-2 ms-auto">
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {"مرتب‌سازی:"}
          </span>
          <Select
            value={filters.sort}
            onValueChange={(value) =>
              setSort(value as typeof filters.sort)
            }
          >
            <SelectTrigger aria-label={"مرتب‌سازی محصولات"} className="h-9 w-[140px] rounded-xl border-border text-xs font-semibold">
              <SelectValue placeholder={"مرتب‌سازی"} />
            </SelectTrigger>
            <SelectContent>
              {sortOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value} className="text-xs">
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Main Grid with Sidebar Filter */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        {/* Desktop Sidebar Filter */}
        <div className="hidden lg:block lg:col-span-1">
          <div className="space-y-4 sticky top-24">
            {FilterSidebarContent}
          </div>
        </div>

        {/* Products Grid & Pagination */}
        <div className="lg:col-span-3">
          {error && !isLoading ? (
            /* Error State — never fake products on API failure */
            <div className="flex flex-col items-center justify-center rounded-3xl border border-destructive/30 bg-destructive/5 py-16 text-center">
              <Package className="mb-3 h-16 w-16 text-destructive/40" />
              <h3 className="mb-1 text-lg font-bold text-foreground">
                {"خطا در دریافت محصولات"}
              </h3>
              <p className="mb-6 max-w-sm text-sm text-muted-foreground">
                {"ارتباط با سرور برقرار نشد. لطفاً دوباره تلاش کنید."}
              </p>
              <Button size="sm" onClick={() => refetch()} className="gap-2 rounded-xl">
                <RotateCcw className="h-4 w-4" />
                {"تلاش مجدد"}
              </Button>
            </div>
          ) : isLoading && results.length === 0 ? (
            <ProductSkeletonGrid />
          ) : results.length > 0 ? (
            <div className="space-y-8">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3">
                {results.map((p) => (
                  <ProductCard key={p.id} product={p} />
                ))}
              </div>

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 pt-6 border-t border-border">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => {
                      setPage(Math.max(1, page - 1));
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                    className="gap-1 rounded-xl text-xs"
                  >
                    <ChevronRight className="h-4 w-4" />
                    {"قبلی"}
                  </Button>

                  <div className="flex items-center gap-1">
                    {getPageWindow(page, totalPages).map(
                      (entry) =>
                        typeof entry === "number" ? (
                          <Button
                            key={entry}
                            variant={entry === page ? "default" : "ghost"}
                            size="sm"
                            onClick={() => {
                              setPage(entry);
                              window.scrollTo({ top: 0, behavior: "smooth" });
                            }}
                            className="h-8 w-8 rounded-xl p-0 text-xs font-semibold"
                          >
                            {toPersianDigits(entry)}
                          </Button>
                        ) : (
                          <span
                            key={entry}
                            className="flex h-8 w-6 items-end justify-center pb-1.5 text-xs text-muted-foreground"
                            aria-hidden
                          >
                            {"…"}
                          </span>
                        ),
                    )}
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => {
                      setPage(Math.min(totalPages, page + 1));
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                    className="gap-1 rounded-xl text-xs"
                  >
                    {"بعدی"}
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          ) : degraded ? (
            /* Degraded State — the search service is unreachable, so an
               empty list says nothing about whether matching products exist.
               Saying "no products found" here would be a false claim. */
            <div className="flex flex-col items-center justify-center rounded-3xl border border-destructive/30 bg-destructive/5 py-16 text-center">
              <Package className="mb-3 h-16 w-16 text-destructive/40" />
              <h3 className="mb-1 text-lg font-bold text-foreground">
                {"جست‌وجو موقتاً در دسترس نیست"}
              </h3>
              <p className="mb-6 max-w-sm text-sm text-muted-foreground">
                {"فهرست محصولات در حال حاضر قابل بازیابی نیست. لطفاً چند لحظه بعد دوباره تلاش کنید."}
              </p>
              <Button
                size="sm"
                onClick={() => refetch()}
                className="gap-2 rounded-xl"
              >
                <RotateCcw className="h-4 w-4" />
                {"تلاش مجدد"}
              </Button>
            </div>
          ) : (
            /* Empty State */
            <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-border py-16 text-center">
              <Package className="h-16 w-16 text-muted-foreground/40 mb-3" />
              <h3 className="text-lg font-bold text-foreground mb-1">
                {"محصولی با این مشخصات یافت نشد"}
              </h3>
              <p className="text-sm text-muted-foreground max-w-sm mb-6">
                {"می‌توانید فیلترهای اعمال شده را تغییر دهید یا عبارت دیگری را جستجو نمایید."}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={resetFilters}
                className="rounded-xl gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                {"حذف همه فیلترها"}
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Filters Sheet (RTL-aware, accessible) */}
      <Sheet open={mobileFilterOpen} onOpenChange={setMobileFilterOpen}>
        <SheetContent
          side="right"
          className="flex h-full w-full max-w-xs flex-col overflow-y-auto p-5 lg:hidden"
          aria-label={"فیلتر کالاها"}
        >
          <SheetHeader className="mb-4 border-b border-border pb-4 text-start">
            <SheetTitle className="flex items-center gap-2 text-base font-bold">
              <SlidersHorizontal className="h-5 w-5 text-primary" />
              {"فیلتر کالاها"}
            </SheetTitle>
            <SheetDescription className="text-xs">
              {"دسته‌بندی، برند، امتیاز و محدوده قیمت را انتخاب کنید"}
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-4">
            {FilterSidebarContent}
          </div>
          <div className="mt-6 border-t border-border pt-4">
            <Button
              className="w-full rounded-xl"
              onClick={() => setMobileFilterOpen(false)}
            >
              {"مشاهده"} {toPersianDigits(total)} {"نتیجه"}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default function ProductsPage() {
  return (
    <Suspense
      fallback={
        <div className="container mx-auto px-4 py-12">
          <Skeleton className="h-10 w-48 mb-6" />
          <ProductSkeletonGrid />
        </div>
      }
    >
      <ProductsListContent />
    </Suspense>
  );
}
