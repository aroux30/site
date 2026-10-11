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
  Sparkles,
  ChevronLeft,
  Info,
  CheckCircle2,
} from "lucide-react";
import { useCompareStore, MAX_COMPARE_PRODUCTS } from "@/stores/compare-store";
import { FeatureGuard } from "@/components/store/feature-guard";
import { useToast } from "@/components/ui/use-toast";
import { useCart } from "@/hooks/use-cart";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { formatPrice, toPersianDigits, cn } from "@/lib/utils";
import type { Product } from "@/types/product";

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

function ComparePageInner() {
  const { products, removeProduct, clearCompare } =
    useCompareStore();
  const { addToCart } = useCart();

  const [mounted, setMounted] = useState(false);
  const [highlightDiff, setHighlightDiff] = useState(false);
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setMounted(true);
  }, []);

  const { toast } = useToast();

  const handleAddToCart = async (product: Product) => {
    try {
      await addToCart({
        productId: product.id,
        title: product.title,
        slug: product.slug,
        price: product.price,
        originalPrice: product.originalPrice,
        image: product.thumbnail || product.images?.[0]?.url,
        sku: product.sku,
        quantity: 1,
      });
    } catch (err: unknown) {
      // Server rejected the add (e.g. insufficient stock) — the store has
      // already rolled the optimistic line back (QA B19).
      toast({
        title: "افزودن به سبد ناموفق بود",
        description: (err as { message?: string })?.message,
        variant: "destructive",
      });
      return;
    }

    setAddedIds((prev) => ({ ...prev, [product.id]: true }));
    setTimeout(() => {
      setAddedIds((prev) => ({ ...prev, [product.id]: false }));
    }, 1500);
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
            <p className="text-xs sm:text-sm text-muted-foreground ps-13">
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
                          <Star className="h-3.5 w-3.5 fill-amber-400 me-1" />
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
                            <Check className="h-3 w-3 me-1" />
                            موجود در انبار
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20 text-[11px] font-medium"
                          >
                            <X className="h-3 w-3 me-1" />
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
                className="p-3 ps-6 text-xs text-primary uppercase tracking-wider font-extrabold"
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
                    className="p-3 ps-6 text-xs text-primary uppercase tracking-wider font-extrabold"
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
                      <Link
                      href={`/products?search=${encodeURIComponent(product.title)}`}
                      className="w-full"
                    >
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

/** Redirects away when the compare module switch is off. */
export default function ComparePage() {
  return (
    <FeatureGuard feature="compare">
      <ComparePageInner />
    </FeatureGuard>
  );
}
