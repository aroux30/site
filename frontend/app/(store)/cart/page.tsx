"use client";

import Link from "next/link";
import { Minus, Plus, Trash2, ShoppingBag } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useCartStore } from "@/stores/cart-store";
import { formatPrice } from "@/lib/utils";

export default function CartPage() {
  const { items, removeItem, updateQuantity, totalPrice, totalItems } =
    useCartStore();

  if (items.length === 0) {
    return (
      <div className="container-page">
        <div className="flex flex-col items-center justify-center py-20">
          <ShoppingBag className="mb-4 h-16 w-16 text-muted-foreground" />
          <h1 className="mb-2 text-2xl font-bold text-foreground">
            سبد خرید شما خالی است
          </h1>
          <p className="mb-6 text-muted-foreground">
            محصولات مورد نظر خود را به سبد خرید اضافه کنید.
          </p>
          <Link href="/products">
            <Button>مشاهده محصولات</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page">
      <h1 className="mb-8 text-2xl font-bold text-foreground">سبد خرید</h1>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Cart Items */}
        <div className="lg:col-span-2">
          <div className="space-y-4">
            {items.map((item) => (
              <Card key={item.productId} className="p-4">
                <div className="flex gap-4">
                  <div className="h-24 w-24 flex-shrink-0 rounded-lg bg-muted">
                    <div className="flex h-full items-center justify-center text-2xl text-muted-foreground">
                      📦
                    </div>
                  </div>
                  <div className="flex flex-1 flex-col justify-between">
                    <div>
                      <h3 className="font-medium text-foreground">
                        {item.title}
                      </h3>
                      {item.variant && (
                        <p className="text-sm text-muted-foreground">
                          {item.variant}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() =>
                            updateQuantity(
                              item.productId,
                              Math.max(0, item.quantity - 1),
                            )
                          }
                          className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-foreground hover:bg-muted"
                        >
                          <Minus className="h-3 w-3" />
                        </button>
                        <span className="w-8 text-center text-sm font-medium">
                          {item.quantity}
                        </span>
                        <button
                          onClick={() =>
                            updateQuantity(item.productId, item.quantity + 1)
                          }
                          className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-foreground hover:bg-muted"
                        >
                          <Plus className="h-3 w-3" />
                        </button>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="font-bold text-foreground">
                          {formatPrice(item.price * item.quantity)}
                        </span>
                        <button
                          onClick={() => removeItem(item.productId)}
                          className="text-destructive hover:text-destructive/80"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Order Summary */}
        <div>
          <Card className="sticky top-24 p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">
              خلاصه سفارش
            </h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  تعداد اقلام ({totalItems})
                </span>
                <span className="text-foreground">
                  {formatPrice(totalPrice)}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">هزینه ارسال</span>
                <span className="text-primary">رایگان</span>
              </div>
              <hr className="border-border" />
              <div className="flex items-center justify-between font-semibold">
                <span className="text-foreground">مبلغ قابل پرداخت</span>
                <span className="text-primary">
                  {formatPrice(totalPrice)}
                </span>
              </div>
            </div>
            <Link href="/checkout" className="mt-6 block">
              <Button className="w-full" size="lg">
                ادامه فرآیند خرید
              </Button>
            </Link>
          </Card>
        </div>
      </div>
    </div>
  );
}
