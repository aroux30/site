"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
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
  Flame,
  Award,
  CreditCard,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { SpotlightCard } from "@/components/ui/spotlight-card";
import { BentoGrid, BentoCard } from "@/components/ui/bento-grid";
import { Marquee } from "@/components/ui/marquee";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { NumberTicker } from "@/components/ui/number-ticker";
import { TiltCard3D } from "@/components/3d/tilt-card-3d";
import { ParticleConstellation } from "@/components/3d/particle-constellation";
import { GsapReveal } from "@/components/3d/gsap-reveal";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import { useCart } from "@/hooks/use-cart";
import {
  fetchCategories,
  fetchProducts,
  type ApiCategory,
  type ApiProduct,
} from "@/lib/api/services";

// Dynamically load 3D scene on client side to avoid WebGL SSR issues
const Hero3DScene = dynamic(
  () => import("@/components/3d/hero-scene").then((mod) => mod.Hero3DScene),
  {
    ssr: false,
    loading: () => (
      <div className="h-[420px] w-full flex items-center justify-center">
        <div className="h-44 w-44 rounded-full bg-emerald-500/20 blur-2xl animate-pulse" />
      </div>
    ),
  }
);

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
    short_description: "پرچمدار بی‌رقیب با دوربین ۲۰۰ مگاپیکسلی، هوش مصنوعی Galaxy AI و قلم S-Pen",
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
    short_description: "لپ‌تاپ گیمینگ قدرتمند با نمایشگر OLED ۲۴۰Hz و پردازنده Core Ultra 9",
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
    short_description: "بهترین نویزکنسلینگ دنیا با صدای شگفت‌انگیز Hi-Res و ارگونومی سبک",
  },
  {
    id: "f4",
    name: "ساعت هوشمند اپل واچ سری ۹ (۴۵ میلی‌متر)",
    slug: "apple-watch-series-9",
    category_id: "c4",
    min_price: 24000000,
    max_price: 27500000,
    variant_count: 3,
    is_active: true,
    is_featured: true,
    short_description: "پردازنده فوق‌سریع S9، ژست حرکتی Double Tap و روشنایی ۲۰۰۰ نیتی نمایشگر",
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
];

const brandPartners = [
  "اپل (Apple)",
  "سامسونگ (Samsung)",
  "سونی (Sony)",
  "ایسوس (ASUS)",
  "شیائومی (Xiaomi)",
  "دلونگی (DeLonghi)",
  "جی‌بی‌ال (JBL)",
  "آنکر (Anker)",
  "ال‌جی (LG)",
];

const valuePillars = [
  { icon: Truck, text: "ارسال فوق‌سریع به سراسر ایران" },
  { icon: Shield, text: "ضمانت اصالت ۱۰۰٪ کالاها" },
  { icon: RotateCcw, text: "۷ روز فرصت تست و بازگشت" },
  { icon: CreditCard, text: "پرداخت امن از درگاه‌های شتاب" },
  { icon: Headphones, text: "مشاوره و پشتیبانی ۲۴/۷" },
  { icon: Award, text: "نمایندگی رسمی برترین برندها" },
];

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
        <h2 className="text-xl sm:text-2xl font-black text-foreground flex items-center gap-2.5">
          <span className="h-6 w-2 rounded-full bg-primary inline-block shadow-sm shadow-primary/40" />
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

function FeaturedProductSpotlight({ product }: { product: ApiProduct }) {
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
    <TiltCard3D maxTilt={9} className="group flex flex-col justify-between p-5 transition-all duration-300 hover:border-primary/40">
      <Link href={`/products/${product.slug}`} className="flex flex-col h-full">
        {/* Image Area */}
        <div className="relative aspect-square overflow-hidden rounded-xl bg-muted/40 p-4">
          {product.primary_image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={product.primary_image_url}
              alt={product.name}
              className="h-full w-full object-contain transition-transform duration-500 group-hover:scale-105"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-muted-foreground/30">
              <Package className="h-20 w-20" />
            </div>
          )}

          {discount && discount > 0 && (
            <Badge
              variant="destructive"
              className="absolute top-3 right-3 rounded-full px-2.5 py-0.5 text-xs font-black shadow-sm"
            >
              {toPersianDigits(discount)}٪ تخفیف
            </Badge>
          )}

          {product.is_featured && (
            <Badge className="absolute bottom-3 right-3 bg-amber-500 hover:bg-amber-600 text-white rounded-full text-[10px] px-2.5 py-0.5 gap-1 font-bold">
              <Sparkles className="h-3 w-3" />
              منتخب
            </Badge>
          )}
        </div>

        {/* Content */}
        <div className="flex flex-1 flex-col pt-4">
          <h3 className="mb-2 line-clamp-2 min-h-[2.8rem] text-sm font-bold leading-relaxed text-foreground group-hover:text-primary transition-colors">
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
            <span className="font-bold text-foreground">۴.۸</span>
            <span>(۴۸ نظر ثبت‌شده)</span>
          </div>

          {/* Price */}
          <div className="mt-auto flex flex-col gap-1 pt-2 border-t border-border/60">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-base font-black text-foreground">
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

      {/* Action Button */}
      <div className="pt-3">
        <Button
          size="sm"
          onClick={handleAddToCart}
          className="w-full gap-2 rounded-xl font-bold transition-all shadow-sm"
          variant={added ? "secondary" : "default"}
        >
          {added ? (
            <>
              <Check className="h-4 w-4 text-emerald-600" />
              <span className="text-xs text-emerald-600">به سبد افزوده شد</span>
            </>
          ) : (
            <>
              <ShoppingCart className="h-4 w-4" />
              <span className="text-xs">افزودن سریع به سبد</span>
            </>
          )}
        </Button>
      </div>
    </TiltCard3D>
  );
}

function ProductSkeleton() {
  return (
    <Card className="overflow-hidden rounded-2xl p-4">
      <Skeleton className="aspect-square w-full rounded-xl" />
      <div className="pt-4 space-y-3">
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

  // Countdown timer for special promo
  const [timeLeft, setTimeLeft] = useState({ hours: 14, minutes: 32, seconds: 45 });

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev.seconds > 0) return { ...prev, seconds: prev.seconds - 1 };
        if (prev.minutes > 0) return { ...prev, minutes: 59, seconds: 59 };
        if (prev.hours > 0) return { hours: prev.hours - 1, minutes: 59, seconds: 59 };
        return { hours: 24, minutes: 0, seconds: 0 };
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

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
    <div className="container mx-auto px-4 py-6 sm:py-10 space-y-16 sm:space-y-24">
      {/* ============================================================ */}
      {/*  1 · Hero Banner with Interactive 3D Holographic Gadget      */}
      {/* ============================================================ */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-l from-emerald-950 via-primary-900 to-teal-950 px-6 py-12 text-white shadow-2xl sm:px-10 sm:py-16 lg:py-16">
        {/* Interactive 3D Particle Constellation */}
        <ParticleConstellation
          particleCount={45}
          connectionDistance={120}
          particleColor="rgba(52, 211, 153, 0.5)"
          lineColor="rgba(52, 211, 153, 0.15)"
        />

        {/* Animated background highlights */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 -left-24 h-96 w-96 rounded-full bg-emerald-400/20 blur-3xl animate-pulse"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-24 -right-24 h-96 w-96 rounded-full bg-teal-400/25 blur-3xl"
        />

        <div className="relative z-10 grid grid-cols-1 items-center gap-8 lg:grid-cols-12">
          {/* Left / Right Column in RTL: Content */}
          <div className="lg:col-span-7">
            <GsapReveal delay={0.1} duration={0.7} yOffset={20}>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3.5 py-1 text-xs font-semibold text-emerald-200 backdrop-blur-md">
                <Sparkles className="h-3.5 w-3.5 text-amber-300" />
                <span>پلتفرم مدرن ایکامرس ایران • تجربه سه‌بعدی ۳۶۰°</span>
              </div>

              <h1 className="mb-5 text-3xl font-black leading-tight sm:text-4xl lg:text-5xl">
                تجربه خریدی هوشمند، سریع و فراتر از انتظار
              </h1>

              <p className="mb-8 max-w-xl text-sm leading-relaxed text-white/85 sm:text-base lg:text-lg">
                دسترسی به بیش از ۱۰ هزار قلم کالای اصیل با ارسال اکسپرس، گارانتی معتبر و پرداخت امن شتاب. هر آنچه برای یک زندگی مدرن دیجیتال نیاز دارید.
              </p>

              <div className="flex flex-wrap items-center gap-4">
                <Link href="/products">
                  <ShimmerButton
                    background="hsl(0 0% 100%)"
                    shimmerColor="#10b981"
                    className="font-black text-primary px-8 py-3.5 shadow-xl text-sm sm:text-base"
                  >
                    <span>مشاهده فروشگاه و محصولات</span>
                    <ChevronLeft className="h-4 w-4" />
                  </ShimmerButton>
                </Link>

                <Link href="/products?sort_by=price&sort_order=desc">
                  <Button
                    size="lg"
                    variant="outline"
                    className="h-12 rounded-full border-2 border-white/30 bg-white/10 px-6 font-bold text-white backdrop-blur-md hover:bg-white/20 hover:text-white text-sm sm:text-base"
                  >
                    <Flame className="ml-2 h-4 w-4 text-amber-300" />
                    تخفیف‌های داغ روز
                  </Button>
                </Link>
              </div>
            </GsapReveal>

            {/* Animated Metrics Row (NumberTicker) */}
            <div className="mt-10 grid grid-cols-3 gap-4 border-t border-white/15 pt-8">
              <div>
                <div className="text-2xl sm:text-3xl font-black text-white">
                  <NumberTicker value={10000} />+
                </div>
                <p className="text-xs text-emerald-200/80 mt-0.5">کالای اصل و اورجینال</p>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-white">
                  <NumberTicker value={50000} />+
                </div>
                <p className="text-xs text-emerald-200/80 mt-0.5">مشتری وفادار و فعال</p>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-white">
                  <NumberTicker value={99} />٪
                </div>
                <p className="text-xs text-emerald-200/80 mt-0.5">رضایت مشتریان</p>
              </div>
            </div>
          </div>

          {/* 3D Holographic Device Canvas */}
          <div className="lg:col-span-5 flex items-center justify-center">
            <Hero3DScene />
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  2 · Infinite Marquee: Brand Partners & Promises             */}
      {/* ============================================================ */}
      <section className="space-y-4">
        <div className="rounded-2xl border border-border/80 bg-card/60 py-4 shadow-sm backdrop-blur-sm">
          <Marquee speed={35} pauseOnHover>
            {valuePillars.map((pillar, idx) => {
              const Icon = pillar.icon;
              return (
                <div
                  key={idx}
                  className="flex items-center gap-2.5 rounded-full border border-border bg-background px-4 py-2 text-xs font-bold text-foreground shadow-2xs"
                >
                  <Icon className="h-4 w-4 text-primary" />
                  <span>{pillar.text}</span>
                </div>
              );
            })}
          </Marquee>

          <div className="my-2 border-t border-border/40" />

          <Marquee speed={45} reverse pauseOnHover>
            {brandPartners.map((brand, idx) => (
              <span
                key={idx}
                className="px-5 text-sm font-semibold text-muted-foreground/80 transition-colors hover:text-primary cursor-default"
              >
                ★ {brand}
              </span>
            ))}
          </Marquee>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  3 · Bento Grid Category Showcase                            */}
      {/* ============================================================ */}
      <section>
        <SectionHeader
          title="دسته‌بندی‌های برگزیده (Bento Grid)"
          subtitle="سریع‌ترین راه برای رسیدن به کالای مورد نظر شما"
          href="/products"
          linkText="مشاهده تمام دسته‌ها"
        />

        <BentoGrid>
          <BentoCard
            name="موبایل و گجت‌های هوشمند"
            description="جدیدترین پرچمداران اپل، سامسونگ، شیائومی و لوازم جانبی اورجینال با تضمین بهترین قیمت"
            href="/products?category_slug=phones"
            Icon={Smartphone}
            badge="پرفروش‌ترین"
            className="md:col-span-2"
            background={
              <div className="h-full w-full bg-gradient-to-br from-emerald-500/10 via-teal-500/5 to-transparent" />
            }
          />
          <BentoCard
            name="لپ‌تاپ و اولترابوک"
            description="مک‌بوک، اولترابوک‌های مهندسی و لپ‌تاپ‌های گیمینگ ایسوس و لنوو"
            href="/products?category_slug=laptops"
            Icon={Laptop}
            className="md:col-span-1"
            background={
              <div className="h-full w-full bg-gradient-to-bl from-blue-500/10 to-transparent" />
            }
          />
          <BentoCard
            name="ساعت و دستبند هوشمند"
            description="اپل واچ، گلکسی واچ و پایشگرهای حرفه‌ای سلامت و ورزش"
            href="/products?category_slug=smartwatch"
            Icon={Sparkles}
            className="md:col-span-1"
            background={
              <div className="h-full w-full bg-gradient-to-tr from-amber-500/10 to-transparent" />
            }
          />
          <BentoCard
            name="لوازم صوتی و سینمای خانگی"
            description="هدفون‌های پرچم‌دار سونی و اپل، اسپیکرهای ضدآب جی‌بی‌ال و ساندبارهای حرفه‌ای"
            href="/products?category_slug=audio-video"
            Icon={Headphones}
            badge="پیشنهاد ویژه"
            className="md:col-span-2"
            background={
              <div className="h-full w-full bg-gradient-to-br from-purple-500/10 via-pink-500/5 to-transparent" />
            }
          />
        </BentoGrid>
      </section>

      {/* ============================================================ */}
      {/*  4 · Featured Products (3D Interactive Tilt & Spotlight)     */}
      {/* ============================================================ */}
      <section>
        <SectionHeader
          title="محصولات منتخب و پرچمدار (3D Interactive Edition)"
          subtitle="تکنولوژی‌های برتر با بازخورد فیزیکی سه‌بعدی و انعکاس نوری"
          href="/products?sort_by=created_at&sort_order=desc"
          linkText="مشاهده تمام کالاها"
        />

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <ProductSkeleton key={i} />
              ))
            : featuredProducts.map((p) => (
                <FeaturedProductSpotlight key={p.id} product={p} />
              ))}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  5 · Live Countdown Special Offer Banner                     */}
      {/* ============================================================ */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-emerald-600 via-teal-600 to-primary-700 p-8 text-white shadow-2xl">
        <div className="relative z-10 flex flex-col items-center justify-between gap-6 lg:flex-row text-center lg:text-start">
          <div className="max-w-xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/20 px-3.5 py-1 text-xs font-black backdrop-blur-md">
              <Zap className="h-4 w-4 text-amber-300" />
              <span>پیشنهاد شگفت‌انگیز ۲۴ ساعته</span>
            </div>
            <h3 className="mt-3 text-2xl sm:text-3xl font-black leading-tight">
              ارسال کاملاً رایگان + تا ۱۵٪ تخفیف ویژه خرید اول
            </h3>
            <p className="mt-2 text-sm text-white/90 leading-relaxed">
              با وارد کردن کد تخفیف <span className="font-mono font-black text-amber-300">WELCOME10</span> در مرحله سبد خرید از تخفیف ویژه بهره‌مند شوید.
            </p>
          </div>

          {/* Countdown Boxes */}
          <div className="flex items-center gap-3">
            <div className="flex flex-col items-center rounded-2xl bg-black/30 backdrop-blur-md px-4 py-3 min-w-[70px]">
              <span className="text-2xl font-black text-amber-300 tabular-nums">
                {toPersianDigits(timeLeft.hours)}
              </span>
              <span className="text-[11px] text-white/70 font-medium">ساعت</span>
            </div>
            <span className="text-xl font-bold">:</span>
            <div className="flex flex-col items-center rounded-2xl bg-black/30 backdrop-blur-md px-4 py-3 min-w-[70px]">
              <span className="text-2xl font-black text-amber-300 tabular-nums">
                {toPersianDigits(timeLeft.minutes)}
              </span>
              <span className="text-[11px] text-white/70 font-medium">دقیقه</span>
            </div>
            <span className="text-xl font-bold">:</span>
            <div className="flex flex-col items-center rounded-2xl bg-black/30 backdrop-blur-md px-4 py-3 min-w-[70px]">
              <span className="text-2xl font-black text-amber-300 tabular-nums">
                {toPersianDigits(timeLeft.seconds)}
              </span>
              <span className="text-[11px] text-white/70 font-medium">ثانیه</span>
            </div>
          </div>

          <Link href="/products?sale=true">
            <Button
              size="lg"
              className="h-12 rounded-2xl bg-white font-black text-emerald-800 hover:bg-white/90 shadow-lg whitespace-nowrap px-8"
            >
              مشاهده تخفیف‌ها
            </Button>
          </Link>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  6 · Best Sellers Section                                    */}
      {/* ============================================================ */}
      <section>
        <SectionHeader
          title="پرفروش‌ترین‌های این هفته"
          subtitle="کالاهایی که بیشترین رضایت و سفارش را داشته‌اند"
          href="/products?sort_by=price&sort_order=desc"
          linkText="مشاهده لیست کامل"
        />

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <ProductSkeleton key={i} />
              ))
            : bestSellers.map((p) => (
                <FeaturedProductSpotlight key={p.id} product={p} />
              ))}
        </div>
      </section>
    </div>
  );
}
