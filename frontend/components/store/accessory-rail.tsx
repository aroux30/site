"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Plus, PackageOpen } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { fetchProductAccessories, type ApiProductAccessory } from "@/lib/api/services";
import { useCart } from "@/hooks/use-cart";
import { formatPrice, toPersianDigits } from "@/lib/utils";

interface AccessoryRailProps {
  /** Product whose accessories should be offered. */
  productId: string;
  /** Section heading shown above the rail. */
  title?: string;
  className?: string;
}

/**
 * Cross-sell upsell rail (Odoo website_sale "accessory_product_ids" concept).
 *
 * Renders the active accessories linked to a product and lets the shopper add
 * one to the cart in a single click. Prices arrive from the API already in
 * Toman; they are passed to the cart unchanged (integer, no float math).
 */
export function AccessoryRail({ productId, title = "کالاهای مکمل", className }: AccessoryRailProps) {
  const { addToCart } = useCart();
  const [items, setItems] = useState<ApiProductAccessory[]>([]);
  const [addedId, setAddedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!productId) return;
    fetchProductAccessories(productId).then((data) => {
      if (!cancelled) setItems(data);
    });
    return () => {
      cancelled = true;
    };
  }, [productId]);

  if (items.length === 0) return null;

  const handleAdd = async (accessory: ApiProductAccessory) => {
    try {
      await addToCart({
        productId: accessory.id,
        title: accessory.name,
        slug: accessory.slug,
        price: accessory.price ?? 0,
        image: accessory.image_url ?? undefined,
        quantity: 1,
      });
      setAddedId(accessory.id);
      window.setTimeout(() => setAddedId((cur) => (cur === accessory.id ? null : cur)), 1500);
    } catch {
      // addToCart surfaces its own toast/error state; keep the rail quiet.
    }
  };

  return (
    <section className={className} aria-label={title}>
      <h2 className="mb-4 text-lg font-bold text-foreground">{title}</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {items.map((accessory) => (
          <Card key={accessory.id} className="overflow-hidden">
            <Link
              href={`/products/${accessory.slug}`}
              className="block"
              aria-label={accessory.name}
            >
              <div className="relative aspect-square w-full bg-muted">
                {accessory.image_url ? (
                  <Image
                    src={accessory.image_url}
                    alt={accessory.name}
                    fill
                    sizes="(max-width: 640px) 50vw, 25vw"
                    className="object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                    <PackageOpen className="h-10 w-10" />
                  </div>
                )}
              </div>
            </Link>
            <CardContent className="flex flex-col gap-2 p-3">
              <Link
                href={`/products/${accessory.slug}`}
                className="line-clamp-2 text-sm font-medium leading-snug text-foreground hover:text-primary"
              >
                {accessory.name}
              </Link>
              {accessory.price != null && (
                <span className="text-sm font-bold text-primary">
                  {formatPrice(accessory.price)}
                </span>
              )}
              <Button
                size="sm"
                variant={addedId === accessory.id ? "default" : "outline"}
                className="mt-auto w-full"
                onClick={() => handleAdd(accessory)}
              >
                <Plus className="ml-1 h-4 w-4" />
                {addedId === accessory.id ? "افزوده شد" : "افزودن"}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
