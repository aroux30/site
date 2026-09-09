"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import {
  ArrowLeftRight,
  ShoppingCart,
  Trash2,
  Check,
  X,
  Star,
  Plus,
  Package,
  Layers,
  Sparkles,
  ChevronLeft,
  ArrowRight,
  Info,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { useCompareStore, MAX_COMPARE_PRODUCTS } from "@/stores/compare-store";
import { useCart } from "@/hooks/use-cart";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { formatPrice, toPersianDigits, cn } from "@/lib/utils";
import type { Product } from "@/types/product";

/* -------------------------------------------------------------------------- */
/*                        Suggested Flagship Products                         */
/* -------------------------------------------------------------------------- */

const FLAGSHIP_SUGGESTIONS: Product[] = [
  {
    id: "samsung-galaxy-s24-ultra",
    title: "گوشی موبایل سامسونگ Galaxy S24 Ultra",
    slug: "samsung-galaxy-s24-ultra",
    description:
      "گوشی پرچمدار سامسونگ گلکسی اس ۲۴ اولترا با فریم تیتانیومی و نمایشگر ۶.۸ اینچی Dynamic AMOLED 2X، قلم S-Pen و قابلیت‌های هوش مصنوعی پیشرفته Galaxy AI.",
    shortDescription:
      "حافظه ۲۵۶ گیگابایت، رم ۱۲، دوربین ۲۰۰ مگاپیکسل، بدنه تیتانیوم گرید ۵",
    price: 65000000,
    originalPrice: 72000000,
    sku: "SAM-S24U-TIT-256",
    stock: 15,
    isActive: true,
    isFeatured: true,
    type: "گوشی هوشمند پرچمدار",
    weight: "۲۳۲ گرم",
    dimensions: "۱۶۲.۳ × ۷۹ × ۸.۶ میلی‌متر",
    thumbnail: "/images/products/s24-ultra.png",
    images: [
      {
        id: "img-s24",
        url: "/images/products/s24-ultra.png",
        alt: "Samsung Galaxy S24 Ultra",
        order: 1,
      },
    ],
    categoryId: "cat-phones",
    category: {
      id: "cat-phones",
      name: "موبایل و تبلت",
      slug: "phones",
    },
    brandId: "brand-samsung",
    brand: {
      id: "brand-samsung",
      name: "سامسونگ (Samsung)",
      slug: "samsung",
    },
    tags: ["موبایل", "سامسونگ", "پرچمدار", "S24 Ultra"],
    variants: [],
    attributes: [
      { name: "پردازنده", value: "Snapdragon 8 Gen 3 for Galaxy" },
      { name: "باتری", value: "۵۰۰۰ میلی‌آمپر ساعت با شارژ ۴۵ وات" },
      { name: "نمایشگر", value: "۶.۸ اینچ Dynamic AMOLED 2X ۱۲۰ هرتز" },
      { name: "دوربین اصلی", value: "۲۰۰ مگاپیکسل مجهز به زوم ۵ و ۱۰ برابر" },
    ],
    rating: 4.8,
    reviewCount: 142,
    createdAt: "2024-01-20T00:00:00Z",
    updatedAt: "2024-02-01T00:00:00Z",
  },
  {
    id: "apple-iphone-16-pro-max",
    title: "گوشی موبایل اپل iPhone 16 Pro Max",
    slug: "apple-iphone-16-pro-max",
    description:
      "جدیدترین پرچمدار کمپانی اپل با پردازنده A18 Pro، نمایشگر ۶.۹ اینچی Super Retina XDR، دکمه Camera Control و دوربین سه‌گانه ۴۸ مگاپیکسلی با فیلمبرداری 4K 120fps.",
    shortDescription:
      "حافظه ۲۵۶ گیگابایت، پردازنده A18 Pro، صفحه ۶.۹ اینچ، بدنه تیتانیوم طبیعی",
    price: 88000000,
    originalPrice: 95000000,
    sku: "APL-IP16PM-TIT-256",
    stock: 8,
    isActive: true,
    isFeatured: true,
    type: "گوشی هوشمند پرچمدار",
    weight: "۲۲۷ گرم",
    dimensions: "۱۶۳ × ۷۷.۶ × ۸.۲۵ میلی‌متر",
    thumbnail: "/images/products/iphone-16-pro.png",
    images: [
      {
        id: "img-ip16",
        url: "/images/products/iphone-16-pro.png",
        alt: "Apple iPhone 16 Pro Max",
        order: 1,
      },
    ],
    categoryId: "cat-phones",
    category: {
      id: "cat-phones",
      name: "موبایل و تبلت",
      slug: "phones",
    },
    brandId: "brand-apple",
    brand: {
      id: "brand-apple",
      name: "اپل (Apple)",
      slug: "apple",
    },
    tags: ["موبایل", "اپل", "آیفون", "iPhone 16 Pro"],
    variants: [],
    attributes: [
      { name: "پردازنده", value: "Apple A18 Pro شش هسته‌ای" },
      { name: "باتری", value: "۴۶۸۵ میلی‌آمپر ساعت با شارژ MagSafe" },
      { name: "نمایشگر", value: "۶.۹ اینچ Super Retina XDR OLED ۱۲۰ هرتز" },
      { name: "دوربین اصلی", value: "۴۸ مگاپیکسل Fusion با زوم اپتیکال ۵ برابر" },
    ],
    rating: 4.9,
    reviewCount: 98,
    createdAt: "2024-09-10T00:00:00Z",
    updatedAt: "2024-09-12T00:00:00Z",
  },
  {
    id: "asus-zenbook-14-oled",
    title: "لپ‌تاپ ایسوس Zenbook 14 OLED",
    slug: "asus-zenbook-14-oled",
    description:
      "اولترابوک فوق‌باریک و سبک مهندسی ایسوس با پردازنده Intel Core Ultra 7 155H مجهز به NPU هوش مصنوعی، صفحه‌نمایش خیره‌کننده OLED 2.8K و ماندگاری شارژ تا ۱۵ ساعت.",
    shortDescription:
      "پردازنده Core Ultra 7، رم ۱۶ گیگابایت، حافظه ۱ ترابایت SSD، وزن ۱.۲ کیلوگرم",
    price: 62000000,
    originalPrice: 66000000,
    sku: "ASU-UX3405-OLED-16G",
    stock: 12,
    isActive: true,
    isFeatured: true,
    type: "اولترابوک / لپ‌تاپ پرچمدار",
    weight: "۱.۲ کیلوگرم",
    dimensions: "۳۱۲.۴ × ۲۲۰.۱ × ۱۴.۹ میلی‌متر",
    thumbnail: "/images/products/zenbook-14.png",
    images: [
      {
        id: "img-zenbook",
        url: "/images/products/zenbook-14.png",
        alt: "Asus Zenbook 14 OLED",
        order: 1,
      },
    ],
    categoryId: "cat-laptops",
    category: {
      id: "cat-laptops",
      name: "لپ‌تاپ و کامپیوتر",
      slug: "laptops",
    },
    brandId: "brand-asus",
    brand: {
      id: "brand-asus",
      name: "ایسوس (Asus)",
      slug: "asus",
    },
    tags: ["لپ‌تاپ", "ایسوس", "Zenbook", "اولترابوک", "OLED"],
    variants: [],
    attributes: [
      { name: "پردازنده", value: "Intel Core Ultra 7 155H با ۱۶ هسته" },
      { name: "باتری", value: "۷۵ وات‌ساعت با پشتیبانی شارژ Type-C" },
      { name: "نمایشگر", value: "۱۴ اینچ OLED 2.8K با نرخ نوسازی ۱۲۰Hz" },
      { name: "رم و حافظه", value: "۱۶GB LPDDR5X + 1TB M.2 NVMe SSD" },
    ],
    rating: 4.7,
    reviewCount: 65,
    createdAt: "2024-03-01T00:00:00Z",
    updatedAt: "2024-03-05T00:00:00Z",
  },
];

/* -------------------------------------------------------------------------- */
/*                               Helper Methods                               */
/* -------------------------------------------------------------------------- */

interface SpecRowDef {
  key: string;
  label: string;
  category?: string;
}

function getProductSpec(product: Product, key: string): string {
  switch (key) {
    case "type":
      return product.type || product.category?.name || "کالای دیجیتال";
    case "sku":
      return product.sku || "N/A";
    case "weight":
      return (
        (product.weight ? String(product.weight) : "") ||
        product.attributes?.find((a) => a.name.includes("وزن"))?.value ||
        "ثبت نشده"
      );
    case "dimensions":
      return (
        product.dimensions ||
        product.attributes?.find((a) => a.name.includes("ابعاد"))?.value ||
        "ثبت نشده"
      );
    case "description":
      return product.shortDescription || product.description || "بدون خلاصه";
    case "brand":
      return product.brand?.name || "متفرقه";
    case "category":
      return product.category?.name || "دسته‌بندی نشده";
    case "stock":
      return product.stock > 0 ? "موجود در انبار" : "ناموجود";
    case "rating":
      return `${toPersianDigits(product.rating || 0)} از ۵ (${toPersianDigits(product.reviewCount || 0)} نظر)`;
    default: {
      const attr = product.attributes?.find(
        (a) => a.name.trim().toLowerCase() === key.trim().toLowerCase(),
      );
      if (attr) return attr.value;
      if (product.specifications && product.specifications[key]) {
        return product.specifications[key];
      }
      return "—";
    }
  }
}

function checkRowDifference(products: Product[], key: string): boolean {
  if (products.length <= 1) return false;
  const first = products[0];
  if (!first) return false;
  const firstVal = getProductSpec(first, key).trim().toLowerCase();
  return products.slice(1).some((p) => {
    if (!p) return false;
    const val = getProductSpec(p, key).trim().toLowerCase();
    return val !== firstVal;
  });
}

/* -------------------------------------------------------------------------- */
/*                            Main Page Component                             */
/* -------------------------------------------------------------------------- */

export default function ComparePage() {
  const { products, removeProduct, clearCompare, addProduct } =
    useCompareStore();
  const { addToCart } = useCart();

  const [mounted, setMounted] = useState(false);
  const [highlightDiff, setHighlightDiff] = useState(false);
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleAddToCart = (product: Product) => {
    addToCart({
      productId: product.id,
      title: product.title,
      slug: product.slug,
      price: product.price,
      originalPrice: product.originalPrice,
      image: product.thumbnail || product.images?.[0]?.url,
      sku: product.sku,
      quantity: 1,
    });

    setAddedIds((prev) => ({ ...prev, [product.id]: true }));
    setTimeout(() => {
      setAddedIds((prev) => ({ ...prev, [product.id]: false }));
    }, 1500);
  };

  const handleAddAllFlagships = () => {
    clearCompare();
    FLAGSHIP_SUGGESTIONS.forEach((flagship) => {
      addProduct(flagship);
    });
  };

  // Extract all unique attribute names across all compared products
  const dynamicAttributeKeys = useMemo(() => {
    if (!products.length) return [];
    const set = new Set<string>();
    products.forEach((p) => {
      p.attributes?.forEach((attr) => {
        if (
          !["وزن", "ابعاد", "نوع", "نوع کالا"].some((ignore) =>
            attr.name.includes(ignore),
          )
        ) {
          set.add(attr.name);
        }
      });
      if (p.specifications) {
        Object.keys(p.specifications).forEach((k) => set.add(k));
      }
    });
    return Array.from(set);
  }, [products]);

  // Primary specs breakdown rows as required: Type, SKU, Weight, Dimensions, Description summary
  const primarySpecRows: SpecRowDef[] = [
    { key: "type", label: "نوع کالا" },
    { key: "sku", label: "شناسه کالا (SKU)" },
    { key: "weight", label: "وزن" },
    { key: "dimensions", label: "ابعاد" },
    { key: "description", label: "خلاصه توضیحات" },
  ];

  if (!mounted) {
    return (
      <div className="container mx-auto min-h-[60vh] px-4 py-12 flex items-center justify-center">
        <div className="text-center space-y-3">
          <ArrowLeftRight className="h-10 w-10 animate-spin text-primary mx-auto" />
          <p className="text-sm text-muted-foreground">در حال بارگذاری لیست مقایسه...</p>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------------ */
  /*                              Empty State                                 */
  /* ------------------------------------------------------------------------ */
  if (products.length === 0) {
    return (
      <div className="container mx-auto px-4 py-10 space-y-12">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link href="/" className="hover:text-primary transition-colors">
            صفحه اصلی
          </Link>
          <ChevronLeft className="h-3.5 w-3.5" />
          <span className="text-foreground font-semibold">مقایسه محصولات</span>
        </nav>

        {/* Hero Empty Notice */}
        <div className="relative overflow-hidden rounded-3xl border border-dashed border-border bg-card p-8 sm:p-12 text-center shadow-sm">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-6 shadow-inner">
            <ArrowLeftRight className="h-10 w-10" />
          </div>

          <h1 className="text-2xl sm:text-3xl font-black text-foreground mb-3">
            لیست مقایسه شما خالی است
          </h1>
          <p className="max-w-xl mx-auto text-sm sm:text-base text-muted-foreground leading-relaxed mb-8">
            برای بررسی تفاوت‌ها، مقایسه قیمت و مشخصات فنی، می‌توانید تا ۴ محصول را
            به این لیست اضافه کنید.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link href="/products">
              <Button size="lg" className="rounded-2xl gap-2 font-bold px-8 shadow-md">
                <Plus className="h-4 w-4" />
                <span>افزودن محصول به لیست مقایسه</span>
              </Button>
            </Link>

            <Button
              variant="outline"
              size="lg"
              onClick={handleAddAllFlagships}
              className="rounded-2xl gap-2 font-semibold border-primary/40 text-primary hover:bg-primary/10"
            >
              <Sparkles className="h-4 w-4" />
              <span>مقایسه پرچمداران برتر (۳ محصول پیشنهادی)</span>
            </Button>
          </div>
        </div>

        {/* Suggested Flagship Comparison Section */}
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-border pb-4">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-amber-500" />
                <h2 className="text-xl sm:text-2xl font-bold text-foreground">
                  پیشنهاد مقایسه پرچمداران بازار
                </h2>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground mt-1">
                سامسونگ اس ۲۴ اولترا در برابر آیفون ۱۶ پرو مکس در برابر زنبوک ایسوس
              </p>
            </div>

            <Button
              onClick={handleAddAllFlagships}
              className="rounded-xl gap-2 font-bold shadow-sm"
              variant="secondary"
            >
              <ArrowLeftRight className="h-4 w-4" />
              <span>مقایسه هر ۳ مدل با یک کلیک</span>
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {FLAGSHIP_SUGGESTIONS.map((product) => {
              const discountPercent =
                product.originalPrice && product.originalPrice > product.price
                  ? Math.round(
                      ((product.originalPrice - product.price) /
                        product.originalPrice) *
                        100,
                    )
                  : 0;

              return (
                <Card
                  key={product.id}
                  className="overflow-hidden rounded-3xl border border-border bg-card flex flex-col justify-between hover:shadow-lg transition-all duration-300"
                >
                  <div className="p-6 space-y-4">
                    {/* Image / Thumbnail placeholder */}
                    <div className="relative aspect-square w-full rounded-2xl bg-muted/40 border border-border/50 flex items-center justify-center p-4">
                      {product.thumbnail ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={product.thumbnail}
                          alt={product.title}
                          className="max-h-full max-w-full object-contain"
                          onError={(e) => {
                            // Gracefully replace with placeholder icon if image doesn't exist
                            e.currentTarget.style.display = "none";
                            e.currentTarget.nextElementSibling?.classList.remove("hidden");
                          }}
                        />
                      ) : null}
                      <div className="hidden flex-col items-center justify-center text-muted-foreground">
                        <Package className="h-16 w-16 mb-2 opacity-50" />
                        <span className="text-xs">{product.brand?.name}</span>
                      </div>

                      {discountPercent > 0 && (
                        <Badge
                          variant="destructive"
                          className="absolute top-3 right-3 rounded-full text-xs font-bold"
                        >
                          {toPersianDigits(discountPercent)}٪ تخفیف
                        </Badge>
                      )}

                      <Badge
                        variant="outline"
                        className="absolute top-3 left-3 bg-background/80 backdrop-blur text-[11px]"
                      >
                        {product.category?.name}
                      </Badge>
                    </div>

                    {/* Brand & Title */}
                    <div>
                      <span className="text-xs font-medium text-primary block mb-1">
                        {product.brand?.name}
                      </span>
                      <h3 className="font-bold text-foreground text-base leading-snug line-clamp-2">
                        {product.title}
                      </h3>
                    </div>

                    {/* Rating */}
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <div className="flex items-center text-amber-500 font-bold">
                        <Star className="h-3.5 w-3.5 fill-amber-400 ml-1" />
                        <span>{toPersianDigits(product.rating)}</span>
                      </div>
                      <span>({toPersianDigits(product.reviewCount)} دیدگاه)</span>
                    </div>

                    {/* Specs highlight tags */}
                    <div className="space-y-1.5 pt-2 border-t border-border">
                      {product.attributes?.slice(0, 3).map((attr, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between text-xs"
                        >
                          <span className="text-muted-foreground">{attr.name}:</span>
                          <span className="font-medium text-foreground max-w-[65%] truncate text-left" dir="ltr">
                            {attr.value}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Price */}
                    <div className="pt-2">
                      {product.originalPrice && (
                        <span className="text-xs line-through text-muted-foreground block">
                          {formatPrice(product.originalPrice)}
                        </span>
                      )}
                      <span className="text-lg font-black text-foreground block">
                        {formatPrice(product.price)}
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="p-6 pt-0 mt-auto flex flex-col gap-2">
                    <Button
                      onClick={() => addProduct(product)}
                      className="w-full rounded-xl gap-2 font-bold shadow-sm"
                    >
                      <ArrowLeftRight className="h-4 w-4" />
                      <span>افزودن به مقایسه</span>
                    </Button>
                    <Link href={`/products/${product.slug}`} className="w-full">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full rounded-xl text-xs text-muted-foreground hover:text-foreground"
                      >
                        مشاهده جزئیات کالا
                      </Button>
                    </Link>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------------ */
  /*                          Active Comparison Table                         */
  /* ------------------------------------------------------------------------ */
  return (
    <div className="container mx-auto px-4 py-8 space-y-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link href="/" className="hover:text-primary transition-colors">
          صفحه اصلی
        </Link>
        <ChevronLeft className="h-3.5 w-3.5" />
        <Link href="/products" className="hover:text-primary transition-colors">
          محصولات
        </Link>
        <ChevronLeft className="h-3.5 w-3.5" />
        <span className="text-foreground font-semibold">مقایسه کالاها</span>
      </nav>

      {/* Header & Controls Bar */}
      <div className="rounded-3xl border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <ArrowLeftRight className="h-5 w-5" />
              </div>
              <h1 className="text-2xl font-black text-foreground">
                مقایسه هوشمند محصولات
              </h1>
              <Badge variant="secondary" className="font-bold text-xs">
                {toPersianDigits(products.length)} از {toPersianDigits(MAX_COMPARE_PRODUCTS)} محصول
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground pr-13">
              بررسی همزمان مشخصات، قابلیت‌ها، قیمت و تفاوت‌های کالاهای انتخاب‌شده
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 sm:gap-4">
            {/* Highlight Differences Toggle */}
            <div className="flex items-center gap-2.5 rounded-2xl border border-border bg-muted/30 px-3.5 py-2">
              <Switch
                id="highlight-diff"
                checked={highlightDiff}
                onCheckedChange={setHighlightDiff}
              />
              <label
                htmlFor="highlight-diff"
                className="text-xs sm:text-sm font-semibold text-foreground cursor-pointer select-none flex items-center gap-1.5"
              >
                <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                <span>برجسته‌سازی تفاوت‌ها</span>
              </label>
            </div>

            {/* Add More Products Button */}
            {products.length < MAX_COMPARE_PRODUCTS && (
              <Link href="/products">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-2xl gap-1.5 font-semibold text-xs border-dashed"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>افزودن کالای دیگر</span>
                </Button>
              </Link>
            )}

            {/* Clear Compare Button */}
            <Button
              variant="ghost"
              size="sm"
              onClick={clearCompare}
              className="rounded-2xl gap-1.5 font-semibold text-xs text-red-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>پاک کردن همه</span>
            </Button>
          </div>
        </div>
      </div>

      {/* -------------------------------------------------------------------- */}
      {/*                       Side-by-Side Comparison Table                  */}
      {/* -------------------------------------------------------------------- */}
      <div className="relative overflow-x-auto rounded-3xl border border-border bg-card shadow-sm">
        <table className="w-full text-sm border-collapse min-w-[720px] table-fixed">
          {/* Table Header: Product Top Cards */}
          <thead>
            <tr className="border-b border-border bg-muted/20">
              {/* Sticky Column: Spec Titles */}
              <th className="sticky right-0 z-20 w-44 sm:w-56 p-4 text-right align-top bg-card/95 backdrop-blur border-l border-border shadow-[2px_0_6px_-2px_rgba(0,0,0,0.06)]">
                <div className="sticky top-24 pt-2">
                  <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider block mb-1">
                    مشخصات فنی
                  </span>
                  <span className="text-base font-extrabold text-foreground block">
                    کالاهای انتخابی
                  </span>
                  {highlightDiff && (
                    <div className="mt-3 flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-2 py-1 text-[11px] text-amber-700 dark:text-amber-400 font-medium">
                      <Sparkles className="h-3 w-3 shrink-0" />
                      <span>ردیف‌های دارای تفاوت با رنگ متمایز نشان داده شده‌اند.</span>
                    </div>
                  )}
                </div>
              </th>

              {/* Product Columns */}
              {products.map((product) => {
                const discountPercent =
                  product.originalPrice && product.originalPrice > product.price
                    ? Math.round(
                        ((product.originalPrice - product.price) /
                          product.originalPrice) *
                          100,
                      )
                    : 0;
                const isAdded = !!addedIds[product.id];

                return (
                  <th
                    key={product.id}
                    className="p-4 sm:p-6 text-right align-top border-l border-border last:border-l-0"
                    style={{ width: `${Math.floor(100 / (products.length + 1))}%` }}
                  >
                    <div className="space-y-4">
                      {/* Top Action: Remove */}
                      <div className="flex items-center justify-between">
                        <Badge variant="outline" className="text-[10px] font-bold">
                          {product.brand?.name || "برند"}
                        </Badge>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeProduct(product.id)}
                          className="h-7 w-7 rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                          title="حذف از مقایسه"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>

                      {/* Product Image */}
                      <div className="relative aspect-square w-full max-w-[200px] mx-auto rounded-2xl bg-muted/40 border border-border/60 flex items-center justify-center p-3">
                        {product.thumbnail || product.images?.[0]?.url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={product.thumbnail || product.images?.[0]?.url}
                            alt={product.title}
                            className="max-h-full max-w-full object-contain"
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                              e.currentTarget.nextElementSibling?.classList.remove("hidden");
                            }}
                          />
                        ) : null}
                        <div className="hidden flex-col items-center justify-center text-muted-foreground">
                          <Package className="h-12 w-12 opacity-40 mb-1" />
                          <span className="text-[10px]">{product.brand?.name}</span>
                        </div>

                        {discountPercent > 0 && (
                          <Badge
                            variant="destructive"
                            className="absolute top-2 right-2 rounded-full px-2 py-0.5 text-[10px] font-bold shadow-sm"
                          >
                            {toPersianDigits(discountPercent)}٪
                          </Badge>
                        )}
                      </div>

                      {/* Title & Link */}
                      <div className="min-h-[48px]">
                        <Link
                          href={`/products/${product.slug}`}
                          className="font-bold text-foreground hover:text-primary transition-colors text-sm sm:text-base leading-snug line-clamp-2"
                        >
                          {product.title}
                        </Link>
                      </div>

                      {/* Rating & Reviews */}
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <div className="flex items-center text-amber-500 font-bold">
                          <Star className="h-3.5 w-3.5 fill-amber-400 ml-1" />
                          <span>{toPersianDigits(product.rating || 0)}</span>
                        </div>
                        <span>({toPersianDigits(product.reviewCount || 0)} دیدگاه)</span>
                      </div>

                      {/* Price & Discount */}
                      <div className="space-y-0.5 pt-1">
                        {product.originalPrice && product.originalPrice > product.price && (
                          <span className="text-xs line-through text-muted-foreground block">
                            {formatPrice(product.originalPrice)}
                          </span>
                        )}
                        <span className="text-base sm:text-lg font-black text-foreground block">
                          {formatPrice(product.price)}
                        </span>
                      </div>

                      {/* Stock Status Badge */}
                      <div>
                        {product.stock > 0 ? (
                          <Badge
                            variant="outline"
                            className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 text-[11px] font-medium"
                          >
                            <Check className="h-3 w-3 ml-1" />
                            موجود در انبار
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20 text-[11px] font-medium"
                          >
                            <X className="h-3 w-3 ml-1" />
                            اتمام موجودی
                          </Badge>
                        )}
                      </div>

                      {/* Add to Cart Button */}
                      <div>
                        <Button
                          className="w-full rounded-xl gap-1.5 font-bold shadow-sm"
                          size="sm"
                          disabled={product.stock <= 0}
                          onClick={() => handleAddToCart(product)}
                          variant={isAdded ? "secondary" : "default"}
                        >
                          {isAdded ? (
                            <>
                              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                              <span className="text-emerald-600">افزوده شد!</span>
                            </>
                          ) : (
                            <>
                              <ShoppingCart className="h-4 w-4" />
                              <span>افزودن به سبد</span>
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </th>
                );
              })}

              {/* Empty slot placeholder if < 4 */}
              {products.length < MAX_COMPARE_PRODUCTS && (
                <th
                  className="p-6 text-center align-middle border-l border-border bg-muted/10"
                  style={{ width: `${Math.floor(100 / (products.length + 1))}%` }}
                >
                  <Link
                    href="/products"
                    className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-border/80 hover:border-primary/60 rounded-3xl group transition-all h-full min-h-[280px]"
                  >
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted group-hover:bg-primary/10 group-hover:text-primary transition-colors text-muted-foreground mb-3">
                      <Plus className="h-6 w-6" />
                    </div>
                    <span className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">
                      افزودن کالای دیگر
                    </span>
                    <span className="text-xs text-muted-foreground mt-1 max-w-[140px] text-center">
                      می‌توانید تا {toPersianDigits(MAX_COMPARE_PRODUCTS)} کالا را همزمان مقایسه کنید
                    </span>
                  </Link>
                </th>
              )}
            </tr>
          </thead>

          {/* Table Body: Specs breakdown rows */}
          <tbody className="divide-y divide-border">
            {/* Section Header: General Specs */}
            <tr className="bg-muted/40 font-bold">
              <td
                colSpan={products.length + 1 + (products.length < MAX_COMPARE_PRODUCTS ? 1 : 0)}
                className="p-3 pr-6 text-xs text-primary uppercase tracking-wider font-extrabold"
              >
                مشخصات کلیدی و عمومی
              </td>
            </tr>

            {/* Required Primary Specs: Type, SKU, Weight, Dimensions, Description summary */}
            {primarySpecRows.map((specRow) => {
              const isDiff = checkRowDifference(products, specRow.key);
              const isHighlighted = highlightDiff && isDiff;

              return (
                <tr
                  key={specRow.key}
                  className={cn(
                    "transition-colors",
                    isHighlighted
                      ? "bg-amber-500/10 dark:bg-amber-950/30"
                      : "hover:bg-muted/20",
                  )}
                >
                  {/* Row Header */}
                  <td className="sticky right-0 z-10 p-4 font-semibold text-foreground bg-card/95 backdrop-blur border-l border-border shadow-[2px_0_6px_-2px_rgba(0,0,0,0.06)]">
                    <div className="flex items-center gap-1.5">
                      <span>{specRow.label}</span>
                      {isDiff && highlightDiff && (
                        <span className="inline-block h-2 w-2 rounded-full bg-amber-500" title="دارای تفاوت" />
                      )}
                    </div>
                  </td>

                  {/* Value for each product */}
                  {products.map((product) => {
                    const value = getProductSpec(product, specRow.key);
                    return (
                      <td
                        key={product.id}
                        className={cn(
                          "p-4 text-right align-top border-l border-border last:border-l-0 text-foreground",
                          specRow.key === "description"
                            ? "text-xs text-muted-foreground leading-relaxed"
                            : "font-medium text-sm",
                        )}
                      >
                        {value}
                      </td>
                    );
                  })}

                  {/* Empty Slot column */}
                  {products.length < MAX_COMPARE_PRODUCTS && (
                    <td className="p-4 text-center border-l border-border text-muted-foreground text-xs">
                      —
                    </td>
                  )}
                </tr>
              );
            })}

            {/* Section Header: Dynamic Specs if available */}
            {dynamicAttributeKeys.length > 0 && (
              <>
                <tr className="bg-muted/40 font-bold">
                  <td
                    colSpan={
                      products.length +
                      1 +
                      (products.length < MAX_COMPARE_PRODUCTS ? 1 : 0)
                    }
                    className="p-3 pr-6 text-xs text-primary uppercase tracking-wider font-extrabold"
                  >
                    سایر مشخصات و قابلیت‌ها
                  </td>
                </tr>

                {dynamicAttributeKeys.map((attrKey) => {
                  const isDiff = checkRowDifference(products, attrKey);
                  const isHighlighted = highlightDiff && isDiff;

                  return (
                    <tr
                      key={attrKey}
                      className={cn(
                        "transition-colors",
                        isHighlighted
                          ? "bg-amber-500/10 dark:bg-amber-950/30"
                          : "hover:bg-muted/20",
                      )}
                    >
                      <td className="sticky right-0 z-10 p-4 font-semibold text-foreground bg-card/95 backdrop-blur border-l border-border shadow-[2px_0_6px_-2px_rgba(0,0,0,0.06)]">
                        <div className="flex items-center gap-1.5">
                          <span>{attrKey}</span>
                          {isDiff && highlightDiff && (
                            <span
                              className="inline-block h-2 w-2 rounded-full bg-amber-500"
                              title="دارای تفاوت"
                            />
                          )}
                        </div>
                      </td>

                      {products.map((product) => {
                        const val = getProductSpec(product, attrKey);
                        return (
                          <td
                            key={product.id}
                            className="p-4 text-right align-top border-l border-border last:border-l-0 text-foreground text-sm font-medium"
                          >
                            {val}
                          </td>
                        );
                      })}

                      {products.length < MAX_COMPARE_PRODUCTS && (
                        <td className="p-4 text-center border-l border-border text-muted-foreground text-xs">
                          —
                        </td>
                      )}
                    </tr>
                  );
                })}
              </>
            )}

            {/* Bottom Row: Actions repeater */}
            <tr className="bg-muted/10">
              <td className="sticky right-0 z-10 p-4 font-bold text-foreground bg-card/95 backdrop-blur border-l border-border shadow-[2px_0_6px_-2px_rgba(0,0,0,0.06)]">
                اقدامات
              </td>
              {products.map((product) => {
                const isAdded = !!addedIds[product.id];
                return (
                  <td
                    key={product.id}
                    className="p-4 border-l border-border last:border-l-0"
                  >
                    <div className="flex flex-col gap-2">
                      <Button
                        size="sm"
                        disabled={product.stock <= 0}
                        onClick={() => handleAddToCart(product)}
                        className="w-full rounded-xl gap-1.5 font-bold shadow-sm"
                        variant={isAdded ? "secondary" : "default"}
                      >
                        {isAdded ? (
                          <>
                            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                            <span className="text-emerald-600">افزوده شد!</span>
                          </>
                        ) : (
                          <>
                            <ShoppingCart className="h-4 w-4" />
                            <span>خرید کالا</span>
                          </>
                        )}
                      </Button>
                      <Link href={`/products/${product.slug}`} className="w-full">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="w-full rounded-xl text-xs text-muted-foreground hover:text-foreground"
                        >
                          صفحه محصول
                        </Button>
                      </Link>
                    </div>
                  </td>
                );
              })}
              {products.length < MAX_COMPARE_PRODUCTS && (
                <td className="p-4 text-center border-l border-border text-muted-foreground text-xs">
                  —
                </td>
              )}
            </tr>
          </tbody>
        </table>
      </div>

      {/* Comparison Guide Card */}
      <div className="rounded-3xl border border-border bg-card p-6 flex flex-col sm:flex-row items-center gap-4 text-xs text-muted-foreground shadow-sm">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Info className="h-5 w-5" />
        </div>
        <div className="space-y-1">
          <span className="font-bold text-foreground block">
            راهنمای مقایسه کالاها:
          </span>
          <p>
            با فعال کردن کلید «برجسته‌سازی تفاوت‌ها»، ردیف‌هایی که مقادیر متفاوتی در میان
            کالاهای انتخابی دارند به رنگ مشخص نمایش داده می‌شوند تا تصمیم‌گیری سریع‌تر و
            دقیق‌تر باشد.
          </p>
        </div>
      </div>
    </div>
  );
}
