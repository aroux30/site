import type { Metadata } from "next";
import Link from "next/link";
import {
  Truck,
  Shield,
  RotateCcw,
  Headphones,
  ChevronLeft,
  Star,
  Zap,
  Sparkles,
  Smartphone,
  Laptop,
  Flame,
  Award,
  CreditCard,
  ArrowLeft,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { BentoGrid, BentoCard } from "@/components/ui/bento-grid";
import { Marquee } from "@/components/ui/marquee";
import { HeroInteractive, HeroActions } from "@/components/home/hero-interactive";
import { CampaignCountdown } from "@/components/home/campaign-countdown";
import { ProductQuickCard } from "@/components/home/product-quick-card";
import type { ApiProduct } from "@/lib/api/services";

export const metadata: Metadata = {
  title: "فروشگاه آنلاین ایرانیان | خرید آسان، مطمئن و با ضمانت اصالت",
  description:
    "مرجع تخصصی خرید انواع گوشی‌های هوشمند، لپ‌تاپ، لوازم جانبی و تجهیزات دیجیتال با گارانتی رسمی، ارسال رایگان و پرداخت امن شتاب.",
  openGraph: {
    title: "فروشگاه آنلاین ایرانیان",
    description: "مرجع تخصصی خرید تجهیزات دیجیتال با گارانتی رسمی و ارسال رایگان سراسری.",
    type: "website",
  },
};

// Authoritative featured products for instant server-rendered HTML
const featuredProducts: ApiProduct[] = [
  {
    id: "prod-s24u",
    name: "گوشی موبایل سامسونگ گلکسی S24 Ultra",
    slug: "samsung-galaxy-s24-ultra",
    category_id: "cat-mobile",
    min_price: 68500000,
    max_price: 77900000,
    variant_count: 2,
    is_active: true,
    is_featured: true,
    short_description: "پرچمدار سامسونگ با هوش مصنوعی Galaxy AI و دوربین ۲۰۰ مگاپیکسلی تیتانیوم",
    primary_image_url: "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=800",
  },
  {
    id: "prod-ip16pm",
    name: "گوشی موبایل اپل آیفون 16 پرو مکس",
    slug: "apple-iphone-16-pro-max",
    category_id: "cat-mobile",
    min_price: 95000000,
    max_price: 108000000,
    variant_count: 2,
    is_active: true,
    is_featured: true,
    short_description: "چیپست A18 Pro، نمایشگر ۶.۹ اینچی Super Retina XDR و بدنه تیتانیوم صحرایی",
    primary_image_url: "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=800",
  },
  {
    id: "prod-zb14",
    name: "لپ‌تاپ اولترابوک ایسوس ذن‌بوک 14 OLED",
    slug: "asus-zenbook-14-oled",
    category_id: "cat-laptops",
    min_price: 62000000,
    max_price: 62000000,
    variant_count: 1,
    is_active: true,
    is_featured: true,
    short_description: "پردازنده Core Ultra 7 اینتل با ۱۶ گیگابایت رم، ۱ ترابایت SSD و نمایشگر ۱۲۰ هرتز OLED",
    primary_image_url: "https://images.unsplash.com/photo-1541807084-5c52b6b3adef?w=800",
  },
  {
    id: "prod-xm5",
    name: "هدفون بی‌سیم نویز کنسلینگ سونی WH-1000XM5",
    slug: "sony-wh-1000xm5-wireless-headphones",
    category_id: "cat-audio",
    min_price: 16800000,
    max_price: 16800000,
    variant_count: 2,
    is_active: true,
    is_featured: true,
    short_description: "قوی‌ترین سیستم حذف نویز جهان با دو پردازنده اختصاصی و صدای استودیویی Hi-Res",
    primary_image_url: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800",
  },
  {
    id: "prod-wuo2",
    name: "ساعت هوشمند اپل واچ اولترا ۲",
    slug: "apple-watch-ultra-2",
    category_id: "cat-smartwatch",
    min_price: 48500000,
    max_price: 48500000,
    variant_count: 1,
    is_active: true,
    is_featured: true,
    short_description: "بدنه تیتانیوم ۴۹ میلی‌متری مقاوم در برابر آب تا ۱۰۰ متر با روشنایی ۳۰۰۰ نیت",
    primary_image_url: "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=800",
  },
  {
    id: "prod-pb20",
    name: "پاوربانک ۲۰۰۰۰ میلی‌آمپر ۵۰ وات شیائومی",
    slug: "xiaomi-50w-powerbank-20000",
    category_id: "cat-audio",
    min_price: 2450000,
    max_price: 2450000,
    variant_count: 1,
    is_active: true,
    is_featured: true,
    short_description: "فست شارژ ۵۰ واتی با قابلیت شارژ لپ‌تاپ و ۳ خروجی همزمان Type-C",
    primary_image_url: "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=800",
  },
];

export default function HomePage() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* ── 1. Hero Section (SSR Shell + Client 3D Island) ── */}
      <section className="relative overflow-hidden pt-6 pb-12 lg:pt-10 lg:pb-16 bg-gradient-to-b from-emerald-500/5 via-background to-background">
        <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            {/* Left Content (Text + CTAs) */}
            <div className="lg:col-span-7 space-y-6 text-center lg:text-right">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
                <Sparkles className="w-3.5 h-3.5" />
                <span>پلتفرم مدرن ایکامرس ایران • تجربه خرید هوشمند</span>
              </div>

              <h1 className="text-3xl sm:text-4xl lg:text-6xl font-black text-foreground tracking-tight leading-[1.2]">
                تجربه خریدی <span className="text-emerald-600 dark:text-emerald-400">سریع، مطمئن</span> و فراتر از انتظار
              </h1>

              <p className="text-muted-foreground text-sm sm:text-base lg:text-lg max-w-2xl mx-auto lg:mx-0 leading-relaxed">
                دسترسی مستقیم به برترین پرچمداران دیجیتال، گجت‌های هوشمند و لوازم جانبی اورجینال با ارسال اکسپرس، ضمانت اصالت ۱۰۰٪ و درگاه‌های امن بانکی و کریپتو.
              </p>

              {/* Client Action Buttons Island */}
              <HeroActions />

              {/* Trust Counters */}
              <div className="grid grid-cols-3 gap-4 pt-6 border-t border-border/60 max-w-lg mx-auto lg:mx-0">
                <div>
                  <div className="text-2xl lg:text-3xl font-black text-foreground">۱۰,۰۰۰+</div>
                  <div className="text-xs text-muted-foreground mt-0.5">کالای اصل و معتبر</div>
                </div>
                <div>
                  <div className="text-2xl lg:text-3xl font-black text-emerald-600 dark:text-emerald-400">۵۰,۰۰۰+</div>
                  <div className="text-xs text-muted-foreground mt-0.5">مشتری وفادار</div>
                </div>
                <div>
                  <div className="text-2xl lg:text-3xl font-black text-foreground">۹۹.۸٪</div>
                  <div className="text-xs text-muted-foreground mt-0.5">رضایت مشتریان</div>
                </div>
              </div>
            </div>

            {/* Right Content (Client 3D Island) */}
            <div className="lg:col-span-5 flex justify-center">
              <HeroInteractive />
            </div>
          </div>
        </div>
      </section>

      {/* ── 2. Value Propositions Marquee ── */}
      <div className="py-4 border-y border-border/60 bg-muted/20">
        <Marquee pauseOnHover className="[--duration:25s]">
          <div className="flex items-center gap-12 text-sm font-semibold text-muted-foreground px-4">
            <span className="flex items-center gap-2">
              <Truck className="w-4 h-4 text-emerald-500" />
              ارسال فوق‌سریع به سراسر ایران
            </span>
            <span className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-500" />
              ضمانت اصالت ۱۰۰٪ کالاها
            </span>
            <span className="flex items-center gap-2">
              <RotateCcw className="w-4 h-4 text-emerald-500" />
              ۷ روز فرصت تست و بازگشت
            </span>
            <span className="flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-emerald-500" />
              پرداخت امن از درگاه‌های شتاب و تتر
            </span>
            <span className="flex items-center gap-2">
              <Headphones className="w-4 h-4 text-emerald-500" />
              مشاوره و پشتیبانی ۲۴/۷
            </span>
          </div>
        </Marquee>
      </div>

      {/* ── 3. Bento Grid Featured Categories ── */}
      <section className="py-14 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-10 gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 dark:text-emerald-400 mb-2">
                <Sparkles className="w-3.5 h-3.5" />
                دسته‌بندی‌های محبوب
              </div>
              <h2 className="text-2xl sm:text-3xl font-black text-foreground">
                کاوش بر اساس دسته‌بندی
              </h2>
            </div>
            <Link
              href="/products"
              className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 hover:underline inline-flex items-center gap-1"
            >
              مشاهده تمامی دسته‌ها
              <ChevronLeft className="w-4 h-4" />
            </Link>
          </div>

          <BentoGrid className="grid-cols-1 md:grid-cols-3 gap-6">
            <BentoCard
              name="موبایل و تبلت"
              className="md:col-span-2 bg-gradient-to-br from-emerald-900/20 via-background to-card border-border/80"
              background={<div className="absolute inset-0 bg-emerald-500/5 backdrop-blur-[2px]" />}
              Icon={Smartphone}
              description="جدیدترین پرچمداران اپل، سامسونگ و شیائومی همراه با رجیستری رسمی و گارانتی معتبر شرکتی."
              href="/products?category=mobile"
              cta="مشاهده گوشی‌ها"
            />
            <BentoCard
              name="لپ‌تاپ و کامپیوتر"
              className="md:col-span-1 bg-card border-border/80"
              background={<div className="absolute inset-0 bg-indigo-500/5" />}
              Icon={Laptop}
              description="اولترابوک‌های مهندسی، لپ‌تاپ‌های گیمینگ و مک‌بوک‌های اپل با برترین کانفیگ روز."
              href="/products?category=laptops"
              cta="مشاهده لپ‌تاپ‌ها"
            />
            <BentoCard
              name="ساعت‌های هوشمند"
              className="md:col-span-1 bg-card border-border/80"
              background={<div className="absolute inset-0 bg-amber-500/5" />}
              Icon={Award}
              description="اپل واچ، گلکسی واچ و دستبندهای ورزشی پایش سلامت با امکانات مکالمه و ضدآب."
              href="/products?category=smartwatch"
              cta="مشاهده ساعت‌ها"
            />
            <BentoCard
              name="لوازم صوتی و هدفون"
              className="md:col-span-2 bg-gradient-to-bl from-teal-900/20 via-background to-card border-border/80"
              background={<div className="absolute inset-0 bg-teal-500/5" />}
              Icon={Headphones}
              description="هدفون‌های مجهز به نویزکنسلینگ فعال، هندزفری‌های بلوتوثی و اسپیکرهای ضدآب قابل حمل."
              href="/products?category=audio"
              cta="مشاهده سیستم‌های صوتی"
            />
          </BentoGrid>
        </div>
      </section>

      {/* ── 4. Flash Sale / Campaign Banner with Client Countdown ── */}
      <section className="py-6">
        <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-l from-emerald-900 via-slate-900 to-slate-950 p-8 sm:p-12 border border-emerald-500/30 text-white shadow-2xl">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
              <div className="lg:col-span-8 space-y-4">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-bold border border-emerald-500/30">
                  <Flame className="w-3.5 h-3.5 text-amber-400" />
                  جشنواره تخفیف طلایی آغاز شد
                </div>
                <h3 className="text-2xl sm:text-4xl font-black leading-tight">
                  تا ۱۵٪ تخفیف + ارسال کاملاً رایگان سفارشات
                </h3>
                <p className="text-slate-200 text-sm sm:text-base max-w-xl leading-relaxed">
                  با استفاده از کوپن تخفیف{" "}
                  <span className="font-mono font-black text-amber-300 bg-amber-400/15 border border-amber-400/30 px-2.5 py-0.5 rounded-lg tracking-wider">
                    WELCOME
                  </span>{" "}
                  در مرحله چک‌اوت از تخفیف ویژه بهره‌مند شوید.
                </p>
                {/* Client Countdown Island */}
                <div className="pt-2">
                  <span className="text-xs text-slate-300 block mb-2 font-semibold">
                    زمان باقی‌مانده تا پایان کمپین:
                  </span>
                  <CampaignCountdown />
                </div>
              </div>

              <div className="lg:col-span-4 flex justify-center lg:justify-end">
                <Link href="/products?sale=true">
                  <Button size="lg" className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-black px-8 h-12 rounded-2xl shadow-xl">
                    ورود به تخفیف‌های ویژه
                    <ArrowLeft className="w-4 h-4 mr-2" />
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 5. Flagship Products Grid (SSR Shell + Interactive Cards) ── */}
      <section className="py-14 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-10 gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 dark:text-emerald-400 mb-2">
                <Zap className="w-3.5 h-3.5" />
                کالاهای منتخب پرچمدار
              </div>
              <h2 className="text-2xl sm:text-3xl font-black text-foreground">
                پرفروش‌ترین‌های این هفته
              </h2>
            </div>
            <Link
              href="/products"
              className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 hover:underline inline-flex items-center gap-1"
            >
              مشاهده تمام کالاها
              <ChevronLeft className="w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
            {featuredProducts.map((product) => (
              <ProductQuickCard
                key={product.id}
                product={product}
                featured={product.is_featured}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ── 6. Verified Customer Social Proof ── */}
      <section className="py-14 bg-muted/20 border-t border-border/60">
        <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-2xl sm:text-3xl font-black text-foreground mb-3">
              نظرات و تجربیات خریداران واقعی
            </h2>
            <p className="text-sm text-muted-foreground">
              بیش از ۵۰,۰۰۰ خریدار در سراسر کشور اصالت کالاها و سرعت ارسال ما را تایید کرده‌اند.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="p-6 rounded-3xl border-border bg-card shadow-sm space-y-4">
              <div className="flex items-center gap-1 text-amber-500">
                {[...Array(5)].map((_, i) => (
                  <Star key={i} className="w-4 h-4 fill-current" />
                ))}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                «گوشی سامسونگ اس ۲۴ اولترا با بسته‌بندی عالی و گارانتی رسمی شرکت به دستم رسید. سرعت ارسال و پشتیبانی فوق‌العاده محترمانه بود.»
              </p>
              <div className="pt-2 border-t border-border/50 text-xs text-foreground font-bold flex items-center justify-between">
                <span>محمدرضا کاظمی</span>
                <span className="text-emerald-600 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  خرید تاییدشده
                </span>
              </div>
            </Card>

            <Card className="p-6 rounded-3xl border-border bg-card shadow-sm space-y-4">
              <div className="flex items-center gap-1 text-amber-500">
                {[...Array(5)].map((_, i) => (
                  <Star key={i} className="w-4 h-4 fill-current" />
                ))}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                «لپ‌تاپ ایسوس ذن‌بوک دقیقاً همون چیزی بود که برای کارهای طراحی لازم داشتم. امکان پرداخت با تتر خیلی خرید رو برام راحت کرد.»
              </p>
              <div className="pt-2 border-t border-border/50 text-xs text-foreground font-bold flex items-center justify-between">
                <span>سارا نیکنام</span>
                <span className="text-emerald-600 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  خرید تاییدشده
                </span>
              </div>
            </Card>

            <Card className="p-6 rounded-3xl border-border bg-card shadow-sm space-y-4">
              <div className="flex items-center gap-1 text-amber-500">
                {[...Array(5)].map((_, i) => (
                  <Star key={i} className="w-4 h-4 fill-current" />
                ))}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                «نویزکنسلینگ سونی XM5 شگفت‌انگیزه! کد رهگیری پستی بلافاصله بعد از ثبت سفارش برام پیامک شد و دو روزه تحویل گرفتم.»
              </p>
              <div className="pt-2 border-t border-border/50 text-xs text-foreground font-bold flex items-center justify-between">
                <span>امیرحسین رضوی</span>
                <span className="text-emerald-600 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  خرید تاییدشده
                </span>
              </div>
            </Card>
          </div>
        </div>
      </section>
    </div>
  );
}
