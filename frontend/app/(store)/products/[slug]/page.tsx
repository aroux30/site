"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Star,
  Heart,
  ShoppingCart,
  Truck,
  Shield,
  RotateCcw,
  Share2,
  ChevronLeft,
  Minus,
  Plus,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import { cn, formatPrice, toPersianDigits } from "@/lib/utils";
import { useCartStore } from "@/stores/cart-store";

/* -------------------------------------------------------------------------- */
/*                               Sample Data                                  */
/* -------------------------------------------------------------------------- */

const sampleProduct = {
  id: "s24-ultra",
  title: "گوشی موبایل سامسونگ Galaxy S24 Ultra",
  slug: "samsung-galaxy-s24-ultra",
  price: 65000000,
  originalPrice: 72000000,
  category: "الکترونیک",
  subcategory: "گوشی موبایل",
  rating: 4.7,
  reviewCount: 342,
  inStock: true,
  images: [0, 1, 2, 3], // placeholder indices
  colors: [
    { name: "مشکی تیتانیوم", value: "#2d2d2d" },
    { name: "بنفش تیتانیوم", value: "#6b5b7b" },
    { name: "زرد تیتانیوم", value: "#c4b078" },
    { name: "خاکستری تیتانیوم", value: "#9a9a9a" },
  ],
  features: [
    "صفحه نمایش ۶.۸ اینچی Dynamic AMOLED 2X",
    "پردازنده Snapdragon 8 Gen 3",
    "دوربین اصلی ۲۰۰ مگاپیکسلی",
    "باتری ۵۰۰۰ میلی‌آمپر ساعت با شارژ سریع",
    "قلم S Pen داخلی با قابلیت‌های هوش مصنوعی",
  ],
  description: `گوشی موبایل سامسونگ Galaxy S24 Ultra با طراحی تیتانیومی مقاوم و زیبا، یکی از پیشرفته‌ترین گوشی‌های هوشمند بازار است. این گوشی مجهز به صفحه نمایش ۶.۸ اینچی Dynamic AMOLED 2X با رزولوشن QHD+ و نرخ نوسازی ۱۲۰ هرتز است که تجربه بصری فوق‌العاده‌ای را ارائه می‌دهد.

پردازنده قدرتمند Snapdragon 8 Gen 3 به همراه ۱۲ گیگابایت حافظه رم، عملکرد بی‌نظیری را در اجرای بازی‌ها، اپلیکیشن‌های سنگین و چندوظیفگی فراهم می‌کند. سیستم دوربین چهارگانه با سنسور اصلی ۲۰۰ مگاپیکسلی، تصاویر خیره‌کننده‌ای با جزئیات باورنکردنی ثبت می‌کند.

قابلیت‌های هوش مصنوعی Galaxy AI شامل ترجمه همزمان مکالمات تلفنی، ویرایش حرفه‌ای تصاویر، خلاصه‌سازی متون و جستجوی هوشمند است. قلم S Pen داخلی نیز امکان یادداشت‌برداری سریع و طراحی را فراهم می‌سازد.

باتری ۵۰۰۰ میلی‌آمپر ساعتی با پشتیبانی از شارژ سریع ۴۵ واتی، استفاده طولانی‌مدت در طول روز را تضمین می‌کند. این دستگاه همچنین دارای استاندارد مقاومت IP68 در برابر آب و گرد و غبار است.`,
  specifications: {
    برند: "سامسونگ",
    مدل: "Galaxy S24 Ultra",
    "حافظه داخلی": "۲۵۶ گیگابایت",
    رم: "۱۲ گیگابایت",
    "اندازه صفحه نمایش": "۶.۸ اینچ",
    "دوربین اصلی": "۲۰۰ مگاپیکسل",
    باتری: "۵۰۰۰ میلی‌آمپر ساعت",
    "سیستم عامل": "Android 14",
    رنگ: "مشکی تیتانیوم",
    گارانتی: "۱۸ ماهه",
  } as Record<string, string>,
};

const sampleReviews = [
  {
    id: "1",
    author: "علی محمدی",
    date: "۱۴۰۳/۰۶/۱۵",
    rating: 5,
    text: "واقعاً عالیه! کیفیت دوربین فوق‌العاده‌ست و عملکرد پردازنده بسیار روان و سریع. قلم S Pen هم که دیگه حرف نداره. بهترین گوشی‌ای که تا حالا داشتم.",
    pros: ["کیفیت دوربین عالی", "عملکرد سریع", "طراحی زیبا"],
    cons: ["قیمت بالا"],
  },
  {
    id: "2",
    author: "مریم حسینی",
    date: "۱۴۰۳/۰۵/۲۸",
    rating: 4,
    text: "گوشی بسیار خوبیه ولی قیمتش واقعاً بالاست. صفحه نمایش خیلی باکیفیته و باتری هم خوب دوام میاره. قابلیت‌های هوش مصنوعی هم جالب هستن.",
    pros: ["صفحه نمایش عالی", "عمر باتری خوب", "قابلیت‌های AI"],
    cons: ["قیمت بالا", "سنگین"],
  },
  {
    id: "3",
    author: "رضا کریمی",
    date: "۱۴۰۳/۰۵/۱۰",
    rating: 5,
    text: "از هر نظر یک گوشی کامل و بی‌نقص. ارتقای بزرگی نسبت به S23 Ultra بود. عملکرد Galaxy AI هم فراتر از انتظارم بود. خیلی راضی‌ام از خریدم.",
    pros: ["ارتقای محسوس نسبت به نسل قبل", "Galaxy AI", "ساخت تیتانیومی"],
    cons: ["شارژر داخل جعبه نیست"],
  },
];

const relatedProducts = [
  {
    id: "r1",
    title: "گوشی موبایل سامسونگ Galaxy S24+",
    slug: "samsung-galaxy-s24-plus",
    price: 52000000,
    originalPrice: 55000000,
    rating: 4.5,
    reviewCount: 189,
  },
  {
    id: "r2",
    title: "گوشی موبایل آیفون ۱۵ پرو مکس",
    slug: "iphone-15-pro-max",
    price: 78000000,
    originalPrice: null,
    rating: 4.8,
    reviewCount: 523,
  },
  {
    id: "r3",
    title: "گوشی موبایل شیائومی ۱۴ اولترا",
    slug: "xiaomi-14-ultra",
    price: 38000000,
    originalPrice: 42000000,
    rating: 4.3,
    reviewCount: 97,
  },
  {
    id: "r4",
    title: "گوشی موبایل گوگل پیکسل ۸ پرو",
    slug: "google-pixel-8-pro",
    price: 45000000,
    originalPrice: null,
    rating: 4.6,
    reviewCount: 156,
  },
];

/* -------------------------------------------------------------------------- */
/*                              Helper Components                             */
/* -------------------------------------------------------------------------- */

function RatingStars({
  rating,
  size = "sm",
}: {
  rating: number;
  size?: "sm" | "md";
}) {
  const sizeClass = size === "md" ? "h-5 w-5" : "h-4 w-4";
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <Star
          key={i}
          className={cn(
            sizeClass,
            i < Math.floor(rating)
              ? "fill-yellow-400 text-yellow-400"
              : i < rating
                ? "fill-yellow-400/50 text-yellow-400"
                : "text-muted-foreground/30",
          )}
        />
      ))}
    </div>
  );
}

function RelatedProductCard({
  product,
}: {
  product: (typeof relatedProducts)[number];
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
              {toPersianDigits(discount)}% تخفیف
            </Badge>
          )}
        </div>
        <div className="p-4">
          <h3 className="mb-2 line-clamp-2 text-sm font-medium text-foreground group-hover:text-primary transition-colors">
            {product.title}
          </h3>
          <div className="mb-2 flex items-center gap-1">
            <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />
            <span className="text-xs text-muted-foreground">
              {toPersianDigits(product.rating)} ({toPersianDigits(product.reviewCount)} نظر)
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

/* -------------------------------------------------------------------------- */
/*                              Main Page Component                           */
/* -------------------------------------------------------------------------- */

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, ease: "easeOut" },
};

const stagger = {
  animate: {
    transition: {
      staggerChildren: 0.1,
    },
  },
};

export default function ProductDetailPage() {
  const [selectedImage, setSelectedImage] = useState(0);
  const [selectedColor, setSelectedColor] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [isWishlisted, setIsWishlisted] = useState(false);
  const addItem = useCartStore((state) => state.addItem);

  const product = sampleProduct;
  const discount = Math.round(
    ((product.originalPrice - product.price) / product.originalPrice) * 100,
  );

  function handleAddToCart() {
    addItem({
      productId: product.id,
      title: product.title,
      slug: product.slug,
      price: product.price,
      originalPrice: product.originalPrice,
      quantity,
      variant: product.colors[selectedColor]?.name,
    });
  }

  return (
    <div className="container-page">
      {/* ------------------------------------------------------------------ */}
      {/*  Breadcrumb                                                        */}
      {/* ------------------------------------------------------------------ */}
      <motion.nav
        className="mb-6 flex items-center gap-1 text-sm text-muted-foreground"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <Link href="/" className="hover:text-primary transition-colors">
          صفحه اصلی
        </Link>
        <ChevronLeft className="h-4 w-4" />
        <Link href="/products" className="hover:text-primary transition-colors">
          {product.category}
        </Link>
        <ChevronLeft className="h-4 w-4" />
        <span className="text-foreground">{product.subcategory}</span>
      </motion.nav>

      {/* ------------------------------------------------------------------ */}
      {/*  Product Overview                                                  */}
      {/* ------------------------------------------------------------------ */}
      <motion.section
        className="mb-12 grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-12"
        variants={stagger}
        initial="initial"
        animate="animate"
      >
        {/* Image Gallery */}
        <motion.div className="flex flex-col gap-4" variants={fadeInUp}>
          {/* Main Image */}
          <div className="relative aspect-square overflow-hidden rounded-2xl border border-border bg-muted">
            <div className="flex h-full items-center justify-center text-7xl text-muted-foreground select-none">
              📦
            </div>
            {discount > 0 && (
              <Badge
                variant="destructive"
                className="absolute left-3 top-3 rounded-full px-3 py-1 text-sm"
              >
                {toPersianDigits(discount)}% تخفیف
              </Badge>
            )}
            <button
              onClick={() => {
                // Share functionality placeholder
              }}
              className="absolute left-3 bottom-3 rounded-full bg-background/80 p-2 backdrop-blur-sm transition-colors hover:bg-background"
            >
              <Share2 className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>

          {/* Thumbnail Strip */}
          <div className="grid grid-cols-4 gap-3">
            {product.images.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedImage(idx)}
                className={cn(
                  "aspect-square overflow-hidden rounded-xl border-2 bg-muted transition-all",
                  selectedImage === idx
                    ? "border-primary ring-2 ring-primary/20"
                    : "border-border hover:border-muted-foreground/40",
                )}
              >
                <div className="flex h-full items-center justify-center text-2xl text-muted-foreground select-none">
                  📦
                </div>
              </button>
            ))}
          </div>
        </motion.div>

        {/* Product Info */}
        <motion.div className="flex flex-col gap-6" variants={fadeInUp}>
          {/* Title */}
          <div>
            <h1 className="mb-3 text-2xl font-bold leading-relaxed text-foreground lg:text-3xl">
              {product.title}
            </h1>
            <div className="flex items-center gap-3">
              <RatingStars rating={product.rating} size="md" />
              <span className="text-sm text-muted-foreground">
                {toPersianDigits(product.rating)} از ۵
              </span>
              <Separator orientation="vertical" className="h-4" />
              <span className="text-sm text-muted-foreground">
                {toPersianDigits(product.reviewCount)} نظر
              </span>
            </div>
          </div>

          <Separator />

          {/* Price Section */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-4">
              <span className="text-3xl font-extrabold text-primary">
                {formatPrice(product.price)}
              </span>
              {discount > 0 && (
                <Badge variant="destructive" className="rounded-full text-sm">
                  {toPersianDigits(discount)}%
                </Badge>
              )}
            </div>
            {product.originalPrice > product.price && (
              <span className="price-discount text-base">
                {formatPrice(product.originalPrice)}
              </span>
            )}
          </div>

          <Separator />

          {/* Color Selector */}
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium text-foreground">
              رنگ:{" "}
              <span className="text-muted-foreground">
                {product.colors[selectedColor]?.name}
              </span>
            </span>
            <div className="flex items-center gap-3">
              {product.colors.map((color, idx) => (
                <button
                  key={idx}
                  onClick={() => setSelectedColor(idx)}
                  title={color.name}
                  className={cn(
                    "relative h-9 w-9 rounded-full border-2 transition-all",
                    selectedColor === idx
                      ? "border-primary ring-2 ring-primary/20"
                      : "border-border hover:border-muted-foreground/50",
                  )}
                  style={{ backgroundColor: color.value }}
                >
                  {selectedColor === idx && (
                    <Check className="absolute inset-0 m-auto h-4 w-4 text-white drop-shadow-md" />
                  )}
                </button>
              ))}
            </div>
          </div>

          <Separator />

          {/* Quantity Selector */}
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium text-foreground">تعداد</span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="icon"
                className="h-10 w-10 rounded-xl"
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                disabled={quantity <= 1}
              >
                <Minus className="h-4 w-4" />
              </Button>
              <span className="flex h-10 w-14 items-center justify-center text-lg font-semibold text-foreground">
                {toPersianDigits(quantity)}
              </span>
              <Button
                variant="outline"
                size="icon"
                className="h-10 w-10 rounded-xl"
                onClick={() => setQuantity((q) => Math.min(10, q + 1))}
                disabled={quantity >= 10}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col gap-3">
            <motion.div whileTap={{ scale: 0.97 }}>
              <Button
                size="lg"
                className="w-full gap-2 rounded-xl text-base font-semibold h-12"
                onClick={handleAddToCart}
              >
                <ShoppingCart className="h-5 w-5" />
                افزودن به سبد خرید
              </Button>
            </motion.div>
            <Button
              variant="outline"
              size="lg"
              className={cn(
                "w-full gap-2 rounded-xl text-base h-12",
                isWishlisted && "border-red-300 text-red-500 hover:text-red-600",
              )}
              onClick={() => setIsWishlisted(!isWishlisted)}
            >
              <Heart
                className={cn(
                  "h-5 w-5",
                  isWishlisted && "fill-red-500 text-red-500",
                )}
              />
              {isWishlisted
                ? "حذف از علاقه‌مندی‌ها"
                : "افزودن به علاقه‌مندی‌ها"}
            </Button>
          </div>

          <Separator />

          {/* Key Features */}
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium text-foreground">
              ویژگی‌های کلیدی
            </span>
            <ul className="flex flex-col gap-2">
              {product.features.map((feature, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          </div>

          <Separator />

          {/* Shipping & Return */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 rounded-xl bg-muted/60 p-3">
              <Truck className="h-5 w-5 shrink-0 text-primary" />
              <span className="text-sm text-foreground">
                ارسال رایگان برای سفارش‌های بالای ۵۰۰ هزار تومان
              </span>
            </div>
            <div className="flex items-center gap-3 rounded-xl bg-muted/60 p-3">
              <RotateCcw className="h-5 w-5 shrink-0 text-primary" />
              <span className="text-sm text-foreground">
                ۷ روز ضمانت بازگشت کالا
              </span>
            </div>
            <div className="flex items-center gap-3 rounded-xl bg-muted/60 p-3">
              <Shield className="h-5 w-5 shrink-0 text-primary" />
              <span className="text-sm text-foreground">
                ضمانت اصالت و سلامت فیزیکی کالا
              </span>
            </div>
          </div>
        </motion.div>
      </motion.section>

      {/* ------------------------------------------------------------------ */}
      {/*  Product Details Tabs                                              */}
      {/* ------------------------------------------------------------------ */}
      <motion.section
        className="mb-12"
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <Tabs defaultValue="description" className="w-full">
          <TabsList className="mb-6 w-full justify-start gap-1 rounded-xl bg-muted p-1 h-auto flex-wrap">
            <TabsTrigger
              value="description"
              className="rounded-lg px-6 py-2.5 text-sm"
            >
              توضیحات
            </TabsTrigger>
            <TabsTrigger
              value="specifications"
              className="rounded-lg px-6 py-2.5 text-sm"
            >
              مشخصات فنی
            </TabsTrigger>
            <TabsTrigger
              value="reviews"
              className="rounded-lg px-6 py-2.5 text-sm"
            >
              نظرات کاربران ({toPersianDigits(product.reviewCount)})
            </TabsTrigger>
          </TabsList>

          {/* Description Tab */}
          <TabsContent value="description">
            <Card className="p-6 lg:p-8">
              <div className="prose prose-sm max-w-none text-foreground leading-8">
                {product.description.split("\n\n").map((para, idx) => (
                  <p key={idx} className="mb-4 last:mb-0">
                    {para}
                  </p>
                ))}
              </div>
            </Card>
          </TabsContent>

          {/* Specifications Tab */}
          <TabsContent value="specifications">
            <Card className="overflow-hidden">
              <div className="divide-y divide-border">
                {Object.entries(product.specifications).map(
                  ([key, value], idx) => (
                    <div
                      key={key}
                      className={cn(
                        "grid grid-cols-2 gap-4 px-6 py-4 text-sm",
                        idx % 2 === 0 ? "bg-muted/40" : "bg-card",
                      )}
                    >
                      <span className="font-medium text-foreground">{key}</span>
                      <span className="text-muted-foreground">{value}</span>
                    </div>
                  ),
                )}
              </div>
            </Card>
          </TabsContent>

          {/* Reviews Tab */}
          <TabsContent value="reviews">
            <div className="flex flex-col gap-6">
              {/* Reviews Summary */}
              <Card className="p-6">
                <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-8">
                  <div className="flex flex-col items-center gap-2">
                    <span className="text-5xl font-extrabold text-foreground">
                      {toPersianDigits(product.rating)}
                    </span>
                    <RatingStars rating={product.rating} size="md" />
                    <span className="text-sm text-muted-foreground">
                      از {toPersianDigits(product.reviewCount)} نظر
                    </span>
                  </div>
                  <Separator
                    orientation="vertical"
                    className="hidden h-20 sm:block"
                  />
                  <div className="flex flex-1 flex-col gap-2">
                    {[5, 4, 3, 2, 1].map((star) => {
                      const pct =
                        star === 5
                          ? 65
                          : star === 4
                            ? 25
                            : star === 3
                              ? 7
                              : star === 2
                                ? 2
                                : 1;
                      return (
                        <div key={star} className="flex items-center gap-3">
                          <span className="w-3 text-sm text-muted-foreground">
                            {toPersianDigits(star)}
                          </span>
                          <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full rounded-full bg-yellow-400 transition-all"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="w-8 text-xs text-muted-foreground">
                            {toPersianDigits(pct)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </Card>

              {/* Individual Reviews */}
              {sampleReviews.map((review) => (
                <Card key={review.id} className="p-6">
                  <div className="flex flex-col gap-4">
                    {/* Review Header */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                          {review.author.charAt(0)}
                        </div>
                        <div>
                          <span className="block text-sm font-medium text-foreground">
                            {review.author}
                          </span>
                          <span className="block text-xs text-muted-foreground">
                            {review.date}
                          </span>
                        </div>
                      </div>
                      <RatingStars rating={review.rating} />
                    </div>

                    {/* Review Text */}
                    <p className="text-sm leading-7 text-foreground">
                      {review.text}
                    </p>

                    {/* Pros & Cons */}
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      {review.pros.length > 0 && (
                        <div className="flex flex-col gap-2">
                          <span className="text-xs font-medium text-emerald-600">
                            نقاط قوت
                          </span>
                          <ul className="flex flex-col gap-1.5">
                            {review.pros.map((pro, idx) => (
                              <li
                                key={idx}
                                className="flex items-center gap-2 text-xs text-muted-foreground"
                              >
                                <Plus className="h-3 w-3 text-emerald-500" />
                                {pro}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {review.cons.length > 0 && (
                        <div className="flex flex-col gap-2">
                          <span className="text-xs font-medium text-red-500">
                            نقاط ضعف
                          </span>
                          <ul className="flex flex-col gap-1.5">
                            {review.cons.map((con, idx) => (
                              <li
                                key={idx}
                                className="flex items-center gap-2 text-xs text-muted-foreground"
                              >
                                <Minus className="h-3 w-3 text-red-400" />
                                {con}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </motion.section>

      {/* ------------------------------------------------------------------ */}
      {/*  Mobile Accordion (visible on small screens as alternative)        */}
      {/* ------------------------------------------------------------------ */}
      {/* Note: The tabs above work on mobile too, but an accordion is provided
          in the FAQ/policy section at the bottom for additional info.       */}

      {/* ------------------------------------------------------------------ */}
      {/*  Related Products                                                  */}
      {/* ------------------------------------------------------------------ */}
      <motion.section
        className="mb-8"
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <h2 className="mb-6 text-xl font-bold text-foreground">
          محصولات مرتبط
        </h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {relatedProducts.map((rp) => (
            <RelatedProductCard key={rp.id} product={rp} />
          ))}
        </div>
      </motion.section>

      {/* ------------------------------------------------------------------ */}
      {/*  FAQ Accordion                                                     */}
      {/* ------------------------------------------------------------------ */}
      <motion.section
        className="mb-8"
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <h2 className="mb-6 text-xl font-bold text-foreground">
          سوالات متداول
        </h2>
        <Card className="p-6">
          <Accordion type="single" collapsible className="w-full">
            <AccordionItem value="warranty">
              <AccordionTrigger>شرایط گارانتی چگونه است؟</AccordionTrigger>
              <AccordionContent>
                این محصول دارای ۱۸ ماه گارانتی شرکتی است. در صورت بروز هرگونه
                مشکل فنی، می‌توانید از طریق مراکز مجاز خدمات پس از فروش اقدام
                نمایید.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="shipping">
              <AccordionTrigger>مدت زمان ارسال چقدر است؟</AccordionTrigger>
              <AccordionContent>
                ارسال سفارشات در تهران ۱ تا ۲ روز کاری و در شهرستان‌ها ۲ تا ۵
                روز کاری زمان می‌برد. برای سفارش‌های بالای ۵۰۰ هزار تومان ارسال
                رایگان است.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="return">
              <AccordionTrigger>
                آیا امکان بازگشت کالا وجود دارد؟
              </AccordionTrigger>
              <AccordionContent>
                بله، شما می‌توانید تا ۷ روز پس از دریافت کالا، در صورت عدم
                رضایت یا وجود ایراد، درخواست بازگشت ثبت نمایید. کالا باید در
                بسته‌بندی اصلی و بدون استفاده باشد.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </Card>
      </motion.section>
    </div>
  );
}
