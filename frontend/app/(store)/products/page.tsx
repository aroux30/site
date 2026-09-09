"use client";

import { useState, useEffect, useCallback, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Search,
  SlidersHorizontal,
  ChevronDown,
  X,
  Package,
  Star,
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
import { Slider } from "@/components/ui/slider";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { formatPrice, toPersianDigits, cn } from "@/lib/utils";
import { useCart } from "@/hooks/use-cart";
import { useCompareStore } from "@/stores/compare-store";
import type { Product } from "@/types/product";
import {
  fetchCategories,
  fetchBrands,
  fetchProducts,
  type ApiCategory,
  type ApiBrand,
  type ApiProduct,
  type ApiPaginationMeta,
} from "@/lib/api/services";

/* -------------------------------------------------------------------------- */
/*                               Fallback Data                                */
/* -------------------------------------------------------------------------- */

const fallbackCategories: ApiCategory[] = [
  { id: "c-phones", name: "موبایل و تبلت", slug: "phones", is_active: true },
  { id: "c-laptops", name: "لپ‌تاپ و کامپیوتر", slug: "laptops", is_active: true },
  { id: "c-audio", name: "صوتی و هدفون", slug: "audio", is_active: true },
  { id: "c-wearables", name: "ساعت هوشمند", slug: "smartwatch", is_active: true },
  { id: "c-gaming", name: "کنسول و گیمینگ", slug: "gaming", is_active: true },
  { id: "c-home", name: "خانه و آشپزخانه", slug: "home", is_active: true },
];

const fallbackBrands: ApiBrand[] = [
  { id: "b-apple", name: "اپل (Apple)", slug: "apple", is_active: true },
  { id: "b-samsung", name: "سامسونگ (Samsung)", slug: "samsung", is_active: true },
  { id: "b-sony", name: "سونی (Sony)", slug: "sony", is_active: true },
  { id: "b-xiaomi", name: "شیائومی (Xiaomi)", slug: "xiaomi", is_active: true },
  { id: "b-asus", name: "ایسوس (Asus)", slug: "asus", is_active: true },
];

const fallbackProducts: ApiProduct[] = [
  {
    id: "p1",
    name: "گوشی موبایل سامسونگ Galaxy S24 Ultra",
    slug: "samsung-galaxy-s24-ultra",
    category_id: "c-phones",
    brand_id: "b-samsung",
    min_price: 65000000,
    max_price: 72000000,
    variant_count: 4,
    is_active: true,
    is_featured: true,
    short_description: "حافظه ۲۵۶ گیگابایت، رم ۱۲، دوربین ۲۰۰ مگاپیکسل، تیتانیوم",
  },
  {
    id: "p2",
    name: "لپ‌تاپ ایسوس ROG Zephyrus G16",
    slug: "asus-rog-zephyrus-g16",
    category_id: "c-laptops",
    brand_id: "b-asus",
    min_price: 89000000,
    max_price: 98000000,
    variant_count: 2,
    is_active: true,
    is_featured: true,
    short_description: "پردازنده Core Ultra 9، رم ۳۲ گیگ، کارت گرافیک RTX 4070",
  },
  {
    id: "p3",
    name: "هدفون بی‌سیم سونی WH-1000XM5",
    slug: "sony-wh-1000xm5",
    category_id: "c-audio",
    brand_id: "b-sony",
    min_price: 18500000,
    max_price: 21000000,
    variant_count: 2,
    is_active: true,
    is_featured: false,
    short_description: "قابلیت نویزکنسلینگ فعال پیشرفته با ۳۰ ساعت نگهداری شارژ",
  },
  {
    id: "p4",
    name: "ساعت هوشمند اپل واچ اولترا ۲",
    slug: "apple-watch-ultra-2",
    category_id: "c-wearables",
    brand_id: "b-apple",
    min_price: 44000000,
    max_price: 48000000,
    variant_count: 3,
    is_active: true,
    is_featured: true,
    short_description: "بدنه تیتانیومی ۴۹ میلی‌متری و روشنایی صفحه ۳۰۰۰ نیت",
  },
  {
    id: "p5",
    name: "گوشی شیائومی ۱۴ اولترا",
    slug: "xiaomi-14-ultra",
    category_id: "c-phones",
    brand_id: "b-xiaomi",
    min_price: 59000000,
    max_price: 64000000,
    variant_count: 2,
    is_active: true,
    is_featured: false,
    short_description: "مجهز به لنزهای عکاسی حرفه‌ای Leica و شارژ فوق‌سریع ۹۰ وات",
  },
  {
    id: "p6",
    name: "کنسول بازی پلی‌استیشن ۵ اسلیم",
    slug: "sony-playstation-5-slim",
    category_id: "c-gaming",
    brand_id: "b-sony",
    min_price: 34500000,
    max_price: 38000000,
    variant_count: 1,
    is_active: true,
    is_featured: false,
    short_description: "حافظه ۱ ترابایت، کیفیت خروجی 4K HDR، دسته DualSense",
  },
  {
    id: "p7",
    name: "مک‌بوک پرو ۱۶ اینچ اپل M3 Max",
    slug: "apple-macbook-pro-16-m3-max",
    category_id: "c-laptops",
    brand_id: "b-apple",
    min_price: 145000000,
    max_price: 155000000,
    variant_count: 2,
    is_active: true,
    is_featured: true,
    short_description: "قوی‌ترین تراشه اپل، نمایشگر Liquid Retina XDR، رم ۳۶ گیگ",
  },
  {
    id: "p8",
    name: "اسپیکر قابل حمل سونی SRS-XG300",
    slug: "sony-srs-xg300",
    category_id: "c-audio",
    brand_id: "b-sony",
    min_price: 14200000,
    max_price: 16000000,
    variant_count: 2,
    is_active: true,
    is_featured: false,
    short_description: "مقاومت در برابر آب IP67، نورپردازی محیطی و بیس عمیق Mega Bass",
  },
];

const sortOptions = [
  { value: "newest", label: "جدیدترین", sort_by: "created_at", sort_order: "desc" },
  { value: "cheapest", label: "ارزان‌ترین", sort_by: "price", sort_order: "asc" },
  { value: "expensive", label: "گران‌ترین", sort_by: "price", sort_order: "desc" },
  { value: "popular", label: "محبوب‌ترین", sort_by: "position", sort_order: "asc" },
];

const MAX_PRICE_LIMIT = 150000000;

/* -------------------------------------------------------------------------- */
/*                               Product Card                                 */
/* -------------------------------------------------------------------------- */

function ProductCard({ product }: { product: ApiProduct }) {
  const { addToCart } = useCart();
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
      price: product.min_price || 0,
      originalPrice:
        product.max_price && product.max_price > (product.min_price || 0)
          ? product.max_price
          : undefined,
      sku: product.id,
      stock: 10,
      isActive: product.is_active,
      isFeatured: product.is_featured,
      images: product.primary_image_url
        ? [
            {
              id: "img-primary",
              url: product.primary_image_url,
              alt: product.name,
              order: 1,
            },
          ]
        : [],
      thumbnail: product.primary_image_url || undefined,
      categoryId: product.category_id || "cat-default",
      tags: [],
      variants: [],
      attributes: [],
      type: "کالای دیجیتال",
      rating: 4.7,
      reviewCount: 15,
      createdAt: product.created_at || new Date().toISOString(),
      updatedAt: product.updated_at || new Date().toISOString(),
    };

    toggleProduct(compareItem);
  };

  const price = product.min_price || 0;
  const originalPrice =
    product.max_price && product.max_price > price ? product.max_price : undefined;
  const discount =
    originalPrice && originalPrice > price
      ? Math.round(((originalPrice - price) / originalPrice) * 100)
      : null;

  const handleAddToCart = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    addToCart({
      productId: product.id,
      title: product.name,
      slug: product.slug,
      price,
      originalPrice,
      image: product.primary_image_url || undefined,
    });
    setAdded(true);
    setTimeout(() => setAdded(false), 1800);
  };

  return (
    <>
      <Card className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-card transition-all duration-300 hover:-translate-y-1 hover:shadow-xl">
        <Link href={`/products/${product.slug}`} className="flex flex-col h-full">
          {/* Product Image */}
          <div className="relative aspect-square overflow-hidden bg-muted/50 p-4">
            {product.primary_image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={product.primary_image_url}
                alt={product.name}
                className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-muted-foreground/30">
                <Package className="h-20 w-20" />
              </div>
            )}

            {/* Quick View Button */}
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setQuickViewOpen(true);
              }}
              className="absolute bottom-3 left-3 z-10 flex h-8 w-8 items-center justify-center rounded-xl bg-background/90 backdrop-blur-md text-foreground shadow-sm opacity-0 transition-opacity duration-200 group-hover:opacity-100 hover:bg-background"
              title="مشاهده سریع"
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
                {toPersianDigits(discount)}٪ تخفیف
              </Badge>
            )}

            {product.is_featured && (
              <Badge className="absolute bottom-3 right-3 bg-amber-500 hover:bg-amber-600 text-white rounded-full text-[10px] px-2 py-0.5 gap-1">
                <Sparkles className="h-2.5 w-2.5" />
                ویژه
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

          {/* Rating */}
          <div className="mb-3 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
            <span className="font-semibold text-foreground">۴.۶</span>
            <span>(۲۸ نظر)</span>
          </div>

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
                به سبد افزوده شد
              </span>
            </>
          ) : (
            <>
              <ShoppingCart className="h-4 w-4" />
              <span className="text-xs font-semibold">افزودن به سبد خرید</span>
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
          <div className="relative aspect-square w-48 overflow-hidden rounded-2xl bg-muted/40 p-3">
            {product.primary_image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={product.primary_image_url}
                alt={product.name}
                className="h-full w-full object-contain"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-muted-foreground/40">
                <Package className="h-16 w-16" />
              </div>
            )}
          </div>

          <div className="flex items-baseline justify-between w-full border-t border-border pt-3">
            <span className="text-xs text-muted-foreground font-medium">
              قیمت مصرف‌کننده:
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
              افزودن به سبد خرید
            </Button>
            <Link href={`/products/${product.slug}`} className="flex-1">
              <Button variant="outline" className="w-full rounded-xl text-xs">
                صفحه کامل کالا
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

/* -------------------------------------------------------------------------- */
/*                               Main Content                                 */
/* -------------------------------------------------------------------------- */

function ProductsListContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Read URL parameters
  const initialQ = searchParams.get("q") || "";
  const initialCategory =
    searchParams.get("category_id") || searchParams.get("category") || "";
  const initialBrand = searchParams.get("brand_id") || "";
  const initialSort = searchParams.get("sort") || "newest";
  const initialPage = parseInt(searchParams.get("page") || "1", 10);
  const initialMinPrice = searchParams.get("min_price")
    ? parseInt(searchParams.get("min_price")!, 10)
    : 0;
  const initialMaxPrice = searchParams.get("max_price")
    ? parseInt(searchParams.get("max_price")!, 10)
    : MAX_PRICE_LIMIT;

  // Filter States
  const [searchQuery, setSearchQuery] = useState(initialQ);
  const [selectedCategory, setSelectedCategory] = useState<string>(initialCategory);
  const [selectedBrand, setSelectedBrand] = useState<string>(initialBrand);
  const [selectedSort, setSelectedSort] = useState<string>(initialSort);
  const [priceRange, setPriceRange] = useState<[number, number]>([
    initialMinPrice,
    initialMaxPrice,
  ]);
  const [currentPage, setCurrentPage] = useState<number>(initialPage);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  // Data States
  const [categories, setCategories] = useState<ApiCategory[]>(fallbackCategories);
  const [brands, setBrands] = useState<ApiBrand[]>(fallbackBrands);
  const [products, setProducts] = useState<ApiProduct[]>(fallbackProducts);
  const [paginationMeta, setPaginationMeta] = useState<ApiPaginationMeta>({
    total: fallbackProducts.length,
    page: 1,
    page_size: 12,
    total_pages: 1,
    has_next: false,
    has_prev: false,
  });
  const [loading, setLoading] = useState(true);

  // Load Categories & Brands
  useEffect(() => {
    async function loadMeta() {
      try {
        const [catData, brandData] = await Promise.allSettled([
          fetchCategories({ is_active: true, page_size: 50 }),
          fetchBrands({ is_active: true, page_size: 50 }),
        ]);

        if (catData.status === "fulfilled" && catData.value.items?.length > 0) {
          setCategories(catData.value.items);
        }
        if (brandData.status === "fulfilled" && brandData.value.items?.length > 0) {
          setBrands(brandData.value.items);
        }
      } catch (err) {
        console.warn("Could not fetch categories/brands, using fallbacks:", err);
      }
    }
    loadMeta();
  }, []);

  // Sync state when URL params change
  useEffect(() => {
    setSearchQuery(searchParams.get("q") || "");
    setSelectedCategory(
      searchParams.get("category_id") || searchParams.get("category") || "",
    );
    setSelectedBrand(searchParams.get("brand_id") || "");
    setSelectedSort(searchParams.get("sort") || "newest");
    setCurrentPage(parseInt(searchParams.get("page") || "1", 10));
  }, [searchParams]);

  // Fetch Products based on current filters
  const loadProducts = useCallback(async () => {
    setLoading(true);

    const sortConfig =
      sortOptions.find((s) => s.value === selectedSort) || sortOptions[0]!;

    const params: Record<string, any> = {
      page: currentPage,
      page_size: 12,
      sort_by: sortConfig.sort_by,
      sort_order: sortConfig.sort_order,
    };

    if (searchQuery.trim()) params.q = searchQuery.trim();
    if (selectedCategory) params.category_id = selectedCategory;
    if (selectedBrand) params.brand_id = selectedBrand;
    if (priceRange[0] > 0) params.min_price = priceRange[0];
    if (priceRange[1] < MAX_PRICE_LIMIT) params.max_price = priceRange[1];

    try {
      const response = await fetchProducts(params);
      if (response.items) {
        setProducts(response.items);
        setPaginationMeta(response.meta);
      }
    } catch (err) {
      console.warn("Products API call failed, applying client filter to fallback:", err);

      // Client-side filtering over fallback data
      let filtered = [...fallbackProducts];

      if (searchQuery.trim()) {
        const query = searchQuery.trim().toLowerCase();
        filtered = filtered.filter(
          (p) =>
            p.name.toLowerCase().includes(query) ||
            p.short_description?.toLowerCase().includes(query),
        );
      }

      if (selectedCategory) {
        filtered = filtered.filter(
          (p) =>
            p.category_id === selectedCategory ||
            categories.find((c) => c.slug === selectedCategory)?.id === p.category_id,
        );
      }

      if (selectedBrand) {
        filtered = filtered.filter((p) => p.brand_id === selectedBrand);
      }

      filtered = filtered.filter((p) => {
        const pPrice = p.min_price || 0;
        return pPrice >= priceRange[0] && pPrice <= priceRange[1];
      });

      // Sorting
      if (selectedSort === "cheapest") {
        filtered.sort((a, b) => (a.min_price || 0) - (b.min_price || 0));
      } else if (selectedSort === "expensive") {
        filtered.sort((a, b) => (b.min_price || 0) - (a.min_price || 0));
      }

      setProducts(filtered);
      setPaginationMeta({
        total: filtered.length,
        page: currentPage,
        page_size: 12,
        total_pages: Math.max(1, Math.ceil(filtered.length / 12)),
        has_next: false,
        has_prev: false,
      });
    } finally {
      setLoading(false);
    }
  }, [
    searchQuery,
    selectedCategory,
    selectedBrand,
    selectedSort,
    priceRange,
    currentPage,
    categories,
  ]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  // Update URL on filter submit
  const updateUrl = (overrides: Record<string, string | number | undefined>) => {
    const params = new URLSearchParams(searchParams.toString());

    Object.entries(overrides).forEach(([k, v]) => {
      if (v === undefined || v === "" || v === 0) {
        params.delete(k);
      } else {
        params.set(k, String(v));
      }
    });

    router.push(`/products?${params.toString()}`);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    updateUrl({ q: searchQuery.trim() || undefined, page: 1 });
  };

  const handleClearFilters = () => {
    setSearchQuery("");
    setSelectedCategory("");
    setSelectedBrand("");
    setPriceRange([0, MAX_PRICE_LIMIT]);
    setSelectedSort("newest");
    setCurrentPage(1);
    router.push("/products");
  };

  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (searchQuery.trim()) count++;
    if (selectedCategory) count++;
    if (selectedBrand) count++;
    if (priceRange[0] > 0 || priceRange[1] < MAX_PRICE_LIMIT) count++;
    return count;
  }, [searchQuery, selectedCategory, selectedBrand, priceRange]);

  // Sidebar Filter Component
  const FilterSidebar = (
    <div className="space-y-6">
      {/* Search Filter */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-bold text-foreground">جستجو در نتایج</h3>
        <form onSubmit={handleSearchSubmit} className="relative">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="نام یا مدل کالا..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-10 pr-9 text-xs rounded-xl"
          />
        </form>
      </div>

      {/* Categories Filter */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-foreground">دسته‌بندی</h3>
          {selectedCategory && (
            <button
              onClick={() => {
                setSelectedCategory("");
                updateUrl({ category_id: undefined, category: undefined, page: 1 });
              }}
              className="text-[11px] text-primary hover:underline"
            >
              پاک کردن
            </button>
          )}
        </div>
        <div className="space-y-1 max-h-56 overflow-y-auto pr-1">
          <button
            type="button"
            onClick={() => {
              setSelectedCategory("");
              updateUrl({ category_id: undefined, category: undefined, page: 1 });
            }}
            className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs text-start transition-colors ${
              selectedCategory === ""
                ? "bg-primary/10 font-bold text-primary"
                : "text-foreground hover:bg-muted"
            }`}
          >
            <span>همه دسته‌ها</span>
          </button>
          {categories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => {
                setSelectedCategory(cat.id);
                updateUrl({ category_id: cat.id, page: 1 });
              }}
              className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs text-start transition-colors ${
                selectedCategory === cat.id || selectedCategory === cat.slug
                  ? "bg-primary/10 font-bold text-primary"
                  : "text-foreground hover:bg-muted"
              }`}
            >
              <span>{cat.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Brands Filter */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-foreground">برند کالا</h3>
          {selectedBrand && (
            <button
              onClick={() => {
                setSelectedBrand("");
                updateUrl({ brand_id: undefined, page: 1 });
              }}
              className="text-[11px] text-primary hover:underline"
            >
              پاک کردن
            </button>
          )}
        </div>
        <div className="space-y-1 max-h-56 overflow-y-auto pr-1">
          <button
            type="button"
            onClick={() => {
              setSelectedBrand("");
              updateUrl({ brand_id: undefined, page: 1 });
            }}
            className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs text-start transition-colors ${
              selectedBrand === ""
                ? "bg-primary/10 font-bold text-primary"
                : "text-foreground hover:bg-muted"
            }`}
          >
            <span>همه برندها</span>
          </button>
          {brands.map((brand) => (
            <button
              key={brand.id}
              type="button"
              onClick={() => {
                setSelectedBrand(brand.id);
                updateUrl({ brand_id: brand.id, page: 1 });
              }}
              className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs text-start transition-colors ${
                selectedBrand === brand.id
                  ? "bg-primary/10 font-bold text-primary"
                  : "text-foreground hover:bg-muted"
              }`}
            >
              <span>{brand.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Price Range Filter */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground">محدوده قیمت (تومان)</h3>
          {(priceRange[0] > 0 || priceRange[1] < MAX_PRICE_LIMIT) && (
            <button
              onClick={() => {
                setPriceRange([0, MAX_PRICE_LIMIT]);
                updateUrl({ min_price: undefined, max_price: undefined, page: 1 });
              }}
              className="text-[11px] text-primary hover:underline"
            >
              ریست
            </button>
          )}
        </div>

        {/* Dual Slider */}
        <div className="px-1 pt-2">
          <Slider
            min={0}
            max={MAX_PRICE_LIMIT}
            step={500000}
            value={[priceRange[0], priceRange[1]]}
            onValueChange={(val) => {
              if (val.length === 2) {
                setPriceRange([val[0]!, val[1]!]);
              }
            }}
          />
        </div>

        {/* Price Inputs */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-muted-foreground block mb-1">از:</span>
            <div className="rounded-lg border border-border p-2 bg-muted/30 font-mono text-center">
              {formatPrice(priceRange[0])}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground block mb-1">تا:</span>
            <div className="rounded-lg border border-border p-2 bg-muted/30 font-mono text-center">
              {formatPrice(priceRange[1])}
            </div>
          </div>
        </div>

        <Button
          size="sm"
          onClick={() => {
            setCurrentPage(1);
            updateUrl({
              min_price: priceRange[0] > 0 ? priceRange[0] : undefined,
              max_price:
                priceRange[1] < MAX_PRICE_LIMIT ? priceRange[1] : undefined,
              page: 1,
            });
          }}
          className="w-full rounded-xl text-xs"
        >
          اعمال محدوده قیمت
        </Button>
      </div>

      {/* Reset All Filters */}
      {activeFiltersCount > 0 && (
        <Button
          variant="outline"
          size="sm"
          onClick={handleClearFilters}
          className="w-full gap-2 rounded-xl text-xs text-red-500 border-red-200 hover:bg-red-50"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          پاک کردن تمام فیلترها
        </Button>
      )}
    </div>
  );

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Top Header & Breadcrumb */}
      <div className="mb-6 flex flex-col gap-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link href="/" className="hover:text-primary transition-colors">
            صفحه اصلی
          </Link>
          <ChevronLeft className="h-3.5 w-3.5" />
          <span className="text-foreground font-medium">فروشگاه محصولات</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <h1 className="text-2xl font-black text-foreground">
            لیست تمام محصولات
          </h1>
          <span className="text-xs sm:text-sm text-muted-foreground">
            نمایش {toPersianDigits(products.length)} کالا از مجموع{" "}
            {toPersianDigits(paginationMeta.total)} محصول
          </span>
        </div>
      </div>

      {/* Action Bar (Search Input, Mobile Filter Trigger, Sort Select) */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl border border-border bg-card p-3 shadow-sm">
        {/* Mobile Filter Button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => setMobileFilterOpen(true)}
          className="lg:hidden gap-2 rounded-xl"
        >
          <SlidersHorizontal className="h-4 w-4 text-primary" />
          <span>فیلترها</span>
          {activeFiltersCount > 0 && (
            <Badge className="h-5 w-5 rounded-full p-0 flex items-center justify-center text-[10px]">
              {toPersianDigits(activeFiltersCount)}
            </Badge>
          )}
        </Button>

        {/* Active Filter Chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          {searchQuery && (
            <Badge
              variant="secondary"
              className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
            >
              <span>جستجو: {searchQuery}</span>
              <X
                className="h-3 w-3 cursor-pointer hover:text-red-500"
                onClick={() => {
                  setSearchQuery("");
                  updateUrl({ q: undefined });
                }}
              />
            </Badge>
          )}
          {selectedCategory && (
            <Badge
              variant="secondary"
              className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
            >
              <span>
                دسته:{" "}
                {categories.find((c) => c.id === selectedCategory || c.slug === selectedCategory)?.name ||
                  selectedCategory}
              </span>
              <X
                className="h-3 w-3 cursor-pointer hover:text-red-500"
                onClick={() => {
                  setSelectedCategory("");
                  updateUrl({ category_id: undefined, category: undefined });
                }}
              />
            </Badge>
          )}
          {selectedBrand && (
            <Badge
              variant="secondary"
              className="gap-1 rounded-lg text-xs py-1 px-2 font-normal"
            >
              <span>
                برند: {brands.find((b) => b.id === selectedBrand)?.name || selectedBrand}
              </span>
              <X
                className="h-3 w-3 cursor-pointer hover:text-red-500"
                onClick={() => {
                  setSelectedBrand("");
                  updateUrl({ brand_id: undefined });
                }}
              />
            </Badge>
          )}
        </div>

        {/* Sort Dropdown */}
        <div className="flex items-center gap-2 mr-auto">
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            مرتب‌سازی:
          </span>
          <div className="relative">
            <select
              value={selectedSort}
              onChange={(e) => {
                setSelectedSort(e.target.value);
                setCurrentPage(1);
                updateUrl({ sort: e.target.value, page: 1 });
              }}
              className="h-9 appearance-none rounded-xl border border-border bg-background pr-3 pl-8 text-xs font-semibold text-foreground focus:border-primary focus:outline-none"
            >
              {sortOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          </div>
        </div>
      </div>

      {/* Main Grid with Sidebar Filter */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        {/* Desktop Sidebar Filter */}
        <div className="hidden lg:block lg:col-span-1">{FilterSidebar}</div>

        {/* Products Grid & Pagination */}
        <div className="lg:col-span-3">
          {loading ? (
            <ProductSkeletonGrid />
          ) : products.length > 0 ? (
            <div className="space-y-8">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3">
                {products.map((p) => (
                  <ProductCard key={p.id} product={p} />
                ))}
              </div>

              {/* Pagination Controls */}
              {paginationMeta.total_pages > 1 && (
                <div className="flex items-center justify-center gap-2 pt-6 border-t border-border">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage <= 1}
                    onClick={() => {
                      const next = Math.max(1, currentPage - 1);
                      setCurrentPage(next);
                      updateUrl({ page: next });
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                    className="gap-1 rounded-xl text-xs"
                  >
                    <ChevronRight className="h-4 w-4" />
                    قبلی
                  </Button>

                  <div className="flex items-center gap-1">
                    {Array.from(
                      { length: paginationMeta.total_pages },
                      (_, idx) => idx + 1,
                    ).map((pageNumber) => (
                      <Button
                        key={pageNumber}
                        variant={pageNumber === currentPage ? "default" : "ghost"}
                        size="sm"
                        onClick={() => {
                          setCurrentPage(pageNumber);
                          updateUrl({ page: pageNumber });
                          window.scrollTo({ top: 0, behavior: "smooth" });
                        }}
                        className="h-8 w-8 rounded-xl p-0 text-xs font-semibold"
                      >
                        {toPersianDigits(pageNumber)}
                      </Button>
                    ))}
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage >= paginationMeta.total_pages}
                    onClick={() => {
                      const next = Math.min(
                        paginationMeta.total_pages,
                        currentPage + 1,
                      );
                      setCurrentPage(next);
                      updateUrl({ page: next });
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                    className="gap-1 rounded-xl text-xs"
                  >
                    بعدی
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          ) : (
            /* Empty State */
            <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-border py-16 text-center">
              <Package className="h-16 w-16 text-muted-foreground/40 mb-3" />
              <h3 className="text-lg font-bold text-foreground mb-1">
                محصولی با این مشخصات یافت نشد
              </h3>
              <p className="text-sm text-muted-foreground max-w-sm mb-6">
                می‌توانید فیلترهای اعمال شده را تغییر دهید یا عبارت دیگری را جستجو نمایید.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleClearFilters}
                className="rounded-xl gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                حذف همه فیلترها
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Filters Drawer / Modal */}
      {mobileFilterOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileFilterOpen(false)}
          />
          <div className="relative mr-auto flex h-full w-full max-w-xs flex-col bg-background p-5 shadow-2xl overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-border mb-4">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="h-5 w-5 text-primary" />
                <h2 className="text-base font-bold text-foreground">فیلتر کالاها</h2>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setMobileFilterOpen(false)}
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
            {FilterSidebar}
            <div className="mt-6 pt-4 border-t border-border">
              <Button
                className="w-full rounded-xl"
                onClick={() => setMobileFilterOpen(false)}
              >
                مشاهده نتایج
              </Button>
            </div>
          </div>
        </div>
      )}
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
