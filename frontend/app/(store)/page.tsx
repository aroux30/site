import Link from "next/link";
import type { Metadata } from "next";
import {
  Truck,
  Shield,
  RotateCcw,
  Headphones,
  ChevronLeft,
  Star,
  Zap,
  Smartphone,
  Shirt,
  Home,
  Sparkles,
  Dumbbell,
  BookOpen,
  ShoppingCart,
  Package,
  Users,
  Mail,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { formatPrice } from "@/lib/utils";

export const metadata: Metadata = {
  title: "صفحه اصلی فروشگاه",
};

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const categories = [
  { name: "الکترونیک", slug: "electronics", icon: Smartphone, count: 1240 },
  { name: "پوشاک", slug: "clothing", icon: Shirt, count: 860 },
  { name: "خانه و آشپزخانه", slug: "home-kitchen", icon: Home, count: 530 },
  { name: "زیبایی و سلامت", slug: "beauty-health", icon: Sparkles, count: 720 },
  { name: "ورزش و سفر", slug: "sports-travel", icon: Dumbbell, count: 410 },
  {
    name: "کتاب و لوازم التحریر",
    slug: "books-stationery",
    icon: BookOpen,
    count: 980,
  },
];

const featuredProducts = [
  {
    id: 1,
    title: "گوشی موبایل سامسونگ Galaxy A54",
    price: 12_500_000,
    originalPrice: 14_000_000,
    rating: 4.5,
    reviews: 128,
  },
  {
    id: 2,
    title: "لپ‌تاپ ایسوس VivoBook 15",
    price: 32_000_000,
    originalPrice: null,
    rating: 4.7,
    reviews: 64,
  },
  {
    id: 3,
    title: "هدفون بی‌سیم سونی WH-1000XM5",
    price: 9_800_000,
    originalPrice: 11_000_000,
    rating: 4.8,
    reviews: 256,
  },
  {
    id: 4,
    title: "ساعت هوشمند شیائومی Band 8",
    price: 2_500_000,
    originalPrice: 2_800_000,
    rating: 4.3,
    reviews: 312,
  },
];

const newestProducts = [
  {
    id: 5,
    title: "کتاب اصول طراحی نرم‌افزار",
    price: 185_000,
    originalPrice: null,
    rating: 4.6,
    reviews: 42,
  },
  {
    id: 6,
    title: "تی‌شرت مردانه طرح کلاسیک",
    price: 450_000,
    originalPrice: 550_000,
    rating: 4.2,
    reviews: 89,
  },
  {
    id: 7,
    title: "کیف چرم زنانه",
    price: 1_200_000,
    originalPrice: null,
    rating: 4.4,
    reviews: 56,
  },
  {
    id: 8,
    title: "عطر مردانه بلو شنل",
    price: 3_500_000,
    originalPrice: 4_000_000,
    rating: 4.9,
    reviews: 178,
  },
];

const features = [
  {
    icon: Truck,
    title: "ارسال رایگان",
    desc: "برای سفارش‌های بالای ۵۰۰ هزار تومان",
  },
  {
    icon: Shield,
    title: "ضمانت اصالت",
    desc: "تضمین اصل بودن تمامی محصولات",
  },
  {
    icon: RotateCcw,
    title: "۷ روز ضمانت بازگشت",
    desc: "امکان بازگشت کالا تا ۷ روز",
  },
  {
    icon: Headphones,
    title: "پشتیبانی ۲۴/۷",
    desc: "پاسخگویی در تمام ساعات شبانه‌روز",
  },
];

const heroStats = [
  { icon: Package, label: "۱۰,۰۰۰+ محصول" },
  { icon: Users, label: "۵۰,۰۰۰+ مشتری" },
  { icon: Truck, label: "ارسال رایگان" },
  { icon: Headphones, label: "پشتیبانی ۲۴/۷" },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function discountPercent(original: number, current: number) {
  return Math.round(((original - current) / original) * 100);
}

function renderStars(rating: number) {
  const full = Math.floor(rating);
  const hasHalf = rating - full >= 0.5;
  const stars: React.ReactNode[] = [];

  for (let i = 0; i < full; i++) {
    stars.push(
      <Star
        key={`full-${i}`}
        className="h-3.5 w-3.5 fill-amber-400 text-amber-400"
      />,
    );
  }
  if (hasHalf) {
    stars.push(
      <Star
        key="half"
        className="h-3.5 w-3.5 fill-amber-400/50 text-amber-400"
      />,
    );
  }
  const empty = 5 - full - (hasHalf ? 1 : 0);
  for (let i = 0; i < empty; i++) {
    stars.push(
      <Star
        key={`empty-${i}`}
        className="h-3.5 w-3.5 text-muted-foreground/30"
      />,
    );
  }
  return stars;
}

/* ------------------------------------------------------------------ */
/*  Sub-components (inlined, server-safe)                              */
/* ------------------------------------------------------------------ */

function SectionHeader({
  title,
  href,
  linkText = "مشاهده همه",
}: {
  title: string;
  href: string;
  linkText?: string;
}) {
  return (
    <div className="mb-8 flex items-center justify-between">
      <h2 className="text-2xl font-bold text-foreground">{title}</h2>
      <Link
        href={href}
        className="group inline-flex items-center gap-1 text-sm font-medium text-primary transition-colors hover:text-primary/80"
      >
        {linkText}
        <ChevronLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
      </Link>
    </div>
  );
}

function ProductCard({
  product,
}: {
  product: {
    id: number;
    title: string;
    price: number;
    originalPrice: number | null;
    rating: number;
    reviews: number;
  };
}) {
  const hasDiscount =
    product.originalPrice !== null && product.originalPrice > product.price;
  const discount = hasDiscount
    ? discountPercent(product.originalPrice!, product.price)
    : 0;

  return (
    <Card className="group relative overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:shadow-lg">
      {/* Image placeholder */}
      <div className="relative aspect-square overflow-hidden bg-muted">
        <div className="flex h-full w-full items-center justify-center">
          <Package className="h-16 w-16 text-muted-foreground/20" />
        </div>

        {hasDiscount && (
          <Badge
            variant="destructive"
            className="absolute start-3 top-3 text-xs"
          >
            {discount}٪ تخفیف
          </Badge>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="mb-2 line-clamp-2 min-h-[2.5rem] text-sm font-semibold leading-relaxed text-foreground">
          {product.title}
        </h3>

        {/* Rating */}
        <div className="mb-3 flex items-center gap-1.5">
          <div className="flex items-center gap-0.5">
            {renderStars(product.rating)}
          </div>
          <span className="text-xs text-muted-foreground">
            ({product.reviews})
          </span>
        </div>

        {/* Price */}
        <div className="mb-3 flex items-center gap-2">
          <span className="price text-base">{formatPrice(product.price)}</span>
          {hasDiscount && (
            <span className="price-discount text-xs">
              {formatPrice(product.originalPrice!)}
            </span>
          )}
        </div>

        {/* Add-to-cart */}
        <Button size="sm" className="w-full gap-2">
          <ShoppingCart className="h-4 w-4" />
          افزودن به سبد
        </Button>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function StoreHomePage() {
  return (
    <div className="container-page">
      {/* ============================================================ */}
      {/*  1 · Hero Banner                                             */}
      {/* ============================================================ */}
      <section className="relative mb-16 overflow-hidden rounded-2xl bg-gradient-to-l from-primary-700 via-primary-600 to-secondary-600 px-6 py-14 text-white sm:px-12 sm:py-20">
        {/* Decorative shapes */}
        <div
          aria-hidden
          className="pointer-events-none absolute -end-20 -top-20 h-72 w-72 rounded-full bg-white/5"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-16 -start-16 h-56 w-56 rotate-45 rounded-3xl bg-white/5"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute end-1/4 top-1/3 h-32 w-32 rounded-full bg-white/[0.03]"
        />

        <div className="relative z-10 max-w-2xl">
          <h1 className="mb-4 text-3xl font-extrabold leading-tight sm:text-4xl lg:text-5xl">
            بهترین‌ها رو آنلاین بخر
          </h1>
          <p className="mb-8 max-w-lg text-base leading-relaxed text-white/85 sm:text-lg">
            هزاران محصول باکیفیت از معتبرترین برندها، ارسال سریع و رایگان به
            سراسر کشور، و ضمانت بازگشت تا ۷ روز.
          </p>

          <div className="flex flex-wrap gap-3">
            <Button
              asChild
              size="lg"
              className="bg-white font-semibold text-primary-700 hover:bg-white/90"
            >
              <Link href="/products">مشاهده محصولات</Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="border-white/40 bg-transparent font-semibold text-white hover:bg-white/10 hover:text-white"
            >
              <Link href="/products?sale=true">تخفیف‌های ویژه</Link>
            </Button>
          </div>
        </div>

        {/* Stats row */}
        <div className="relative z-10 mt-12 grid grid-cols-2 gap-4 border-t border-white/15 pt-8 sm:grid-cols-4">
          {heroStats.map((stat) => (
            <div key={stat.label} className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/10">
                <stat.icon className="h-5 w-5" />
              </div>
              <span className="text-sm font-medium text-white/90">
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  2 · Categories Grid                                         */}
      {/* ============================================================ */}
      <section className="mb-16">
        <SectionHeader title="دسته‌بندی محصولات" href="/products" />

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {categories.map((cat) => (
            <Link
              key={cat.slug}
              href={`/products?category=${cat.slug}`}
              className="group flex flex-col items-center gap-3 rounded-xl border border-border bg-card p-6 text-card-foreground transition-all duration-300 hover:-translate-y-1 hover:shadow-md"
            >
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                <cat.icon className="h-7 w-7" />
              </div>
              <span className="text-sm font-semibold">{cat.name}</span>
              <span className="text-xs text-muted-foreground">
                {cat.count} محصول
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  3 · Special Offers Banner                                   */}
      {/* ============================================================ */}
      <section className="mb-16">
        <Link
          href="/products?sale=true"
          className="group block overflow-hidden rounded-2xl bg-gradient-to-l from-rose-600 to-orange-500 p-6 text-white transition-shadow hover:shadow-xl sm:p-8"
        >
          <div className="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/15">
                <Zap className="h-8 w-8" />
              </div>
              <div>
                <h2 className="mb-1 text-xl font-bold sm:text-2xl">
                  تخفیف‌های شگفت‌انگیز
                </h2>
                <p className="text-sm text-white/80">
                  فرصت محدود — همین الان خرید کنید
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Badge className="border-white/30 bg-white/20 px-4 py-1.5 text-sm font-bold text-white hover:bg-white/30">
                تا ۷۰٪ تخفیف
              </Badge>
              <div className="flex items-center gap-1 text-sm font-medium">
                <span>مشاهده</span>
                <ChevronLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
              </div>
            </div>
          </div>

          {/* Countdown-style boxes */}
          <div className="mt-6 flex gap-3">
            {[
              { value: "۰۳", label: "روز" },
              { value: "۱۲", label: "ساعت" },
              { value: "۴۵", label: "دقیقه" },
              { value: "۲۰", label: "ثانیه" },
            ].map((t) => (
              <div
                key={t.label}
                className="flex flex-col items-center rounded-lg bg-white/10 px-3 py-2 backdrop-blur-sm sm:px-4"
              >
                <span className="text-lg font-extrabold sm:text-2xl">
                  {t.value}
                </span>
                <span className="text-[10px] text-white/70 sm:text-xs">
                  {t.label}
                </span>
              </div>
            ))}
          </div>
        </Link>
      </section>

      {/* ============================================================ */}
      {/*  4 · Featured Products (محصولات پرفروش)                      */}
      {/* ============================================================ */}
      <section className="mb-16">
        <SectionHeader title="محصولات پرفروش" href="/products?sort=popular" />
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {featuredProducts.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  5 · Newest Products (جدیدترین محصولات)                      */}
      {/* ============================================================ */}
      <section className="mb-16">
        <SectionHeader title="جدیدترین محصولات" href="/products?sort=newest" />
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {newestProducts.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  6 · Why Choose Us (چرا ما؟)                                 */}
      {/* ============================================================ */}
      <section className="mb-16">
        <h2 className="mb-8 text-center text-2xl font-bold text-foreground">
          چرا ما را انتخاب کنید؟
        </h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => (
            <Card
              key={feature.title}
              className="flex flex-col items-center p-8 text-center transition-shadow duration-300 hover:shadow-md"
            >
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
                <feature.icon className="h-7 w-7" />
              </div>
              <h3 className="mb-2 font-bold text-foreground">
                {feature.title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {feature.desc}
              </p>
            </Card>
          ))}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  7 · Newsletter                                              */}
      {/* ============================================================ */}
      <section className="mb-12 overflow-hidden rounded-2xl bg-gradient-to-l from-primary-50 to-secondary-50 p-8 dark:from-primary-950/40 dark:to-secondary-950/40 sm:p-12">
        <div className="mx-auto max-w-2xl text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Mail className="h-6 w-6" />
          </div>
          <h2 className="mb-3 text-2xl font-bold text-foreground">
            عضویت در خبرنامه
          </h2>
          <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
            از جدیدترین تخفیف‌ها و محصولات باخبر شوید و قبل از همه از فروش‌های
            ویژه مطلع شوید.
          </p>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-center">
            <Input
              type="email"
              placeholder="ایمیل خود را وارد کنید..."
              className="h-12 sm:w-80"
              dir="ltr"
            />
            <Button size="lg" className="h-12 shrink-0 gap-2 px-8">
              <Mail className="h-4 w-4" />
              عضویت
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
