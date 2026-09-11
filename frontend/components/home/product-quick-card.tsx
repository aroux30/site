"use client";

import Link from "next/link";
import Image from "next/image";
import { ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TiltCard3D } from "@/components/3d/tilt-card-3d";
import { formatPrice } from "@/lib/utils";
import { useAddToCart } from "@/lib/api/queries";
import { playAddToCartChime } from "@/lib/audio-effects";
import type { ApiProduct } from "@/lib/api/services";

interface ProductQuickCardProps {
  product: ApiProduct;
  featured?: boolean;
}

export function ProductQuickCard({ product, featured }: ProductQuickCardProps) {
  const addToCart = useAddToCart();

  const handleAddToCart = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    playAddToCartChime();
    addToCart.mutate({
      product_id: product.id,
      quantity: 1,
    });
  };

  const image =
    product.primary_image_url ||
    "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800";

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
            <Image
              src={image}
              alt={product.name}
              fill
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
              {formatPrice(product.min_price || 0)} تومان
            </span>
          </div>
          <Button
            size="sm"
            onClick={handleAddToCart}
            disabled={addToCart.isPending}
            className="rounded-xl font-bold h-9 px-3.5 gap-1.5 shadow-sm"
          >
            <ShoppingCart className="w-3.5 h-3.5" />
            <span className="text-xs">خرید</span>
          </Button>
        </div>
      </div>
    </TiltCard3D>
  );
}
