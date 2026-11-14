"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StarRating } from "@/components/ui/star-rating";
import { ImageGallery } from "@/components/store/image-gallery";
import { RemoteImage } from "@/components/shared/remote-image";
import { cn, formatPrice, toPersianDigits } from "@/lib/utils";
import { useCart } from "@/hooks/use-cart";
import { playAddToCartChime } from "@/lib/audio-effects";
import { useToast } from "@/components/ui/use-toast";
import {
  Check,
  ExternalLink,
  Minus,
  Plus,
  ShoppingCart,
} from "lucide-react";
import type { ApiProduct } from "@/lib/api/services";

/* ─────────────────────────────────────────────────────────────────────
 * QuickViewModal — preview a product from the listing without
 * navigating to the full PDP.
 *
 * Usage:
 *   const [qvProduct, setQvProduct] = useState<ApiProduct | null>(null);
 *   <ProductCard onQuickView={setQvProduct} ... />
 *   <QuickViewModal product={qvProduct} onClose={() => setQvProduct(null)} />
 * ────────────────────────────────────────────────────────────────── */

interface QuickViewModalProps {
  product: (ApiProduct & {
    rating_average?: number;
    review_count?: number;
    images?: { url: string; alt?: string }[];
  }) | null;
  onClose: () => void;
}

export function QuickViewModal({ product, onClose }: QuickViewModalProps) {
  const { addToCart } = useCart();
  const { toast } = useToast();
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);
  const addedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset quantity when product changes
  useEffect(() => {
    setQuantity(1);
    setAdded(false);
    return () => {
      if (addedTimer.current) clearTimeout(addedTimer.current);
    };
  }, [product?.id]);

  if (!product) return null;

  const maxQty = product.max_order_quantity ?? 10;

  const handleAddToCart = async () => {
    setAdding(true);
    try {
      await addToCart({
        productId: product.id,
        title: product.name,
        slug: product.slug,
        price: product.min_price ?? 0,
        originalPrice:
          product.max_price && product.max_price > (product.min_price ?? 0)
            ? product.max_price
            : undefined,
        image: product.primary_image_url || undefined,
        maxQuantity: product.max_order_quantity ?? undefined,
        quantity,
      });
      playAddToCartChime();
      setAdded(true);
      addedTimer.current = setTimeout(() => setAdded(false), 2000);
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

  const hasDiscount =
    product.max_price &&
    product.min_price &&
    product.max_price > product.min_price;
  const discountPercent = hasDiscount
    ? Math.round(
        ((product.max_price! - product.min_price!) / product.max_price!) * 100
      )
    : 0;

  const galleryImages = product.images?.length
    ? product.images
    : product.primary_image_url
      ? [{ url: product.primary_image_url, alt: product.name }]
      : [];

  return (
    <Dialog open={!!product} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-3xl w-[95vw] max-h-[90vh] overflow-y-auto p-0">
        <DialogTitle className="sr-only">{product.name} - پیش‌نمایش سریع</DialogTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-0">
          {/* Image side */}
          <div className="bg-muted/20 p-4 md:p-6">
            {galleryImages.length > 1 ? (
              <ImageGallery
                images={galleryImages}
                productName={product.name}
              />
            ) : (
              <div className="aspect-square rounded-xl overflow-hidden bg-muted/10">
                <RemoteImage
                  src={product.primary_image_url}
                  alt={product.name}
                  sizes="(max-width: 768px) 90vw, 45vw"
                  className="object-contain p-4"
                />
              </div>
            )}
          </div>

          {/* Info side */}
          <div className="p-5 md:p-6 flex flex-col" dir="rtl">
            {/* Badges */}
            <div className="flex flex-wrap gap-2 mb-3">
              {product.is_featured && (
                <Badge className="bg-primary text-primary-foreground text-[10px]">
                  پیشنهاد ویژه
                </Badge>
              )}
              {discountPercent > 0 && (
                <Badge className="bg-red-500 text-white text-[10px]">
                  {toPersianDigits(discountPercent)}٪ تخفیف
                </Badge>
              )}
              {product.variant_count > 1 && (
                <Badge variant="secondary" className="text-[10px]">
                  {toPersianDigits(product.variant_count)} مدل
                </Badge>
              )}
            </div>

            {/* Title */}
            <h2 className="text-lg font-bold text-foreground leading-snug">
              {product.name}
            </h2>

            {/* Rating */}
            {product.rating_average !== undefined &&
              product.rating_average > 0 && (
                <div className="mt-2">
                  <StarRating
                    value={product.rating_average}
                    size="sm"
                    showValue
                    reviewCount={product.review_count}
                  />
                </div>
              )}

            {/* Description */}
            {product.short_description && (
              <p className="mt-3 text-sm text-muted-foreground leading-relaxed line-clamp-3">
                {product.short_description}
              </p>
            )}

            {/* Price */}
            <div className="mt-4 rounded-xl border border-border/60 bg-muted/20 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">قیمت:</span>
                <div className="text-end">
                  {hasDiscount && (
                    <span className="block text-xs text-muted-foreground line-through">
                      {formatPrice(product.max_price!)}
                    </span>
                  )}
                  <span className="text-xl font-black text-primary">
                    {product.min_price != null
                      ? formatPrice(product.min_price)
                      : "تماس بگیرید"}
                  </span>
                </div>
              </div>
            </div>

            {/* Quantity + Add to cart */}
            <div className="mt-4 flex items-center gap-3">
              {/* Quantity stepper */}
              <div className="flex items-center rounded-xl border border-border/60 overflow-hidden">
                <button
                  type="button"
                  onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                  disabled={quantity <= 1}
                  className="h-10 w-10 flex items-center justify-center text-muted-foreground hover:bg-muted/50 transition-colors disabled:opacity-30"
                  aria-label="کاهش تعداد"
                >
                  <Minus className="h-3.5 w-3.5" />
                </button>
                <span className="h-10 w-10 flex items-center justify-center text-sm font-bold tabular-nums border-x border-border/60">
                  {toPersianDigits(quantity)}
                </span>
                <button
                  type="button"
                  onClick={() => setQuantity((q) => Math.min(maxQty, q + 1))}
                  disabled={quantity >= maxQty}
                  className="h-10 w-10 flex items-center justify-center text-muted-foreground hover:bg-muted/50 transition-colors disabled:opacity-30"
                  aria-label="افزایش تعداد"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Add to cart button */}
              <Button
                onClick={handleAddToCart}
                disabled={adding || product.min_price == null}
                className="flex-1 rounded-xl font-bold h-10 gap-2 bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                {added ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <ShoppingCart className="w-4 h-4" />
                )}
                {added ? "اضافه شد" : "افزودن به سبد"}
              </Button>
            </div>

            {/* View full details link */}
            <Link
              href={`/products/${product.slug || product.id}`}
              onClick={onClose}
              className="mt-4 inline-flex items-center gap-1.5 text-sm text-primary hover:underline underline-offset-4 transition-colors"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              مشاهده جزئیات کامل محصول
            </Link>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
