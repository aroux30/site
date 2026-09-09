"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  Minus,
  Plus,
  Trash2,
  ShoppingBag,
  ArrowLeft,
  ArrowRight,
  Tag,
  ShieldCheck,
  Truck,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useCart } from "@/hooks/use-cart";
import { useAuthStore } from "@/stores/auth-store";
import { formatPrice, toPersianDigits, formatNumber } from "@/lib/utils";

export default function CartPage() {
  const router = useRouter();
  const {
    items,
    totalItems,
    subtotal,
    couponCode,
    couponDiscount,
    totalDiscount,
    isSyncing,
    updateItemQuantity,
    removeFromCart,
    clearCart,
    applyCoupon,
    removeCoupon,
    getCartSummary,
  } = useCart();

  const { isAuthenticated } = useAuthStore();

  const [inputCoupon, setInputCoupon] = useState("");
  const [couponLoading, setCouponLoading] = useState(false);
  const [couponMessage, setCouponMessage] = useState<{
    text: string;
    type: "success" | "error";
  } | null>(null);

  const summary = getCartSummary();

  const handleApplyCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputCoupon.trim()) return;

    setCouponLoading(true);
    setCouponMessage(null);

    const res = await applyCoupon(inputCoupon);
    setCouponLoading(false);

    if (res.success) {
      setCouponMessage({ text: res.message, type: "success" });
      setInputCoupon("");
    } else {
      setCouponMessage({ text: res.message, type: "error" });
    }
  };

  const handleRemoveCoupon = async () => {
    await removeCoupon();
    setCouponMessage(null);
  };

  const handleProceedToCheckout = () => {
    if (isAuthenticated) {
      router.push("/checkout");
    } else {
      router.push("/login?redirect=/checkout");
    }
  };

  if (items.length === 0) {
    return (
      <div className="container-page py-12">
        <div className="mx-auto max-w-2xl rounded-2xl border border-border bg-card p-8 text-center shadow-sm">
          <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-primary/10 text-primary">
            <ShoppingBag className="h-12 w-12" />
          </div>
          <h1 className="mb-3 text-2xl font-bold text-foreground">
            سبد خرید شما خالی است
          </h1>
          <p className="mb-8 text-muted-foreground leading-relaxed">
            محصولات مورد علاقه خود را انتخاب کنید و به سبد خرید اضافه نمایید تا در این بخش نمایش داده شوند.
          </p>
          <Link href="/products">
            <Button size="lg" className="gap-2 px-8">
              <span>شروع خرید و مشاهده محصولات</span>
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>

          {/* Guarantees */}
          <div className="mt-12 grid grid-cols-1 gap-4 border-t border-border pt-8 sm:grid-cols-3">
            <div className="flex flex-col items-center gap-2 text-center">
              <Truck className="h-6 w-6 text-primary" />
              <span className="text-sm font-medium text-foreground">ارسال سریع و مطمئن</span>
              <span className="text-xs text-muted-foreground">تحویل به سراسر کشور</span>
            </div>
            <div className="flex flex-col items-center gap-2 text-center">
              <ShieldCheck className="h-6 w-6 text-primary" />
              <span className="text-sm font-medium text-foreground">ضمانت اصالت کالا</span>
              <span className="text-xs text-muted-foreground">۱۰۰٪ کالای اصل و اورجینال</span>
            </div>
            <div className="flex flex-col items-center gap-2 text-center">
              <RotateCcw className="h-6 w-6 text-primary" />
              <span className="text-sm font-medium text-foreground">۷ روز ضمانت بازگشت</span>
              <span className="text-xs text-muted-foreground">بازگشت آسان و بدون قید و شرط</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page py-8">
      {/* Breadcrumb & Header */}
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Link href="/" className="hover:text-primary transition-colors">
              صفحه اصلی
            </Link>
            <span>/</span>
            <span className="text-foreground font-medium">سبد خرید</span>
          </div>
          <h1 className="text-2xl font-extrabold text-foreground flex items-center gap-3">
            <span>سبد خرید</span>
            <Badge variant="secondary" className="text-xs px-2.5 py-0.5">
              {toPersianDigits(totalItems)} کالا
            </Badge>
            {isSyncing && (
              <span className="flex items-center gap-1.5 text-xs font-normal text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin text-primary" />
                در حال به‌روزرسانی...
              </span>
            )}
          </h1>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => clearCart()}
          className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 self-start sm:self-auto gap-1 text-xs"
        >
          <Trash2 className="h-3.5 w-3.5" />
          <span>خالی کردن سبد خرید</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Cart Items List */}
        <div className="lg:col-span-2 space-y-4">
          {items.map((item) => {
            const lineKey = item.id || item.variantId || item.productId;
            const lineTotal = item.price * item.quantity;
            const hasDiscount =
              item.originalPrice && item.originalPrice > item.price;
            const discountPercent = hasDiscount
              ? Math.round(
                  ((item.originalPrice! - item.price) / item.originalPrice!) * 100,
                )
              : 0;

            return (
              <Card
                key={lineKey}
                className="overflow-hidden border-border/80 p-4 sm:p-5 transition-shadow hover:shadow-sm"
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                  {/* Item Image */}
                  <div className="relative h-24 w-24 flex-shrink-0 self-center sm:self-start overflow-hidden rounded-xl border border-border bg-muted/30">
                    {item.image ? (
                      <Image
                        src={item.image}
                        alt={item.title}
                        fill
                        sizes="96px"
                        className="object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-3xl text-muted-foreground/60">
                        <ShoppingBag className="h-8 w-8 text-muted-foreground" />
                      </div>
                    )}
                  </div>

                  {/* Item Info */}
                  <div className="flex flex-1 flex-col justify-between gap-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <Link
                          href={item.slug ? `/products/${item.slug}` : "#"}
                          className="font-semibold text-foreground hover:text-primary transition-colors line-clamp-2"
                        >
                          {item.title}
                        </Link>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          {item.variant && (
                            <Badge variant="outline" className="text-xs bg-muted/40 font-normal">
                              {item.variant}
                            </Badge>
                          )}
                          {item.sku && (
                            <span className="text-xs text-muted-foreground">
                              کد: <span dir="ltr">{item.sku}</span>
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Remove Button */}
                      <button
                        onClick={() => removeFromCart(lineKey)}
                        className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        title="حذف از سبد"
                        aria-label="حذف از سبد"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>

                    {/* Price and Quantity Controls */}
                    <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-border/50">
                      {/* Quantity Stepper */}
                      <div className="flex items-center rounded-lg border border-border bg-background p-1 shadow-sm">
                        <button
                          type="button"
                          onClick={() =>
                            updateItemQuantity(lineKey, item.quantity + 1)
                          }
                          disabled={
                            item.maxQuantity
                              ? item.quantity >= item.maxQuantity
                              : false
                          }
                          className="flex h-7 w-7 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted active:scale-95 disabled:opacity-40"
                          aria-label="افزایش تعداد"
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </button>

                        <span className="w-9 text-center text-sm font-bold text-foreground">
                          {toPersianDigits(item.quantity)}
                        </span>

                        <button
                          type="button"
                          onClick={() =>
                            updateItemQuantity(lineKey, item.quantity - 1)
                          }
                          className="flex h-7 w-7 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted active:scale-95 text-destructive"
                          aria-label="کاهش تعداد"
                        >
                          {item.quantity === 1 ? (
                            <Trash2 className="h-3.5 w-3.5" />
                          ) : (
                            <Minus className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>

                      {/* Price breakdown */}
                      <div className="text-left">
                        {hasDiscount && (
                          <div className="flex items-center gap-1.5 justify-end">
                            <span className="text-xs text-muted-foreground line-through">
                              {formatNumber(item.originalPrice! * item.quantity)}
                            </span>
                            <span className="rounded bg-destructive/10 px-1 py-0.5 text-[10px] font-bold text-destructive">
                              {toPersianDigits(discountPercent)}٪-
                            </span>
                          </div>
                        )}
                        <div className="text-base font-bold text-foreground">
                          {formatPrice(lineTotal)}
                        </div>
                        {item.quantity > 1 && (
                          <div className="text-[11px] text-muted-foreground text-left">
                            هر واحد: {formatPrice(item.price)}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}

          {/* Continue Shopping Link */}
          <div className="pt-2">
            <Link
              href="/products"
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <ArrowRight className="h-4 w-4" />
              <span>افزودن محصولات بیشتر به سبد خرید</span>
            </Link>
          </div>
        </div>

        {/* Order Summary Sidebar */}
        <div className="space-y-4">
          <Card className="sticky top-24 p-6 shadow-sm border-border">
            <h2 className="mb-4 text-lg font-bold text-foreground">خلاصه سفارش</h2>

            {/* Free Shipping Notification */}
            <div className="mb-5 rounded-xl border border-primary/20 bg-primary/5 p-3 text-xs leading-relaxed">
              {summary.freeShippingEligible ? (
                <div className="flex items-center gap-2 text-primary font-medium">
                  <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                  <span>ارسال سفارش شما رایگان محاسبه خواهد شد!</span>
                </div>
              ) : (
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center gap-1.5 text-foreground font-medium">
                    <Truck className="h-4 w-4 text-primary flex-shrink-0" />
                    <span>
                      با خرید{" "}
                      <span className="font-bold text-primary">
                        {formatPrice(summary.freeShippingRemaining)}
                      </span>{" "}
                      دیگر، ارسال سفارش شما رایگان می‌شود!
                    </span>
                  </div>
                  {/* Progress Bar */}
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
                    <div
                      className="h-full bg-primary transition-all duration-500"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.round((subtotal / 5000000) * 100),
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Price Calculations */}
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between text-muted-foreground">
                <span>قیمت کالاها ({toPersianDigits(totalItems)})</span>
                <span className="font-medium text-foreground">
                  {formatPrice(subtotal)}
                </span>
              </div>

              {totalDiscount > 0 && (
                <div className="flex items-center justify-between text-destructive">
                  <span>سود شما از خرید</span>
                  <span className="font-medium">
                    {formatPrice(totalDiscount)} -
                  </span>
                </div>
              )}

              {couponDiscount > 0 && (
                <div className="flex items-center justify-between text-emerald-600 dark:text-emerald-400">
                  <span>تخفیف کد هدیه</span>
                  <span className="font-medium">
                    {formatPrice(couponDiscount)} -
                  </span>
                </div>
              )}

              <div className="flex items-center justify-between text-muted-foreground">
                <span>هزینه تخمینی ارسال</span>
                {summary.shipping === 0 ? (
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                    رایگان
                  </span>
                ) : (
                  <span className="font-medium text-foreground">
                    {formatPrice(summary.shipping)}
                  </span>
                )}
              </div>

              <div className="my-3 border-t border-border pt-3">
                <div className="flex items-center justify-between text-base font-extrabold text-foreground">
                  <span>مبلغ قابل پرداخت</span>
                  <span className="text-primary text-lg">
                    {formatPrice(summary.total)}
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground text-left">
                  هزینه نهایی ارسال در مرحله بعد محاسبه خواهد شد.
                </p>
              </div>
            </div>

            {/* Coupon Code Section */}
            <div className="mt-5 border-t border-border pt-4">
              <label className="mb-2 block text-xs font-semibold text-foreground">
                کد تخفیف دارید؟
              </label>

              {couponCode ? (
                <div className="flex items-center justify-between rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-2.5 text-xs text-emerald-700 dark:text-emerald-300">
                  <div className="flex items-center gap-1.5">
                    <Tag className="h-3.5 w-3.5" />
                    <span>کد اعمال شده: </span>
                    <strong className="font-mono tracking-wider">{couponCode}</strong>
                  </div>
                  <button
                    type="button"
                    onClick={handleRemoveCoupon}
                    className="rounded p-1 hover:bg-emerald-500/20 text-muted-foreground hover:text-foreground"
                    title="حذف کد تخفیف"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <form onSubmit={handleApplyCoupon} className="space-y-2">
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Tag className="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        type="text"
                        value={inputCoupon}
                        onChange={(e) => setInputCoupon(e.target.value)}
                        placeholder="کد تخفیف خود را وارد کنید"
                        className="pr-8 text-xs font-mono"
                        dir="ltr"
                      />
                    </div>
                    <Button
                      type="submit"
                      variant="outline"
                      size="sm"
                      disabled={couponLoading || !inputCoupon.trim()}
                      className="px-4 text-xs font-medium"
                    >
                      {couponLoading ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        "اعمال"
                      )}
                    </Button>
                  </div>
                  {couponMessage && (
                    <div
                      className={`flex items-center gap-1.5 text-xs ${
                        couponMessage.type === "success"
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-destructive"
                      }`}
                    >
                      {couponMessage.type === "success" ? (
                        <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0" />
                      ) : (
                        <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                      )}
                      <span>{couponMessage.text}</span>
                    </div>
                  )}
                </form>
              )}
            </div>

            {/* Checkout Button */}
            <div className="mt-6">
              <Button
                onClick={handleProceedToCheckout}
                className="w-full gap-2 text-base font-bold shadow-md hover:shadow-lg"
                size="lg"
              >
                <span>ادامه فرآیند خرید</span>
                <ArrowLeft className="h-4 w-4" />
              </Button>
              {!isAuthenticated && (
                <p className="mt-2 text-center text-[11px] text-muted-foreground">
                  جهت ثبت سفارش، در مرحله بعد وارد حساب کاربری خود می‌شوید.
                </p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
