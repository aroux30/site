"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import {
  ShoppingBag,
  X,
  Plus,
  Minus,
  Trash2,
  ArrowLeft,
  Truck,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useCart } from "@/hooks/use-cart";
import { formatPrice, toPersianDigits } from "@/lib/utils";

interface CartDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CartDrawer({ isOpen, onClose }: CartDrawerProps) {
  const {
    items,
    totalItems,
    subtotal,
    totalPrice,
    updateItemQuantity,
    removeFromCart,
    getCartSummary,
  } = useCart();

  const summary = getCartSummary();

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex" dir="rtl">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300 animate-in fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer Panel (RTL: Slides in from left / start-0) */}
      <div className="relative me-auto flex h-full w-full max-w-md flex-col bg-background shadow-2xl z-10 border-e border-border animate-in ltr:slide-in-from-left rtl:slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <ShoppingBag className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-foreground">سبد خرید شما</h2>
              <span className="text-xs text-muted-foreground">
                {toPersianDigits(totalItems)} قلم کالا
              </span>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-8 w-8 rounded-xl"
            aria-label="بستن سبد خرید"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Free Shipping Progress Indicator */}
        <div className="border-b border-border bg-primary/5 p-4">
          {summary.freeShippingEligible ? (
            <div className="flex items-center gap-2 text-xs font-bold text-emerald-600">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>تبریک! سفارش شما مشمول ارسال کاملاً رایگان شد.</span>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-foreground font-medium">
                <span className="flex items-center gap-1.5">
                  <Truck className="h-4 w-4 text-primary" />
                  <span>
                    فقط{" "}
                    <strong className="text-primary font-bold">
                      {formatPrice(summary.freeShippingRemaining)}
                    </strong>{" "}
                    دیگر تا ارسال رایگان
                  </span>
                </span>
                <span className="font-mono text-muted-foreground text-[11px]">
                  {toPersianDigits(Math.round((subtotal / 5000000) * 100))}٪
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, Math.round((subtotal / 5000000) * 100))}%`,
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Cart Items List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 divide-y divide-border/40">
          {items.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full py-16 text-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-muted/60 text-muted-foreground mb-4">
                <ShoppingBag className="h-10 w-10 opacity-40" />
              </div>
              <h3 className="text-base font-bold text-foreground mb-1">
                سبد خرید شما خالی است
              </h3>
              <p className="text-xs text-muted-foreground max-w-xs mb-6 leading-relaxed">
                می‌توانید از بخش محصولات دیدن کنید و کالاهای مورد علاقه خود را اضافه نمایید.
              </p>
              <Link href="/products" onClick={onClose}>
                <Button size="sm" className="rounded-xl px-6 font-bold">
                  مشاهده کاتالوگ محصولات
                </Button>
              </Link>
            </div>
          ) : (
            items.map((item) => {
              const lineKey = item.variantId || item.productId;
              return (
                <div key={lineKey} className="pt-3 first:pt-0 flex gap-3">
                  {/* Thumbnail */}
                  <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-xl border border-border bg-muted/40 p-1 flex items-center justify-center">
                    {item.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={item.image}
                        alt={item.title}
                        className="max-h-full max-w-full object-contain"
                      />
                    ) : (
                      <ShoppingBag className="h-8 w-8 text-muted-foreground/30" />
                    )}
                  </div>

                  {/* Details */}
                  <div className="flex flex-1 flex-col justify-between">
                    <div>
                      <div className="flex items-start justify-between gap-1">
                        <Link
                          href={item.slug ? `/products/${item.slug}` : "/products"}
                          onClick={onClose}
                          className="line-clamp-2 text-xs font-bold text-foreground hover:text-primary transition-colors leading-snug"
                        >
                          {item.title}
                        </Link>
                        <button
                          type="button"
                          onClick={() => removeFromCart(lineKey)}
                          className="text-muted-foreground hover:text-red-500 transition-colors p-1"
                          title="حذف"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      {item.variant && (
                        <span className="text-[10px] text-muted-foreground block mt-0.5">
                          مدل / رنگ: {item.variant}
                        </span>
                      )}
                    </div>

                    {/* Stepper and Price */}
                    <div className="flex items-center justify-between pt-1">
                      <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/30 p-0.5">
                        <button
                          type="button"
                          onClick={() =>
                            updateItemQuantity(lineKey, Math.max(1, item.quantity - 1))
                          }
                          className="flex h-6 w-6 items-center justify-center rounded text-foreground hover:bg-background"
                        >
                          <Minus className="h-3 w-3" />
                        </button>
                        <span className="w-6 text-center text-xs font-bold font-mono">
                          {toPersianDigits(item.quantity)}
                        </span>
                        <button
                          type="button"
                          onClick={() => updateItemQuantity(lineKey, item.quantity + 1)}
                          className="flex h-6 w-6 items-center justify-center rounded text-foreground hover:bg-background"
                        >
                          <Plus className="h-3 w-3" />
                        </button>
                      </div>

                      <span className="text-xs font-black text-foreground">
                        {formatPrice(item.price * item.quantity)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer with Checkout Actions */}
        {items.length > 0 && (
          <div className="border-t border-border bg-card p-5 space-y-3 shadow-lg">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">مبلغ کل قابل پرداخت:</span>
              <span className="text-base font-black text-primary">
                {formatPrice(totalPrice)}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2.5 pt-1">
              <Link href="/checkout" onClick={onClose} className="col-span-1">
                <Button className="w-full rounded-xl font-bold text-xs gap-1.5 h-11 shadow-md">
                  <span>تکمیل سفارش</span>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </Link>

              <Link href="/cart" onClick={onClose} className="col-span-1">
                <Button
                  variant="outline"
                  className="w-full rounded-xl text-xs gap-1.5 h-11 border-border"
                >
                  <span>مشاهده سبد</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
