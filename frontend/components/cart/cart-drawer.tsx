"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
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
  TicketPercent,
  Loader2,
  AlertCircle,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { useCart, type CartItem } from "@/hooks/use-cart";
import { formatPrice, toPersianDigits } from "@/lib/utils";

interface CartDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

/* -------------------------------------------------------------------------- */
/*  LineItem — reusable cart row (image, title, variant, stepper, line total) */
/* -------------------------------------------------------------------------- */

function CartLineItem({
  item,
  onUpdateQuantity,
  onRemove,
  onClose,
}: {
  item: CartItem;
  onUpdateQuantity: (id: string, q: number) => void;
  onRemove: (id: string) => void;
  onClose: () => void;
}) {
  const lineKey = item.variantId || item.productId;
  const maxQuantity = item.maxQuantity ?? 10;
  const atMaxQuantity = item.quantity >= maxQuantity;

  return (
    <div className="pt-3 first:pt-0 flex gap-3">
      {/* Thumbnail */}
      <Link
        href={item.slug ? `/products/${item.slug}` : "/products"}
        onClick={onClose}
        className="relative h-20 w-20 shrink-0 overflow-hidden rounded-xl border border-border bg-muted/40 flex items-center justify-center"
        aria-hidden="true"
        tabIndex={-1}
      >
        {item.image ? (
          <Image
            src={item.image}
            alt=""
            width={80}
            height={80}
            className="h-full w-full object-contain p-1"
          />
        ) : (
          <ShoppingBag className="h-8 w-8 text-muted-foreground/30" />
        )}
      </Link>

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
              onClick={() => onRemove(lineKey)}
              className="text-muted-foreground hover:text-destructive transition-colors p-1"
              aria-label={`حذف ${item.title} از سبد`}
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
              onClick={() => onUpdateQuantity(lineKey, Math.max(1, item.quantity - 1))}
              disabled={item.quantity <= 1}
              className="flex h-6 w-6 items-center justify-center rounded text-foreground hover:bg-background disabled:opacity-40"
              aria-label="کاهش تعداد"
            >
              <Minus className="h-3 w-3" />
            </button>
            <span className="w-6 text-center text-xs font-bold">
              {toPersianDigits(item.quantity)}
            </span>
            <button
              type="button"
              onClick={() => onUpdateQuantity(lineKey, item.quantity + 1)}
              disabled={atMaxQuantity}
              className="flex h-6 w-6 items-center justify-center rounded text-foreground hover:bg-background disabled:opacity-40"
              aria-label="افزایش تعداد"
            >
              <Plus className="h-3 w-3" />
            </button>
          </div>

          <div className="flex flex-col items-end">
            <span className="text-xs font-black text-foreground">
              {formatPrice(item.price * item.quantity)}
            </span>
            {item.quantity > 1 && (
              <span className="text-[10px] text-muted-foreground">
                {formatPrice(item.price)} × {toPersianDigits(item.quantity)}
              </span>
            )}
          </div>
        </div>

        {atMaxQuantity && (
          <span className="text-[10px] text-warning mt-1">
            حداکثر {toPersianDigits(maxQuantity)} عدد در سبد
          </span>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Cart Drawer                                                               */
/* -------------------------------------------------------------------------- */

export function CartDrawer({ isOpen, onClose }: CartDrawerProps) {
  const {
    items,
    totalItems,
    couponCode,
    couponDiscount,
    isLoading,
    isSyncing,
    error,
    updateItemQuantity,
    removeFromCart,
    fetchCart,
    applyCoupon,
    removeCoupon,
    getCartSummary,
  } = useCart();

  const summary = getCartSummary();

  // Coupon form state
  const [couponInput, setCouponInput] = useState("");
  const [couponPending, setCouponPending] = useState(false);
  const [couponError, setCouponError] = useState<string | null>(null);

  // Close on Escape key + lock body scroll while open
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

  const handleApplyCoupon = async () => {
    const code = couponInput.trim();
    if (!code || couponPending) return;
    setCouponPending(true);
    setCouponError(null);
    try {
      const res = await applyCoupon(code);
      if (res.success) {
        setCouponInput("");
      } else {
        setCouponError(res.message || "کد تخفیف معتبر نیست.");
      }
    } catch {
      setCouponError("اعمال کد تخفیف ممکن نشد. دوباره تلاش کن.");
    } finally {
      setCouponPending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex"
      dir="rtl"
      role="dialog"
      aria-modal="true"
      aria-label="سبد خرید"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300 animate-in fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer Panel (RTL: slides from start/right) */}
      <div className="relative me-auto flex h-full w-full max-w-md flex-col bg-background shadow-2xl z-10 border-e border-border animate-in ltr:slide-in-from-left rtl:slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <ShoppingBag className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-foreground">سبد خرید شما</h2>
              <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                {toPersianDigits(totalItems)} قلم کالا
                {isSyncing && (
                  <Loader2 className="h-3 w-3 animate-spin text-muted-foreground/70" />
                )}
              </span>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-8 w-8 rounded-xl"
            aria-label="بستن سبد خرید"
            autoFocus
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Free Shipping Progress Indicator */}
        {items.length > 0 && (
          <div className="border-b border-border bg-primary/5 p-4">
            {summary.freeShippingEligible ? (
              <div className="flex items-center gap-2 text-xs font-bold text-success">
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
                  <span className="text-muted-foreground text-[11px]">
                    {toPersianDigits(
                      Math.round((summary.subtotal / 5000000) * 100),
                    )}
                    ٪
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(100, Math.round((summary.subtotal / 5000000) * 100))}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Error state — sync/refetch failed */}
        {error && !isLoading && (
          <div className="mx-4 mt-4 flex items-center justify-between gap-2 rounded-xl border border-destructive/25 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive">
            <span className="flex items-center gap-1.5 font-semibold">
              <AlertCircle className="h-4 w-4 shrink-0" />
              همگام‌سازی سبد با سرور ممکن نشد.
            </span>
            <button
              type="button"
              onClick={() => fetchCart()}
              className="flex items-center gap-1 font-bold underline underline-offset-4"
            >
              <RotateCcw className="h-3 w-3" />
              تلاش مجدد
            </button>
          </div>
        )}

        {/* Cart Items List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 divide-y divide-border/40">
          {/* Loading skeleton (first paint before any item arrives) */}
          {isLoading && items.length === 0 ? (
            <div className="space-y-5 py-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="flex gap-3">
                  <Skeleton className="h-20 w-20 rounded-xl" />
                  <div className="flex-1 space-y-2 pt-1">
                    <Skeleton className="h-3.5 w-4/5" />
                    <Skeleton className="h-3 w-2/5" />
                    <Skeleton className="h-6 w-24 rounded-lg mt-3" />
                  </div>
                </div>
              ))}
            </div>
          ) : items.length === 0 ? (
            /* Empty Cart */
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
              <div className="flex items-center gap-2">
                <Link href="/products" onClick={onClose}>
                  <Button size="sm" className="rounded-xl px-5 font-bold">
                    مشاهده کاتالوگ محصولات
                  </Button>
                </Link>
                <Link href="/products?sale=true" onClick={onClose}>
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-xl px-4 font-bold border-border"
                  >
                    تخفیف‌های ویژه
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            items.map((item) => (
              <CartLineItem
                key={item.variantId || item.productId}
                item={item}
                onUpdateQuantity={updateItemQuantity}
                onRemove={removeFromCart}
                onClose={onClose}
              />
            ))
          )}
        </div>

        {/* Coupon + Order Summary + Checkout CTA */}
        {items.length > 0 && (
          <div className="border-t border-border bg-card p-5 space-y-4 shadow-lg">
            {/* Coupon */}
            {couponCode ? (
              <div className="flex items-center justify-between rounded-xl border border-success/25 bg-success/10 px-3 py-2.5">
                <span className="flex items-center gap-2 text-xs font-bold text-success">
                  <TicketPercent className="h-4 w-4" />
                  کد «{couponCode}» اعمال شد
                  {couponDiscount > 0 && (
                    <span>− {formatPrice(couponDiscount)}</span>
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    removeCoupon();
                    setCouponError(null);
                  }}
                  className="text-success/80 hover:text-destructive transition-colors"
                  aria-label="حذف کد تخفیف"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <div>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <TicketPercent className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={couponInput}
                      onChange={(e) => {
                        setCouponInput(e.target.value);
                        if (couponError) setCouponError(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          handleApplyCoupon();
                        }
                      }}
                      placeholder="کد تخفیف دارید؟"
                      className="h-9 rounded-xl pr-9 text-xs"
                      aria-label="کد تخفیف"
                    />
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleApplyCoupon}
                    disabled={couponPending || !couponInput.trim()}
                    className="h-9 rounded-xl px-4 text-xs font-bold border-border gap-1.5"
                  >
                    {couponPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      "اعمال"
                    )}
                  </Button>
                </div>
                {couponError && (
                  <p className="mt-1.5 text-[11px] font-medium text-destructive flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" />
                    {couponError}
                  </p>
                )}
              </div>
            )}

            {/* Order Summary */}
            <div className="space-y-1.5 text-xs">
              <div className="flex items-center justify-between text-muted-foreground">
                <span>جمع کالاها ({toPersianDigits(summary.itemCount)} قلم)</span>
                <span className="font-semibold text-foreground">
                  {formatPrice(summary.subtotal)}
                </span>
              </div>
              {summary.discount > 0 && (
                <div className="flex items-center justify-between text-success font-semibold">
                  <span>تخفیف کوپن</span>
                  <span>− {formatPrice(summary.discount)}</span>
                </div>
              )}
              <div className="flex items-center justify-between text-muted-foreground">
                <span>هزینه ارسال</span>
                {summary.shipping === 0 ? (
                  <span className="font-bold text-success">رایگان</span>
                ) : (
                  <span className="font-semibold text-foreground">
                    {formatPrice(summary.shipping)}
                  </span>
                )}
              </div>
              <div className="flex items-center justify-between border-t border-border pt-2.5 mt-2">
                <span className="text-sm font-bold text-foreground">
                  مبلغ قابل پرداخت:
                </span>
                <span className="text-base font-black text-primary">
                  {formatPrice(summary.total)}
                  <span className="ms-1 text-[10px] font-medium text-muted-foreground">
                    تومان
                  </span>
                </span>
              </div>
            </div>

            {/* Checkout CTAs */}
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
