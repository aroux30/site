"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Heart, ShoppingCart, Trash2, ArrowLeft, Package, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useWishlist, useToggleWishlist, useAddToCart } from "@/lib/api/queries";
import { formatPrice } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";

export default function FavoritesPage() {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const {
    data: wishlistData,
    isLoading: isWishlistLoading,
    isError: isWishlistError,
    refetch: refetchWishlist,
  } = useWishlist();
  const toggleWishlist = useToggleWishlist();
  const addToCart = useAddToCart();

  const items = wishlistData?.items || [];

  return (
    <div className="container mx-auto px-4 py-12 max-w-6xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 mb-8 border-b border-border">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/10 text-rose-500 text-xs font-semibold mb-2">
            <Heart className="w-3.5 h-3.5 fill-current" />
            علاقه‌مندی‌های من
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-foreground">
            لیست کالاهای مورد علاقه
          </h1>
        </div>

        <Link href="/products">
          <Button variant="outline" size="sm" className="gap-2 text-xs">
            ادامه گشت‌و‌گذار در محصولات
            <ArrowLeft className="w-3.5 h-3.5" />
          </Button>
        </Link>
      </div>

      {!isAuthenticated && !isAuthLoading ? (
        <div className="text-center py-16 bg-muted/20 rounded-3xl border border-border p-8 max-w-lg mx-auto">
          <div className="w-16 h-16 rounded-full bg-rose-500/10 text-rose-500 flex items-center justify-center mx-auto mb-4">
            <Heart className="w-8 h-8" />
          </div>
          <h3 className="text-xl font-bold mb-2">برای مشاهده علاقه‌مندی‌ها وارد شوید</h3>
          <p className="text-sm text-muted-foreground mb-6">
            با ورود به حساب کاربری، کالاهای ذخیره‌شده شما در تمامی دستگاه‌ها همگام خواهند شد.
          </p>
          <Link href="/login?redirect=/favorites">
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold w-full">
              ورود به حساب کاربری
            </Button>
          </Link>
        </div>
      ) : isWishlistError ? (
        <div className="text-center py-16 bg-destructive/5 rounded-3xl border border-destructive/20 p-8 max-w-lg mx-auto">
          <h3 className="text-lg font-bold mb-2 text-destructive">
            دریافت لیست علاقه‌مندی‌ها ممکن نشد
          </h3>
          <p className="text-sm text-muted-foreground mb-6">
            اتصال با سرور برقرار نشد. لطفاً دوباره تلاش کنید.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => refetchWishlist()}
          >
            تلاش مجدد
          </Button>
        </div>
      ) : isWishlistLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-2xl border border-border bg-card p-4 space-y-3 animate-pulse">
              <div className="w-full h-44 bg-muted rounded-xl" />
              <div className="h-4 bg-muted rounded w-3/4" />
              <div className="h-4 bg-muted rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 bg-card rounded-3xl border border-border p-8 shadow-sm">
          <div className="w-20 h-20 rounded-full bg-muted/60 text-muted-foreground flex items-center justify-center mx-auto mb-4">
            <Heart className="w-10 h-10 stroke-1" />
          </div>
          <h3 className="text-xl font-bold mb-2">لیست علاقه‌مندی‌های شما خالی است</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto mb-6">
            با کلیک روی آیکون قلب روی هر کالا در صفحه محصولات، می‌توانید آن را به این لیست اضافه نمایید.
          </p>
          <Link href="/products">
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-2">
              <Package className="w-4 h-4" />
              مشاهده محصولات فروشگاه
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {items.map((item: any) => {
            const product = item.product || item;
            const price = product.price || product.min_price || 0;
            const image = product.primary_image_url || product.images?.[0]?.url || "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600";

            return (
              <Card key={item.id || product.id} className="group overflow-hidden rounded-2xl border-border bg-card hover:shadow-lg transition-all flex flex-col justify-between">
                <div>
                  <div className="relative w-full h-48 bg-muted/30 overflow-hidden">
                    <Image
                      src={image}
                      alt={product.name}
                      fill
                      className="object-contain p-4 group-hover:scale-105 transition-transform duration-500"
                    />
                    <button
                      onClick={() => toggleWishlist.mutate(product.id)}
                      className="absolute top-3 left-3 p-2 rounded-full bg-background/80 backdrop-blur-md text-rose-500 hover:bg-rose-500 hover:text-white transition-colors shadow-sm"
                      title="حذف از علاقه‌مندی‌ها"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <CardContent className="p-4">
                    <Link href={`/products/${product.slug || product.id}`}>
                      <h3 className="font-bold text-sm leading-snug line-clamp-2 mb-2 group-hover:text-emerald-600 transition-colors">
                        {product.name}
                      </h3>
                    </Link>
                    <div className="text-emerald-600 dark:text-emerald-400 font-extrabold text-base">
                      {formatPrice(price)} تومان
                    </div>
                  </CardContent>
                </div>

                <div className="p-4 pt-0">
                  <Button
                    size="sm"
                    className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs gap-2"
                    onClick={() => {
                      addToCart.mutate({
                        product_id: product.id,
                        variant_id: product.variants?.[0]?.id,
                        quantity: 1,
                      });
                    }}
                  >
                    <ShoppingCart className="w-3.5 h-3.5" />
                    افزودن به سبد خرید
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
