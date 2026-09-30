"use client";

import { useState } from "react";
import Link from "next/link";
import { RemoteImage } from "@/components/shared/remote-image";
import { Check, ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TiltCard3D } from "@/components/3d/tilt-card-3d";
import { formatPrice } from "@/lib/utils";
import { useCart } from "@/hooks/use-cart";
import { playAddToCartChime } from "@/lib/audio-effects";
import { useToast } from "@/components/ui/use-toast";
import type { ApiProduct } from "@/lib/api/services";

interface ProductQuickCardProps {
  product: ApiProduct;
  featured?: boolean;
}

export function ProductQuickCard({ product, featured }: ProductQuickCardProps) {
  const { addToCart } = useCart();
  const { toast } = useToast();
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);

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
      setTimeout(() => setAdded(false), 1800);
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

  const image = product.primary_image_url;

  const productHref = `/products/${product.slug || product.id}`;

  return (
    <TiltCard3D maxTilt={7} className="h-full">
      <div className="group relative h-full rounded-3xl border border-border/80 bg-card p-4 transition-all duration-300 hover:shadow-2xl hover:border-primary/40 flex flex-col justify-between">
        <div>
          {/* Image & Badges */}
          <Link
            href={productHref}
            aria-label={product.name}
            className="relative block h-48 sm:h-56 w-full rounded-2xl bg-muted/20 overflow-hidden mb-4"
          >
            <RemoteImage
              src={image}
              alt={product.name}
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 25vw"
              className="object-contain p-4 transition-transform duration-500 group-hover:scale-105"
            />
            {featured && (
              <Badge className="absolute top-3 right-3 bg-primary text-primary-foreground font-bold text-xs px-2.5 py-1">
                پیشنهاد ویژه
              </Badge>
            )}
            {product.variant_count && product.variant_count > 1 && (
              <Badge
                variant="secondary"
                className="absolute bottom-3 right-3 bg-background/80 backdrop-blur-md text-[11px]"
              >
                {product.variant_count} مدل و رنگ
              </Badge>
            )}
          </Link>

          {/* Product Info */}
          <div className="space-y-2">
            <Link href={productHref}>
              <h3 className="font-bold text-base leading-snug line-clamp-2 text-foreground group-hover:text-primary transition-colors">
                {product.name}
              </h3>
            </Link>
            {product.short_description && (
              <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                {product.short_description}
              </p>
            )}
          </div>
        </div>

        {/* Price & Action */}
        <div className="mt-4 pt-3 border-t border-border/60 flex items-center justify-between gap-2">
          <div>
            <span className="text-xs text-muted-foreground block">قیمت:</span>
            <span className="text-base sm:text-lg font-black text-primary">
              {formatPrice(product.min_price || 0)}
            </span>
          </div>
          <Button
            size="sm"
            onClick={handleAddToCart}
            disabled={adding}
            className="rounded-xl font-bold h-9 px-3.5 gap-1.5 shadow-sm"
          >
            {added ? (
              <Check className="w-3.5 h-3.5" />
            ) : (
              <ShoppingCart className="w-3.5 h-3.5" />
            )}
            <span className="text-xs">{added ? "اضافه شد" : "خرید"}</span>
          </Button>
        </div>
      </div>
    </TiltCard3D>
  );
}
