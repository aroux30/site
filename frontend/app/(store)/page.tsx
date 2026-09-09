"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Truck,
  Shield,
  RotateCcw,
  Headphones,
  ChevronLeft,
  Star,
  Zap,
  ShoppingCart,
  Package,
  Sparkles,
  Smartphone,
  Laptop,
  Shirt,
  Home,
  Dumbbell,
  BookOpen,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import { useCart } from "@/hooks/use-cart";
import {
  fetchCategories,
  fetchProducts,
  type ApiCategory,
  type ApiProduct,
} from "@/lib/api/services";

/* -------------------------------------------------------------------------- */
/*                               Fallback Data                                */
/* -------------------------------------------------------------------------- */

const fallbackCategories: ApiCategory[] = [
  { id: "c1", name: "موبایل و دیجیتال", slug: "phones", is_active: true },
  { id: "c2", name: "لپ‌تاپ و کامپیوتر", slug: "laptops", is_active: true },
  { id: "c3", name: "لوازم صوتی و تصویر", slug: "audio-video", is_active: true },
  { id: "c4", name: "ساعت و دستبند هوشمند", slug: "smartwatch", is_active: true },
  { id: "c5", name: "مد و پوشاک", slug: "clothing", is_active: true },
  { id: "c6", name: "خانه و آشپزخانه", slug: "home", is_active: true },
  { id: "c7", name: "زیبایی و سلامت", slug: "beauty", is_active: true },
  { id: "c8", name: "کتاب و لوازم‌التحریر", slug: "books", is_active: true },
];

const fallbackFeaturedProducts: ApiProduct[] = [
  {
    id: "f1",
    name: "گوشی موبایل سامسونگ Galaxy S24 Ultra",
    slug: "samsung-galaxy-s24-ultra",
    category_id: "c1",
    min_price: 65000000,
    max_price: 72000000,
    variant_count: 4,
    is_active: true,
    is_featured: true,
    short_description: "پرچمدار بی‌رقیب سامسونگ با دوربین ۲۰۰ مگاپیکسلی و قلم هوشمند S-Pen",
  },
  {
    id: "f2",
    name: "لپ‌تاپ ایسوس ROG Zephyrus G16",
    slug: "asus-rog-zephyrus-g16",
    category_id: "c2",
    min_price: 89000000,
    max_price: 98000000,
    variant_count: 2,
    is_active: true,
    is_featured: true,
    short_description: "لپ‌تاپ گیمینگ قدرتمند با نمایشگر OLED و پردازنده Core Ultra 9",
  },
  {
    id: "f3",
    name: "هدفون بی‌سیم سونی WH-1000XM5",
    slug: "sony-wh-1000xm5",
    category_id: "c3",
    min_price: 18500000,
    max_price: 21000000,
    variant_count: 2,
    is_active: true,
    is_featured: true,
    short_description: "بهترین نویزکنسلینگ بازار با صدای شفاف Hi-Res و ارگونومی فوق‌العاده",
  },
  {
    id: "f4",
    name: "ساعت هوشمند اپل واچ سری ۹",
    slug: "apple-watch-series-9",
    category_id: "c4",
    min_price: 24000000,
    max_price: 27500000,
    variant_count: 3,
    is_active: true,
    is_featured: true,
    short_description: "همراه سلامت هوشمند با نمایشگر همیشه روشن و پایش دقیق ضربان قلب",
  },
  {
    id: "f5",
    name: "گوشی شیائومی ۱۴ پرو",
    slug: "xiaomi-14-pro",
    category_id: "c1",
    min_price: 48000000,
    max_price: 52000000,
    variant_count: 2,
    is_active: true,
    is_featured: true,
    short_description: "طراحی شیک، لنزهای سفارشی لایکا و پردازنده اسنپ‌دراگون نسل ۳",
  },
  {
    id: "f6",
    name: "مک‌بوک ایر M3 اپل (۱۵ اینچ)",
    slug: "apple-macbook-air-m3-15",
    category_id: "c2",
    min_price: 79000000,
    max_price: 85000000,
    variant_count: 3,
    is_active: true,
    is_featured: true,
    short_description: "فوق‌باریک با شارژدهی ۱۸ ساعته و قدرت پردازشی فوق‌العاده تراشه M3",
  },
  {
    id: "f7",
    name: "اسپیکر قابل حمل جی‌بی‌ال Charge 5",
    slug: "jbl-charge-5",
    category_id: "c3",
    min_price: 8200000,
    max_price: 9500000,
    variant_count: 5,
    is_active: true,
    is_featured: true,
    short_description: "ضدآب، باتری ۲۰ ساعته و بیس کوبنده حرفه‌ای مخصوص مسافرت",
  },
  {
    id: "f8",
    name: "ایرپاد پرو نسل ۲ اپل (تایپ سی)",
    slug: "apple-airpods-pro-2-usbc",
    category_id: "c3",
    min_price: 13500000,
    max_price: 15000000,
    variant_count: 1,
    is_active: true,
    is_featured: true,
    short_description: "کیفیت صدای فراگیر، شارژ MagSafe با پورت تایپ سی جدید",
  },
];

const fallbackBestSellers: ApiProduct[] = [
  {
    id: "b1",
    name: "کنسول بازی سونی پلی‌استیشن ۵ اسلیم",
    slug: "sony-playstation-5-slim",
    category_id: "c1",
    min_price: 34500000,
    max_price: 38000000,
    variant_count: 2,
    is_active: true,
    is_featured: false,
    short_description: "طراحی جدید باریک با حافظه ۱ ترابایت و پشتیبانی از رزولوشن 4K 120Hz",
  },
  {
    id: "b2",
    name: "تلویزیون هوشمند ۶۵ اینچ کیولد سامسونگ",
    slug: "samsung-65-qled-4k",
    category_id: "c3",
    min_price: 62000000,
    max_price: 68000000,
    variant_count: 1,
    is_active: true,
    is_featured: false,
    short_description: "پنل QLED با کیفیت تصویر خیره‌کننده و پردازنده کوانتومی فورکی",
  },
  {
    id: "b3",
    name: "تبلت اپل آیپد ایر ۱۱ اینچ M2",
    slug: "apple-ipad-air-11-m2",
    category_id: "c1",
    min_price: 43000000,
    max_price: 47000000,
    variant_count: 4,
    is_active: true,
    is_featured: false,
    short_description: "نمایشگر Liquid Retina و پشتیبانی از قلم هوشمند Apple Pencil Pro",
  },
  {
    id: "b4",
    name: "قهوه‌ساز و اسپرسوساز دلونگی Dedica",
    slug: "delonghi-dedica-espresso",
    category_id: "c6",
    min_price: 11200000,
    max_price: 13000000,
    variant_count: 3,
    is_active: true,
    is_featured: false,
    short_description: "فشار بخار ۱۵ بار با بدنه تمام استیل و فوم‌ساز حرفه‌ای شیر",
  },
  {
    id: "b5",
    name: "دوربین بدون آینه سونی Alpha A7 IV",
    slug: "sony-alpha-a7-iv",
    category_id: "c1",
    min_price: 115000000,
    max_price: 125000000,
    variant_count: 2,
    is_active: true,
    is_featured: false,
    short_description: "سنسور ۳۳ مگاپیکسل فول‌فریم با فوکوس هوش مصنوعی روی چشم",
  },
  {
    id: "b6",
    name: "جاروبرقی روباتیک شیائومی مدل X10+",
    slug: "xiaomi-robot-vacuum-x10-plus",
    category_id: "c6",
    min_price: 39000000,
    max_price: 43000000,
    variant_count: 1,
    is_active: true,
    is_featured: false,
    short_description: "تخلیه خودکار زباله، شستشوی خودکار پد تی و ناوبری پیشرفته لیزری",
  },
  {
    id: "b7",
    name: "ساعت هوشمند گارمین Fenix 7 Pro",
    slug: "garmin-fenix-7-pro",
    category_id: "c4",
    min_price: 58000000,
    max_price: 64000000,
    variant_count: 2,
    is_active: true,
    is_featured: false,
    short_description: "شارژ خورشیدی، نقشه‌های توپوگرافی و چراغ‌قوه LED داخلی ورزشی",
  },
  {
    id: "b8",
    name: "مانیتور ۳۴ اینچ خمیده اولتراواید بنکیو",
    slug: "benq-34-ultrawide-curved",
    category_id: "c2",
    min_price: 36000000,
    max_price: 40000000,
    variant_count: 1,
    is_active: true,
    is_featured: false,
    short_description: "رزولوشن WQHD با نرخ تازه‌سازی ۱۴۴ هرتز مناسب گیمینگ و برنامه‌نویسی",
  },
];

const valuePropositions = [
  {
    icon: Truck,
    title: "ارسال سریع و رایگان",
    desc: "تحویل فوری در تهران و پست پیشتاز سراسر کشور",
  },
  {
    icon: Shield,
    title: "ضمانت اصالت کالا",
    desc: "۱۰۰٪ گارانتی اصالت تمامی کالاها و برندها",
  },
  {
    icon: RotateCcw,
    title: "۷ روز ضمانت بازگشت",
    desc: "امکان مرجوعی کالا در صورت عدم رضایت یا مغایرت",
  },
  {
    icon: Headphones,
    title: "پشتیبانی ۲۴/۷",
    desc: "مشاوره تخصصی قبل از خرید و پاسخگویی مداوم",
  },
];

function getCategoryIcon(slug: string) {
  switch (slug) {
    case "phones":
      return Smartphone;
    case "laptops":
      return Laptop;
    case "clothing":
      return Shirt;
    case "home":
      return Home;
    case "beauty":
      return Sparkles;
    case "sports":
      return Dumbbell;
    case "books":
      return BookOpen;
    default:
      return Package;
  }
}

/* -------------------------------------------------------------------------- */
/*                               Sub-Components                               */
/* -------------------------------------------------------------------------- */

function SectionHeader({
  title,
  subtitle,
  href,
  linkText = "مشاهده همه",
}: {
  title: string;
  subtitle?: string;
  href: string;
  linkText?: string;
}) {
  return (
    <div className="mb-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 border-b border-border pb-4">
      <div>
        <h2 className="text-xl sm:text-2xl font-bold text-foreground flex items-center gap-2">
          <span className="h-6 w-1.5 rounded-full bg-primary inline-block" />
          {title}
        </h2>
        {subtitle && (
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            {subtitle}
          </p>
        )}
      </div>
      <Link
        href={href}
        className="group inline-flex items-center gap-1.5 text-sm font-semibold text-primary transition-colors hover:text-primary/80 self-start sm:self-auto"
      >
        <span>{linkText}</span>
        <ChevronLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
      </Link>
    </div>
  );
}

function ProductCard({ product }: { product: ApiProduct }) {
  const { addToCart } = useCart();
  const [added, setAdded] = useState(false);

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
    <Card className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-card transition-all duration-300 hover:-translate-y-1 hover:shadow-xl">
      <Link href={`/products/${product.slug}`} className="flex flex-col h-full">
        {/* Image Area */}
        <div className="relative aspect-square overflow-hidden bg-muted/60 p-4">
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

        {/* Content */}
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
          <div className="mb-4 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
            <span className="font-medium text-foreground">۴.۷</span>
            <span>(۳۵ نظر)</span>
          </div>

          {/* Price */}
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

      {/* Quick Add To Cart Button */}
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
  );
}

function ProductSkeleton() {
  return (
    <Card className="overflow-hidden rounded-2xl">
      <Skeleton className="aspect-square w-full" />
      <div className="p-4 space-y-3">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
        <Skeleton className="h-5 w-2/5" />
        <Skeleton className="h-9 w-full rounded-xl mt-4" />
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/*                               Main Home Page                               */
/* -------------------------------------------------------------------------- */

export default function StoreHomePage() {
  const [categories, setCategories] = useState<ApiCategory[]>(fallbackCategories);
  const [featuredProducts, setFeaturedProducts] = useState<ApiProduct[]>(
    fallbackFeaturedProducts,
  );
  const [bestSellers, setBestSellers] = useState<ApiProduct[]>(fallbackBestSellers);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function loadData() {
      try {
        const [catRes, featRes, bestRes] = await Promise.allSettled([
          fetchCategories({ is_active: true, page_size: 12 }),
          fetchProducts({
            sort_by: "created_at",
            sort_order: "desc",
            page_size: 8,
          }),
          fetchProducts({
            sort_by: "price",
            sort_order: "desc",
            page_size: 8,
          }),
        ]);

        if (!active) return;

        if (catRes.status === "fulfilled" && catRes.value.items?.length > 0) {
          setCategories(catRes.value.items);
        }
        if (featRes.status === "fulfilled" && featRes.value.items?.length > 0) {
          setFeaturedProducts(featRes.value.items);
        }
        if (bestRes.status === "fulfilled" && bestRes.value.items?.length > 0) {
          setBestSellers(bestRes.value.items);
        }
      } catch (e) {
        console.warn("Home page API fetch failed, fallback mock data in use:", e);
      } finally {
        if (active) setLoading(false);
      }
    }

    loadData();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="container mx-auto px-4 py-6 sm:py-10 space-y-16 sm:space-y-20">
      {/* ============================================================ */}
      {/*  1 · Hero Banner with Persian CTAs                           */}
      {/* ============================================================ */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-l from-primary-800 via-primary-700 to-indigo-900 px-6 py-14 text-white shadow-2xl sm:px-12 sm:py-20 lg:py-24">
        {/* Atmospheric Glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 -left-24 h-96 w-96 rounded-full bg-primary-400/20 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-24 -right-24 h-96 w-96 rounded-full bg-indigo-400/20 blur-3xl"
        />

        <div className="relative z-10 max-w-2xl">
          <Badge className="mb-4 bg-white/15 hover:bg-white/25 text-white border-none rounded-full px-3 py-1 text-xs gap-1.5 backdrop-blur-md">
            <Sparkles className="h-3.5 w-3.5 text-amber-300" />
            جشنواره شگفت‌انگیز فصل
          </Badge>

          <h1 className="mb-5 text-3xl font-black leading-tight sm:text-4xl lg:text-5xl">
            بهترین‌ها رو آنلاین، سریع و مطمئن بخر
          </h1>

          <p className="mb-8 max-w-xl text-sm leading-relaxed text-white/85 sm:text-base lg:text-lg">
            دسترسی به هزاران کالای دیجیتال، لوازم خانگی و گجت‌های هوشمند از برترین
            برندهای روز دنیا با ضمانت اصالت کالا و ارسال سریع به تمام نقاط ایران.
          </p>

          <div className="flex flex-wrap items-center gap-4">
            <Link href="/products">
              <Button
                size="lg"
                className="h-12 rounded-2xl bg-white px-7 font-bold text-primary hover:bg-white/90 shadow-lg text-sm sm:text-base"
              >
                مشاهده محصولات
                <ChevronLeft className="mr-2 h-4 w-4" />
              </Button>
            </Link>

            <Link href="/products?sort_by=price&sort_order=desc">
              <Button
                size="lg"
                variant="outline"
                className="h-12 rounded-2xl border-2 border-white/30 bg-white/10 px-6 font-semibold text-white backdrop-blur-md hover:bg-white/20 hover:text-white text-sm sm:text-base"
              >
                <Zap className="ml-2 h-4 w-4 text-amber-300" />
                تخفیف‌های شگفت‌انگیز
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  2 · Value Propositions (4 Features)                         */}
      {/* ============================================================ */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {valuePropositions.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className="flex items-center gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm transition-all duration-300 hover:border-primary/40 hover:shadow-md"
            >
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Icon className="h-6 w-6" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-foreground">
                  {item.title}
                </h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {item.desc}
                </p>
              </div>
            </div>
          );
        })}
      </section>

      {/* ============================================================ */}
      {/*  3 · Categories Grid                                         */}
      {/* ============================================================ */}
      <section>
        <SectionHeader
          title="دسته‌بندی‌های محبوب"
          subtitle="محصولات منتخب از میان برترین دسته‌ها"
          href="/products"
          linkText="مشاهده تمام دسته‌ها"
        />

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {categories.map((cat) => {
            const Icon = getCategoryIcon(cat.slug);
            return (
              <Link
                key={cat.id}
                href={`/products?category_id=${cat.id}&category_slug=${cat.slug}`}
                className="group flex flex-col items-center justify-center rounded-2xl border border-border bg-card p-4 text-center transition-all duration-200 hover:-translate-y-1 hover:border-primary hover:shadow-md"
              >
                <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/5 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  {cat.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={cat.image_url}
                      alt={cat.name}
                      className="h-8 w-8 object-contain"
                    />
                  ) : (
                    <Icon className="h-7 w-7" />
                  )}
                </div>
                <span className="line-clamp-1 text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                  {cat.name}
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  4 · Featured Products Section                               */}
      {/* ============================================================ */}
      <section>
        <SectionHeader
          title="جدیدترین و منتخب‌ترین محصولات"
          subtitle="بروزرسانی روزانه با جدیدترین تکنولوژی‌ها"
          href="/products?sort_by=created_at&sort_order=desc"
          linkText="مشاهده همه کالاها"
        />

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <ProductSkeleton key={i} />
              ))
            : featuredProducts.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  5 · Special Promo Banner                                    */}
      {/* ============================================================ */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-amber-500 via-orange-500 to-red-600 p-8 text-white shadow-xl">
        <div className="relative z-10 flex flex-col items-center justify-between gap-6 md:flex-row text-center md:text-start">
          <div>
            <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-bold uppercase tracking-wider backdrop-blur-sm">
              پیشنهاد ویژه کاربران
            </span>
            <h3 className="mt-3 text-2xl sm:text-3xl font-black">
              ارسال کاملاً رایگان برای سبدهای بالای ۵۰۰ هزار تومان
            </h3>
            <p className="mt-2 text-sm text-white/90">
              بدون نیاز به کد تخفیف، فقط با اضافه کردن کالاها به سبد خرید خود
            </p>
          </div>
          <Link href="/products">
            <Button
              size="lg"
              className="h-12 rounded-2xl bg-white font-bold text-orange-600 hover:bg-white/90 shadow-md whitespace-nowrap px-8"
            >
              شروع خرید هوشمند
            </Button>
          </Link>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  6 · Best Sellers Section                                    */}
      {/* ============================================================ */}
      <section>
        <SectionHeader
          title="پرفروش‌ترین محصولات"
          subtitle="محبوب‌ترین انتخاب‌های خریداران در هفته گذشته"
          href="/products?sort_by=price&sort_order=desc"
          linkText="مشاهده پرفروش‌ها"
        />

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <ProductSkeleton key={i} />
              ))
            : bestSellers.map((p) => <ProductCard key={p.id} product={p} />)}
        </div>
      </section>
    </div>
  );
}
