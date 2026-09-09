"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, SlidersHorizontal, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPrice } from "@/lib/utils";

interface ProductFilterState {
  search: string;
  category: string;
  sortBy: string;
  priceRange: [number, number];
}

const sampleProducts = [
  {
    id: "1",
    title: "گوشی موبایل سامسونگ گلکسی A54",
    slug: "samsung-galaxy-a54",
    price: 12500000,
    originalPrice: 14000000,
    image: null,
    category: "الکترونیک",
    rating: 4.5,
    reviewCount: 128,
    inStock: true,
  },
  {
    id: "2",
    title: "لپ‌تاپ ایسوس VivoBook 15",
    slug: "asus-vivobook-15",
    price: 32000000,
    originalPrice: null,
    image: null,
    category: "الکترونیک",
    rating: 4.2,
    reviewCount: 64,
    inStock: true,
  },
  {
    id: "3",
    title: "هدفون بی‌سیم سونی WH-1000XM5",
    slug: "sony-wh-1000xm5",
    price: 9800000,
    originalPrice: 11000000,
    image: null,
    category: "الکترونیک",
    rating: 4.8,
    reviewCount: 256,
    inStock: true,
  },
  {
    id: "4",
    title: "ساعت هوشمند شیائومی Band 8",
    slug: "xiaomi-band-8",
    price: 2500000,
    originalPrice: 2800000,
    image: null,
    category: "الکترونیک",
    rating: 4.1,
    reviewCount: 312,
    inStock: false,
  },
  {
    id: "5",
    title: "کتاب اصول طراحی نرم‌افزار",
    slug: "software-design-principles",
    price: 185000,
    originalPrice: null,
    image: null,
    category: "کتاب",
    rating: 4.6,
    reviewCount: 45,
    inStock: true,
  },
  {
    id: "6",
    title: "تی‌شرت مردانه طرح کلاسیک",
    slug: "classic-mens-tshirt",
    price: 450000,
    originalPrice: 550000,
    image: null,
    category: "پوشاک",
    rating: 3.9,
    reviewCount: 89,
    inStock: true,
  },
];

const sortOptions = [
  { value: "newest", label: "جدیدترین" },
  { value: "price-asc", label: "ارزان‌ترین" },
  { value: "price-desc", label: "گران‌ترین" },
  { value: "popular", label: "محبوب‌ترین" },
  { value: "rating", label: "بالاترین امتیاز" },
];

function ProductCard({
  product,
}: {
  product: (typeof sampleProducts)[number];
}) {
  const discount = product.originalPrice
    ? Math.round(
        ((product.originalPrice - product.price) / product.originalPrice) * 100,
      )
    : null;

  return (
    <Card className="group overflow-hidden transition-shadow hover:shadow-lg">
      <Link href={`/products/${product.slug}`}>
        <div className="relative aspect-square bg-muted">
          <div className="flex h-full items-center justify-center text-4xl text-muted-foreground">
            📦
          </div>
          {discount && (
            <Badge
              variant="destructive"
              className="absolute left-2 top-2 rounded-full"
            >
              {discount}% تخفیف
            </Badge>
          )}
          {!product.inStock && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80">
              <span className="text-sm font-medium text-muted-foreground">
                ناموجود
              </span>
            </div>
          )}
        </div>
        <div className="p-4">
          <h3 className="mb-2 line-clamp-2 text-sm font-medium text-foreground group-hover:text-primary">
            {product.title}
          </h3>
          <div className="mb-2 flex items-center gap-1">
            <span className="text-xs text-yellow-500">★</span>
            <span className="text-xs text-muted-foreground">
              {product.rating} ({product.reviewCount} نظر)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="price text-base">{formatPrice(product.price)}</span>
            {product.originalPrice && (
              <span className="price-discount">
                {formatPrice(product.originalPrice)}
              </span>
            )}
          </div>
        </div>
      </Link>
    </Card>
  );
}

function ProductCardSkeleton() {
  return (
    <Card className="overflow-hidden">
      <Skeleton className="aspect-square w-full" />
      <div className="p-4">
        <Skeleton className="mb-2 h-4 w-3/4" />
        <Skeleton className="mb-2 h-3 w-1/2" />
        <Skeleton className="h-5 w-1/3" />
      </div>
    </Card>
  );
}

export default function ProductsPage() {
  const [filters, setFilters] = useState<ProductFilterState>({
    search: "",
    category: "",
    sortBy: "newest",
    priceRange: [0, 100000000],
  });
  const [showFilters, setShowFilters] = useState(false);

  const filteredProducts = sampleProducts.filter((product) => {
    if (
      filters.search &&
      !product.title.includes(filters.search) &&
      !product.category.includes(filters.search)
    ) {
      return false;
    }
    if (filters.category && product.category !== filters.category) {
      return false;
    }
    return true;
  });

  return (
    <div className="container-page">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="mb-2 text-2xl font-bold text-foreground">محصولات</h1>
        <p className="text-muted-foreground">
          مشاهده و خرید از میان هزاران محصول با کیفیت
        </p>
      </div>

      {/* Search and Sort Bar */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 sm:max-w-md">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="جستجوی محصول..."
            value={filters.search}
            onChange={(e) =>
              setFilters((prev) => ({ ...prev, search: e.target.value }))
            }
            className="pr-10"
          />
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <SlidersHorizontal className="ml-2 h-4 w-4" />
            فیلترها
          </Button>
          <div className="relative">
            <select
              value={filters.sortBy}
              onChange={(e) =>
                setFilters((prev) => ({ ...prev, sortBy: e.target.value }))
              }
              className="input-base appearance-none pl-8 pr-3 text-sm"
            >
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          </div>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="mb-6 rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 font-semibold text-foreground">فیلترها</h3>
          <div className="flex flex-wrap gap-3">
            {["همه", "الکترونیک", "پوشاک", "کتاب", "خانه و آشپزخانه"].map(
              (cat) => (
                <Button
                  key={cat}
                  variant={
                    filters.category === (cat === "همه" ? "" : cat)
                      ? "default"
                      : "outline"
                  }
                  size="sm"
                  onClick={() =>
                    setFilters((prev) => ({
                      ...prev,
                      category: cat === "همه" ? "" : cat,
                    }))
                  }
                >
                  {cat}
                </Button>
              ),
            )}
          </div>
        </div>
      )}

      {/* Results Count */}
      <div className="mb-4">
        <span className="text-sm text-muted-foreground">
          {filteredProducts.length} محصول یافت شد
        </span>
      </div>

      {/* Products Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {filteredProducts.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>

      {/* Empty State */}
      {filteredProducts.length === 0 && (
        <div className="py-16 text-center">
          <p className="mb-2 text-lg font-medium text-foreground">
            محصولی یافت نشد
          </p>
          <p className="text-muted-foreground">
            فیلترهای خود را تغییر دهید یا عبارت دیگری جستجو کنید.
          </p>
        </div>
      )}
    </div>
  );
}
