"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useCartStore } from "@/stores/cart-store";
import { formatPrice } from "@/lib/utils";

const checkoutSchema = z.object({
  firstName: z.string().min(2, "نام باید حداقل ۲ حرف باشد"),
  lastName: z.string().min(2, "نام خانوادگی باید حداقل ۲ حرف باشد"),
  phone: z
    .string()
    .regex(/^09\d{9}$/, "شماره موبایل معتبر وارد کنید (مثال: 09123456789)"),
  email: z.string().email("ایمیل معتبر وارد کنید").optional().or(z.literal("")),
  province: z.string().min(1, "استان را انتخاب کنید"),
  city: z.string().min(1, "شهر را وارد کنید"),
  address: z.string().min(10, "آدرس باید حداقل ۱۰ حرف باشد"),
  postalCode: z
    .string()
    .regex(/^\d{10}$/, "کد پستی باید ۱۰ رقمی باشد"),
  note: z.string().optional(),
});

type CheckoutFormData = z.infer<typeof checkoutSchema>;

type CheckoutStep = "shipping" | "payment" | "confirmation";

const steps: { key: CheckoutStep; label: string }[] = [
  { key: "shipping", label: "اطلاعات ارسال" },
  { key: "payment", label: "پرداخت" },
  { key: "confirmation", label: "تأیید سفارش" },
];

export default function CheckoutPage() {
  const [currentStep, setCurrentStep] = useState<CheckoutStep>("shipping");
  const { items, totalPrice, totalItems } = useCartStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CheckoutFormData>({
    resolver: zodResolver(checkoutSchema),
  });

  const onSubmit = (data: CheckoutFormData) => {
    if (currentStep === "shipping") {
      setCurrentStep("payment");
    } else if (currentStep === "payment") {
      setCurrentStep("confirmation");
    }
    // In production, send to API
    console.log("Checkout data:", data);
  };

  return (
    <div className="container-page">
      <h1 className="mb-8 text-2xl font-bold text-foreground">
        تکمیل سفارش
      </h1>

      {/* Steps Indicator */}
      <div className="mb-8">
        <div className="flex items-center justify-center gap-4">
          {steps.map((step, index) => (
            <div key={step.key} className="flex items-center gap-2">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                  step.key === currentStep
                    ? "bg-primary text-primary-foreground"
                    : steps.indexOf(
                          steps.find((s) => s.key === currentStep)!,
                        ) > index
                      ? "bg-primary/20 text-primary"
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {index + 1}
              </div>
              <span
                className={`text-sm ${
                  step.key === currentStep
                    ? "font-medium text-foreground"
                    : "text-muted-foreground"
                }`}
              >
                {step.label}
              </span>
              {index < steps.length - 1 && (
                <div className="mx-2 h-px w-12 bg-border" />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Form Section */}
        <div className="lg:col-span-2">
          {currentStep === "shipping" && (
            <Card className="p-6">
              <h2 className="mb-6 text-lg font-semibold text-foreground">
                اطلاعات گیرنده و آدرس ارسال
              </h2>
              <form
                onSubmit={handleSubmit(onSubmit)}
                className="space-y-4"
              >
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-foreground">
                      نام
                    </label>
                    <Input
                      {...register("firstName")}
                      placeholder="نام خود را وارد کنید"
                    />
                    {errors.firstName && (
                      <p className="mt-1 text-xs text-destructive">
                        {errors.firstName.message}
                      </p>
                    )}
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-foreground">
                      نام خانوادگی
                    </label>
                    <Input
                      {...register("lastName")}
                      placeholder="نام خانوادگی خود را وارد کنید"
                    />
                    {errors.lastName && (
                      <p className="mt-1 text-xs text-destructive">
                        {errors.lastName.message}
                      </p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-foreground">
                      شماره موبایل
                    </label>
                    <Input
                      {...register("phone")}
                      placeholder="09123456789"
                      dir="ltr"
                      className="text-left"
                    />
                    {errors.phone && (
                      <p className="mt-1 text-xs text-destructive">
                        {errors.phone.message}
                      </p>
                    )}
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-foreground">
                      ایمیل (اختیاری)
                    </label>
                    <Input
                      {...register("email")}
                      type="email"
                      placeholder="email@example.com"
                      dir="ltr"
                      className="text-left"
                    />
                    {errors.email && (
                      <p className="mt-1 text-xs text-destructive">
                        {errors.email.message}
                      </p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-foreground">
                      استان
                    </label>
                    <Input
                      {...register("province")}
                      placeholder="استان را وارد کنید"
                    />
                    {errors.province && (
                      <p className="mt-1 text-xs text-destructive">
                        {errors.province.message}
                      </p>
                    )}
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-foreground">
                      شهر
                    </label>
                    <Input
                      {...register("city")}
                      placeholder="شهر را وارد کنید"
                    />
                    {errors.city && (
                      <p className="mt-1 text-xs text-destructive">
                        {errors.city.message}
                      </p>
                    )}
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    آدرس کامل
                  </label>
                  <textarea
                    {...register("address")}
                    rows={3}
                    placeholder="آدرس دقیق خود را وارد کنید..."
                    className="input-base w-full resize-none"
                  />
                  {errors.address && (
                    <p className="mt-1 text-xs text-destructive">
                      {errors.address.message}
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-foreground">
                      کد پستی
                    </label>
                    <Input
                      {...register("postalCode")}
                      placeholder="1234567890"
                      dir="ltr"
                      className="text-left"
                    />
                    {errors.postalCode && (
                      <p className="mt-1 text-xs text-destructive">
                        {errors.postalCode.message}
                      </p>
                    )}
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    توضیحات سفارش (اختیاری)
                  </label>
                  <textarea
                    {...register("note")}
                    rows={2}
                    placeholder="در صورت نیاز، توضیحات اضافی را وارد کنید..."
                    className="input-base w-full resize-none"
                  />
                </div>

                <Button type="submit" size="lg" className="w-full sm:w-auto">
                  ادامه و انتخاب روش پرداخت
                </Button>
              </form>
            </Card>
          )}

          {currentStep === "payment" && (
            <Card className="p-6">
              <h2 className="mb-6 text-lg font-semibold text-foreground">
                انتخاب روش پرداخت
              </h2>
              <div className="space-y-4">
                <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-primary bg-primary/5 p-4">
                  <input
                    type="radio"
                    name="payment"
                    defaultChecked
                    className="h-4 w-4 text-primary"
                  />
                  <div>
                    <p className="font-medium text-foreground">
                      پرداخت آنلاین
                    </p>
                    <p className="text-sm text-muted-foreground">
                      پرداخت از طریق درگاه بانکی
                    </p>
                  </div>
                </label>
                <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-border p-4 hover:border-primary/50">
                  <input
                    type="radio"
                    name="payment"
                    className="h-4 w-4 text-primary"
                  />
                  <div>
                    <p className="font-medium text-foreground">
                      پرداخت در محل
                    </p>
                    <p className="text-sm text-muted-foreground">
                      پرداخت هنگام تحویل کالا
                    </p>
                  </div>
                </label>
              </div>
              <div className="mt-6 flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => setCurrentStep("shipping")}
                >
                  بازگشت
                </Button>
                <Button onClick={() => setCurrentStep("confirmation")}>
                  تأیید و پرداخت
                </Button>
              </div>
            </Card>
          )}

          {currentStep === "confirmation" && (
            <Card className="p-6 text-center">
              <div className="mb-4 text-5xl">✅</div>
              <h2 className="mb-2 text-xl font-bold text-foreground">
                سفارش شما با موفقیت ثبت شد
              </h2>
              <p className="mb-6 text-muted-foreground">
                کد پیگیری سفارش: ORD-123456
              </p>
              <Button
                variant="outline"
                onClick={() => (window.location.href = "/products")}
              >
                ادامه خرید
              </Button>
            </Card>
          )}
        </div>

        {/* Order Summary Sidebar */}
        <div>
          <Card className="sticky top-24 p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">
              خلاصه سفارش
            </h2>
            <div className="space-y-3">
              {items.map((item) => (
                <div
                  key={item.productId}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-muted-foreground">
                    {item.title} × {item.quantity}
                  </span>
                  <span className="text-foreground">
                    {formatPrice(item.price * item.quantity)}
                  </span>
                </div>
              ))}
              <hr className="border-border" />
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  جمع ({totalItems} کالا)
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
                <span className="text-primary">{formatPrice(totalPrice)}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
