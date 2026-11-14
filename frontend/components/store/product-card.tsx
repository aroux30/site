"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { RemoteImage } from "@/components/shared/remote-image";
import { Check, Eye, Heart, ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StarRating } from "@/components/ui/star-rating";
import { ClickSpark } from "@/components/ui/click-spark";
import { PulseHeart } from "@/components/ui/pulse-heart";
import { cn, formatPrice, toPersianDigits } from "@/lib/utils";
import { useCart } from "@/hooks/use-cart";
import { playAddToCartChime } from "@/lib/audio-effects";
import { useToast } from "@/components/ui/use-toast";
import type { ApiProduct } from "@/lib/api/services";

/* ─────────────────────────────────────────────────────────────────────
 * ProductCard — the ONE reusable product card for the entire store
 *
 * Used in: homepage grid, product listing, search results, category
 * pages, recently-viewed, recommendations, and quick-view trigger.
 *
 * Props keep it flexible:
 *   - variant="default" for listings, "compact" for sidebars/rails
 *   - onQuickView callback enables the quick-view button
 *   - wishlist props gate the heart button via feature flags
 * ────────────────────────────────────────────────────────────────── */

interface ProductCardProps {
  product: ApiProduct & {
    /** Rating 0–5 (optional, from search/listing enrichment) */
    rating_average?: number;
    /** Number of reviews */
    review_count?: number;
    /** Category name for display */
    category_name?: string;
  };
  /** Card visual variant */
  variant?: "default" | "compact";
  /** Show "پیشنهاد ویژه" badge */
  featured?: boolean;
  /** Quick-view callback — when provided, shows the eye icon */
  onQuickView?: (product: ApiProduct) => void;
  /** Wishlist state */
  isWishlisted?: boolean;
  /** Wishlist toggle — when provided, shows the heart icon */
  onToggleWishlist?: (productId: string) => void;
  /** Additional classes on the outer wrapper */
  className?: string;
}

export function ProductCard({
  product,
  variant = "default",
  featured,
  onQuickView,
  isWishlisted,
  onToggleWishlist,
  className,
}: ProductCardProps) {
  const { addToCart } = useCart();
  const { toast } = useToast();
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setAdding(true);
    try {
      await addToCart({
        productId: product.id,
        title: product.name,
        slug: product.slug,
        price: product.min_price || 0,
        originalPrice:
          product.max_price && product.max_price > (product.min_price || 0)
            ? product.max_price
            : undefined,
        image: product.primary_image_url || undefined,
      });
      playAddToCartChime();
      setAdded(true);
      timerRef.current = setTimeout(() => setAdded(false), 1800);
    } catch (err: unknown) {
      toast({
        title: "افزودن به سبد ناموفق بود",
        description: (err as { message?: string })?.message,
        variant: "destructive",
      });
    } finally {
      setAdding(false);
    }
  };

  const productHref = `/products/${product.slug || product.id}`;
  const hasDiscount =
    product.max_price &&
    product.min_price &&
    product.max_price > product.min_price;
  const discountPercent = hasDiscount
    ? Math.round(
        ((product.max_price! - product.min_price!) / product.max_price!) * 100
      )
    : 0;

  const isCompact = variant === "compact";

  return (
    <div
      className={cn(
        "group relative rounded-2xl border border-border/60 bg-card overflow-hidden transition-all duration-300 hover:shadow-xl hover:border-primary/30 flex flex-col",
        isCompact ? "p-3" : "p-4",
        className
      )}
    >
      {/* ─── Image ─── */}
      <Link
        href={productHref}
        aria-label={product.name}
        className={cn(
          "relative block w-full rounded-xl bg-muted/20 overflow-hidden",
          isCompact ? "h-36" : "h-48 sm:h-56"
        )}
      >
        <RemoteImage
          src={product.primary_image_url}
          alt={product.name}
          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
          className="object-contain p-3 transition-transform duration-500 group-hover:scale-105"
        />

        {/* Badges */}
        <div className="absolute top-2 start-2 flex flex-col gap-1.5">
          {(featured || product.is_featured) && (
            <Badge className="bg-primary text-primary-foreground text-[10px] px-2 py-0.5 font-bold">
              پیشنهاد ویژه
            </Badge>
          )}
          {discountPercent > 0 && (
            <Badge className="bg-red-500 text-white text-[10px] px-2 py-0.5 font-bold">
              {toPersianDigits(discountPercent)}٪ تخفیف
            </Badge>
          )}
        </div>

        {product.variant_count > 1 && (
          <Badge
            variant="secondary"
            className="absolute bottom-2 start-2 bg-background/80 backdrop-blur-md text-[10px]"
          >
            {toPersianDigits(product.variant_count)} مدل
          </Badge>
        )}

        {/* Hover action buttons */}
        <div className="absolute top-2 end-2 flex flex-col gap-1.5 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100 transition-opacity">
          {onQuickView && (
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onQuickView(product);
              }}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-background/90 backdrop-blur-sm border border-border/60 text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors shadow-sm"
              aria-label="مشاهده سریع"
            >
              <Eye className="h-3.5 w-3.5" />
            </button>
          )}
          {onToggleWishlist && (
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onToggleWishlist(product.id);
              }}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-background/90 backdrop-blur-sm border border-border/60 transition-colors shadow-sm"
              aria-label={isWishlisted ? "حذف از علاقه‌مندی‌ها" : "افزودن به علاقه‌مندی‌ها"}
            >
              <PulseHeart
                active={Boolean(isWishlisted)}
                size="sm"
                className="pointer-events-none"
              />
            </button>
          )}
        </div>
      </Link>

      {/* ─── Info ─── */}
      <div className={cn("flex-1 flex flex-col", isCompact ? "mt-2" : "mt-3")}>
        {/* Category */}
        {product.category_name && !isCompact && (
          <span className="text-[11px] text-muted-foreground mb-1 line-clamp-1">
            {product.category_name}
          </span>
        )}

        {/* Title */}
        <Link href={productHref}>
          <h3
            className={cn(
              "font-bold leading-snug text-foreground group-hover:text-primary transition-colors",
              isCompact
                ? "text-sm line-clamp-1"
                : "text-sm sm:text-base line-clamp-2"
            )}
          >
            {product.name}
          </h3>
        </Link>

        {/* Rating */}
        {product.rating_average !== undefined &&
          product.rating_average > 0 && (
            <div className="mt-1.5">
              <StarRating
                value={product.rating_average}
                size="xs"
                reviewCount={product.review_count}
              />
            </div>
          )}

        {/* Short description (default only) */}
        {!isCompact && product.short_description && (
          <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed mt-1.5">
            {product.short_description}
          </p>
        )}
      </div>

      {/* ─── Price & Action ─── */}
      <div
        className={cn(
          "flex items-center justify-between gap-2 border-t border-border/60",
          isCompact ? "mt-2 pt-2" : "mt-3 pt-3"
        )}
      >
        <div className="min-w-0">
          {hasDiscount && (
            <span className="block text-xs text-muted-foreground line-through">
              {formatPrice(product.max_price!)}
            </span>
          )}
          <span
            className={cn(
              "font-black text-primary",
              isCompact ? "text-sm" : "text-base sm:text-lg"
            )}
          >
            {product.min_price != null ? formatPrice(product.min_price) : "تماس بگیرید"}
          </span>
        </div>

        <ClickSpark>
          <Button
            size="sm"
            onClick={handleAddToCart}
            disabled={adding}
            aria-label={adding ? `در حال افزودن ${product.name} به سبد` : added ? `${product.name} اضافه شد` : `افزودن ${product.name} به سبد خرید`}
            aria-busy={adding}
            className={cn(
              "rounded-xl font-bold gap-1.5 shadow-sm bg-primary hover:bg-primary/90 text-primary-foreground shrink-0",
              isCompact ? "h-8 px-2.5" : "h-9 px-3.5"
            )}
          >
            {added ? (
              <Check className="w-3.5 h-3.5" />
            ) : (
              <ShoppingCart className="w-3.5 h-3.5" />
            )}
            <span className="text-xs">{added ? "اضافه شد" : "خرید"}</span>
          </Button>
        </ClickSpark>
      </div>
    </div>
  );
}
