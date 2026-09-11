"use client";

import React, { useState, useEffect, useTransition, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  User,
  Smartphone,
  Eye,
  EyeOff,
  ArrowRight,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/components/ui/use-toast";
import { isValidIranPhone, normalizeIranPhone } from "@/lib/utils";

interface FormErrors {
  firstName?: string;
  lastName?: string;
  phone?: string;
  password?: string;
  confirmPassword?: string;
  terms?: string;
  general?: string;
}

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { register, isAuthenticated, isLoading: isAuthLoading, user } = useAuth();

  const redirectUrl = searchParams.get("redirect") || "/account";

  // Form Fields State
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);

  // UI state
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  const [, startTransition] = useTransition();

  // If already authenticated with confirmed user profile, redirect only if authorized for target
  useEffect(() => {
    if (isAuthenticated && !isAuthLoading && user) {
      const isTargetAdmin = redirectUrl.startsWith("/admin");
      const isAdmin = Boolean(
        user.is_superuser ||
          user.role === "admin" ||
          user.roles?.includes("super_admin") ||
          user.roles?.includes("admin") ||
          user.permissions?.includes("*")
      );

      // Do not auto-redirect to admin if current user is not an admin
      if (isTargetAdmin && !isAdmin) {
        return;
      }

      router.replace(redirectUrl);
    }
  }, [isAuthenticated, isAuthLoading, user, redirectUrl, router]);

  // Validation function
  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    const cleanFirstName = firstName.trim();
    if (!cleanFirstName) {
      newErrors.firstName = "نام خود را وارد کنید.";
    } else if (cleanFirstName.length < 2) {
      newErrors.firstName = "نام باید حداقل ۲ حرف باشد.";
    }

    const cleanLastName = lastName.trim();
    if (!cleanLastName) {
      newErrors.lastName = "نام خانوادگی خود را وارد کنید.";
    } else if (cleanLastName.length < 2) {
      newErrors.lastName = "نام خانوادگی باید حداقل ۲ حرف باشد.";
    }

    const cleanPhone = normalizeIranPhone(phone);
    if (!cleanPhone) {
      newErrors.phone = "شماره موبایل را وارد کنید.";
    } else if (!isValidIranPhone(cleanPhone)) {
      newErrors.phone = "شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود (مثال: ۰۹۱۲۳۴۵۶۷۸۹).";
    }

    if (!password) {
      newErrors.password = "رمز عبور را وارد کنید.";
    } else if (password.length < 8) {
      newErrors.password = "رمز عبور باید حداقل ۸ کاراکتر باشد.";
    } else if (!/[A-Za-z]/.test(password)) {
      newErrors.password = "رمز عبور باید حداقل شامل یک حرف انگلیسی باشد.";
    } else if (!/\d/.test(password)) {
      newErrors.password = "رمز عبور باید حداقل شامل یک عدد باشد.";
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = "تکرار رمز عبور را وارد کنید.";
    } else if (password !== confirmPassword) {
      newErrors.confirmPassword = "تکرار رمز عبور با رمز عبور مطابقت ندارد.";
    }

    if (!termsAccepted) {
      newErrors.terms = "پذیرش قوانین و مقررات سایت الزامی است.";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    if (!validate()) {
      return;
    }

    setIsSubmitting(true);
    const cleanPhone = normalizeIranPhone(phone);

    try {
      await register({
        phone: cleanPhone,
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      });

      toast({
        title: "ثبت‌نام موفق",
        description: "حساب کاربری شما با موفقیت ایجاد و وارد شدید.",
        variant: "success",
      });

      startTransition(() => {
        router.push(redirectUrl);
        router.refresh();
      });
    } catch (err: unknown) {
      const errorMsg =
        (err as { response?: { data?: { error?: { message?: string } } }; message?: string })?.response?.data?.error?.message ||
        (err as { message?: string })?.message ||
        "خطایی در ایجاد حساب کاربری رخ داد. لطفاً دوباره تلاش کنید.";
      setErrors({ general: errorMsg });
      toast({
        title: "خطا در ثبت‌نام",
        description: errorMsg,
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const clearFieldError = (field: keyof FormErrors) => {
    if (errors[field] || errors.general) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        delete next.general;
        return next;
      });
    }
  };

  return (
    <div className="container mx-auto flex min-h-[calc(100vh-140px)] items-center justify-center px-4 py-12" dir="rtl">
      <div className="w-full max-w-lg">
        {/* Brand & Back Link */}
        <div className="mb-6 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-primary"
          >
            <ArrowRight className="h-4 w-4" />
            <span>بازگشت به صفحه اصلی</span>
          </Link>
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-base font-black text-primary-foreground shadow-sm">
              ف
            </div>
            <span className="text-base font-bold text-foreground">فروشگاه آنلاین</span>
          </Link>
        </div>

        <Card className="border-border/60 shadow-lg">
          <CardHeader className="space-y-1 text-center">
            <CardTitle className="text-2xl font-bold tracking-tight">ایجاد حساب کاربری</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              برای تکمیل خرید و پیگیری سفارش‌ها اطلاعات خود را وارد کنید
            </CardDescription>
          </CardHeader>

          <CardContent className="pt-2">
            {errors.general && (
              <div className="mb-4 flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <p>{errors.general}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Names: 2 Columns */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {/* First Name */}
                <div className="space-y-1.5">
                  <Label htmlFor="first-name-input" className="text-xs font-medium">
                    نام <span className="text-destructive">*</span>
                  </Label>
                  <div className="relative">
                    <Input
                      id="first-name-input"
                      type="text"
                      placeholder="علی"
                      value={firstName}
                      onChange={(e) => {
                        setFirstName(e.target.value);
                        clearFieldError("firstName");
                      }}
                      autoComplete="given-name"
                      className={`pr-9 ${errors.firstName ? "border-destructive focus-visible:ring-destructive" : ""}`}
                      disabled={isSubmitting}
                    />
                    <User className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  </div>
                  {errors.firstName && (
                    <p className="text-[11px] text-destructive">{errors.firstName}</p>
                  )}
                </div>

                {/* Last Name */}
                <div className="space-y-1.5">
                  <Label htmlFor="last-name-input" className="text-xs font-medium">
                    نام خانوادگی <span className="text-destructive">*</span>
                  </Label>
                  <div className="relative">
                    <Input
                      id="last-name-input"
                      type="text"
                      placeholder="محمدی"
                      value={lastName}
                      onChange={(e) => {
                        setLastName(e.target.value);
                        clearFieldError("lastName");
                      }}
                      autoComplete="family-name"
                      className={`pr-9 ${errors.lastName ? "border-destructive focus-visible:ring-destructive" : ""}`}
                      disabled={isSubmitting}
                    />
                    <User className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  </div>
                  {errors.lastName && (
                    <p className="text-[11px] text-destructive">{errors.lastName}</p>
                  )}
                </div>
              </div>

              {/* Iranian Mobile Number */}
              <div className="space-y-1.5">
                <Label htmlFor="register-phone-input" className="text-xs font-medium">
                  شماره موبایل <span className="text-destructive">*</span>
                </Label>
                <div className="relative">
                  <Input
                    id="register-phone-input"
                    type="tel"
                    dir="ltr"
                    placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                    value={phone}
                    onChange={(e) => {
                      setPhone(e.target.value);
                      clearFieldError("phone");
                    }}
                    autoComplete="tel"
                    className={`pl-10 text-left font-mono tracking-wider ${
                      errors.phone ? "border-destructive focus-visible:ring-destructive" : ""
                    }`}
                    disabled={isSubmitting}
                  />
                  <Smartphone className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                </div>
                {errors.phone ? (
                  <p className="text-[11px] text-destructive">{errors.phone}</p>
                ) : (
                  <p className="text-[11px] text-muted-foreground">
                    شماره ۱۱ رقمی همراه با ۰۹ (مثال: ۰۹۱۲۳۴۵۶۷۸۹)
                  </p>
                )}
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <Label htmlFor="register-password-input" className="text-xs font-medium">
                  رمز عبور <span className="text-destructive">*</span>
                </Label>
                <div className="relative">
                  <Input
                    id="register-password-input"
                    type={showPassword ? "text" : "password"}
                    placeholder="حداقل ۸ کاراکتر شامل حرف و عدد"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      clearFieldError("password");
                    }}
                    autoComplete="new-password"
                    className={`pl-10 text-left font-mono ${
                      errors.password ? "border-destructive focus-visible:ring-destructive" : ""
                    }`}
                    disabled={isSubmitting}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                    aria-label={showPassword ? "مخفی کردن رمز" : "نمایش رمز"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password ? (
                  <p className="text-[11px] text-destructive">{errors.password}</p>
                ) : (
                  <p className="text-[11px] text-muted-foreground">
                    حداقل ۸ کاراکتر، شامل حداقل یک حرف انگلیسی و یک عدد
                  </p>
                )}
              </div>

              {/* Confirm Password */}
              <div className="space-y-1.5">
                <Label htmlFor="register-confirm-password-input" className="text-xs font-medium">
                  تکرار رمز عبور <span className="text-destructive">*</span>
                </Label>
                <div className="relative">
                  <Input
                    id="register-confirm-password-input"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="تکرار رمز عبور"
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value);
                      clearFieldError("confirmPassword");
                    }}
                    autoComplete="new-password"
                    className={`pl-10 text-left font-mono ${
                      errors.confirmPassword ? "border-destructive focus-visible:ring-destructive" : ""
                    }`}
                    disabled={isSubmitting}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                    aria-label={showConfirmPassword ? "مخفی کردن رمز" : "نمایش رمز"}
                  >
                    {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="text-[11px] text-destructive">{errors.confirmPassword}</p>
                )}
              </div>

              {/* Terms & Conditions Checkbox */}
              <div className="pt-1">
                <div className="flex items-start gap-2.5">
                  <Checkbox
                    id="terms"
                    checked={termsAccepted}
                    onCheckedChange={(checked) => {
                      setTermsAccepted(!!checked);
                      clearFieldError("terms");
                    }}
                    disabled={isSubmitting}
                    className="mt-0.5"
                  />
                  <Label
                    htmlFor="terms"
                    className="text-xs leading-relaxed text-muted-foreground cursor-pointer"
                  >
                    با ثبت‌نام در سایت،{" "}
                    <span className="text-primary hover:underline">
                      قوانین و مقررات استفاده از خدمات
                    </span>{" "}
                    و{" "}
                    <span className="text-primary hover:underline">
                      حریم خصوصی
                    </span>{" "}
                    فروشگاه آنلاین را مطالعه کرده و می‌پذیرم.
                  </Label>
                </div>
                {errors.terms && (
                  <p className="mt-1.5 text-[11px] text-destructive">{errors.terms}</p>
                )}
              </div>

              {/* Submit Button */}
              <Button
                type="submit"
                className="w-full font-medium"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                    <span>در حال ایجاد حساب...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="ml-2 h-4 w-4" />
                    <span>ثبت‌نام و ورود به حساب</span>
                  </>
                )}
              </Button>
            </form>
          </CardContent>

          <CardFooter className="flex flex-col gap-3 border-t border-border/40 pt-4 text-center text-xs">
            <p className="text-muted-foreground">
              قبلاً در فروشگاه ثبت‌نام کرده‌اید؟{" "}
              <Link
                href={`/login${searchParams.get("redirect") ? `?redirect=${encodeURIComponent(searchParams.get("redirect")!)}` : ""}`}
                className="font-semibold text-primary hover:underline"
              >
                ورود به حساب کاربری
              </Link>
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-140px)] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <RegisterForm />
    </Suspense>
  );
}
