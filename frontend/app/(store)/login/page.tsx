"use client";

import React, { useState, useEffect, useCallback, useTransition, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Lock,
  Smartphone,
  Eye,
  EyeOff,
  ArrowRight,
  KeyRound,
  ShieldCheck,
  RotateCcw,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import {
  InputOTPItem,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp";
import { toEnglishDigits, toPersianDigits, isValidIranPhone } from "@/lib/utils";

const OTP_COUNTDOWN_SECONDS = 120;

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { login, requestOtp, verifyOtp, isAuthenticated, isLoading: isAuthLoading } = useAuth();

  const redirectUrl = searchParams.get("redirect") || "/account";

  // Tab State
  const [activeTab, setActiveTab] = useState<"password" | "otp">("password");

  // Password Login State
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isPasswordSubmitting, setIsPasswordSubmitting] = useState(false);

  // OTP Login State
  const [otpPhone, setOtpPhone] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpStep, setOtpStep] = useState<"phone" | "code">("phone");
  const [otpError, setOtpError] = useState<string | null>(null);
  const [isOtpSending, setIsOtpSending] = useState(false);
  const [isOtpVerifying, setIsOtpVerifying] = useState(false);
  const [countdown, setCountdown] = useState(0);

  const [, startTransition] = useTransition();

  // If already logged in, redirect
  useEffect(() => {
    if (isAuthenticated && !isAuthLoading) {
      router.replace(redirectUrl);
    }
  }, [isAuthenticated, isAuthLoading, redirectUrl, router]);

  // Countdown timer for OTP resend
  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setInterval(() => {
      setCountdown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  // Format seconds as mm:ss in Persian
  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    const formatted = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    return toPersianDigits(formatted);
  };

  // ── Password Login Handler ──────────────────────────────────────────────────
  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);

    const cleanPhone = toEnglishDigits(phone.trim());
    if (!cleanPhone) {
      setPasswordError("لطفاً شماره موبایل خود را وارد کنید.");
      return;
    }
    if (!isValidIranPhone(cleanPhone)) {
      setPasswordError("شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود (مثال: ۰۹۱۲۳۴۵۶۷۸۹).");
      return;
    }
    if (!password) {
      setPasswordError("لطفاً رمز عبور خود را وارد کنید.");
      return;
    }

    setIsPasswordSubmitting(true);
    try {
      await login({
        phone: cleanPhone,
        password,
      });

      toast({
        title: "ورود موفق",
        description: "به حساب کاربری خود خوش آمدید.",
        variant: "success",
      });

      startTransition(() => {
        router.push(redirectUrl);
        router.refresh();
      });
    } catch (err: unknown) {
      const errorMsg =
        (err as { message?: string })?.message ||
        "شماره موبایل یا رمز عبور اشتباه است.";
      setPasswordError(errorMsg);
      toast({
        title: "خطا در ورود",
        description: errorMsg,
        variant: "destructive",
      });
    } finally {
      setIsPasswordSubmitting(false);
    }
  };

  // ── OTP Request Handler ─────────────────────────────────────────────────────
  const handleSendOtp = useCallback(
    async (e?: React.FormEvent) => {
      if (e) e.preventDefault();
      setOtpError(null);

      const cleanPhone = toEnglishDigits(otpPhone.trim());
      if (!cleanPhone) {
        setOtpError("لطفاً شماره موبایل خود را وارد کنید.");
        return;
      }
      if (!isValidIranPhone(cleanPhone)) {
        setOtpError("شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود (مثال: ۰۹۱۲۳۴۵۶۷۸۹).");
        return;
      }

      setIsOtpSending(true);
      try {
        const res = await requestOtp({ phone: cleanPhone });
        setOtpStep("code");
        setCountdown(OTP_COUNTDOWN_SECONDS);
        setOtpCode("");

        toast({
          title: "کد تایید ارسال شد",
          description: res.message || `کد یکبار مصرف به شماره ${toPersianDigits(cleanPhone)} ارسال شد.`,
          variant: "success",
        });
      } catch (err: unknown) {
        const errorMsg =
          (err as { message?: string })?.message ||
          "خطا در ارسال کد تایید. لطفاً بعداً تلاش کنید.";
        setOtpError(errorMsg);
        toast({
          title: "خطا در ارسال پیامک",
          description: errorMsg,
          variant: "destructive",
        });
      } finally {
        setIsOtpSending(false);
      }
    },
    [otpPhone, requestOtp, toast],
  );

  // ── OTP Verify Handler ──────────────────────────────────────────────────────
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setOtpError(null);

    const cleanPhone = toEnglishDigits(otpPhone.trim());
    const cleanCode = toEnglishDigits(otpCode.trim());

    if (!cleanCode || cleanCode.length < 4) {
      setOtpError("لطفاً کد تایید را به درستی وارد کنید.");
      return;
    }

    setIsOtpVerifying(true);
    try {
      await verifyOtp({
        phone: cleanPhone,
        code: cleanCode,
      });

      toast({
        title: "ورود موفق",
        description: "به حساب کاربری خود خوش آمدید.",
        variant: "success",
      });

      startTransition(() => {
        router.push(redirectUrl);
        router.refresh();
      });
    } catch (err: unknown) {
      const errorMsg =
        (err as { message?: string })?.message ||
        "کد تایید وارد شده نامعتبر یا منقضی شده است.";
      setOtpError(errorMsg);
      toast({
        title: "خطا در تایید کد",
        description: errorMsg,
        variant: "destructive",
      });
    } finally {
      setIsOtpVerifying(false);
    }
  };

  // Resend OTP
  const handleResendOtp = useCallback(() => {
    if (countdown > 0 || isOtpSending) return;
    handleSendOtp();
  }, [countdown, isOtpSending, handleSendOtp]);

  // Sync phone when switching tabs if empty
  const handleTabChange = (val: string) => {
    const tab = val as "password" | "otp";
    setActiveTab(tab);
    if (tab === "otp" && !otpPhone && phone) {
      setOtpPhone(phone);
    } else if (tab === "password" && !phone && otpPhone) {
      setPhone(otpPhone);
    }
  };

  return (
    <div className="container mx-auto flex min-h-[calc(100vh-140px)] items-center justify-center px-4 py-12" dir="rtl">
      <div className="w-full max-w-md">
        {/* Brand Logo & Back to Home */}
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
            <CardTitle className="text-2xl font-bold tracking-tight">ورود به حساب کاربری</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              برای مدیریت سفارش‌ها و دسترسی به امکانات فروشگاه وارد شوید
            </CardDescription>
          </CardHeader>

          <CardContent className="pt-2">
            <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="password" className="flex items-center gap-2 text-xs sm:text-sm">
                  <KeyRound className="h-4 w-4" />
                  <span>رمز عبور</span>
                </TabsTrigger>
                <TabsTrigger value="otp" className="flex items-center gap-2 text-xs sm:text-sm">
                  <ShieldCheck className="h-4 w-4" />
                  <span>کد یکبار مصرف (پیامک)</span>
                </TabsTrigger>
              </TabsList>

              {/* ──────────────────────────────────────────────────────────── */}
              {/* Tab 1: Password Login                                         */}
              {/* ──────────────────────────────────────────────────────────── */}
              <TabsContent value="password" className="mt-4 space-y-4">
                {passwordError && (
                  <div className="flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <p>{passwordError}</p>
                  </div>
                )}

                <form onSubmit={handlePasswordLogin} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="phone-input" className="text-xs font-medium">
                      شماره موبایل
                    </Label>
                    <div className="relative">
                      <Input
                        id="phone-input"
                        type="tel"
                        dir="ltr"
                        placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                        value={phone}
                        onChange={(e) => {
                          setPhone(e.target.value);
                          if (passwordError) setPasswordError(null);
                        }}
                        autoComplete="username tel"
                        className="pl-10 text-left font-mono tracking-wider"
                        disabled={isPasswordSubmitting}
                      />
                      <Smartphone className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      شماره ۱۱ رقمی همراه با ۰۹ (مثال: ۰۹۱۲۳۴۵۶۷۸۹)
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="password-input" className="text-xs font-medium">
                        رمز عبور
                      </Label>
                      <button
                        type="button"
                        onClick={() => {
                          setActiveTab("otp");
                          if (!otpPhone && phone) setOtpPhone(phone);
                        }}
                        className="text-[11px] text-primary hover:underline"
                      >
                        ورود با کد یکبار مصرف
                      </button>
                    </div>
                    <div className="relative">
                      <Input
                        id="password-input"
                        type={showPassword ? "text" : "password"}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => {
                          setPassword(e.target.value);
                          if (passwordError) setPasswordError(null);
                        }}
                        autoComplete="current-password"
                        className="pl-10 text-left font-mono"
                        disabled={isPasswordSubmitting}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                        aria-label={showPassword ? "مخفی کردن رمز" : "نمایش رمز"}
                      >
                        {showPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>

                  <Button
                    type="submit"
                    className="w-full font-medium"
                    disabled={isPasswordSubmitting}
                  >
                    {isPasswordSubmitting ? (
                      <>
                        <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                        <span>در حال ورود...</span>
                      </>
                    ) : (
                      <>
                        <Lock className="ml-2 h-4 w-4" />
                        <span>ورود به حساب کاربری</span>
                      </>
                    )}
                  </Button>
                </form>
              </TabsContent>

              {/* ──────────────────────────────────────────────────────────── */}
              {/* Tab 2: OTP Login                                             */}
              {/* ──────────────────────────────────────────────────────────── */}
              <TabsContent value="otp" className="mt-4 space-y-4">
                {otpError && (
                  <div className="flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <p>{otpError}</p>
                  </div>
                )}

                {otpStep === "phone" ? (
                  // Step 1: Request OTP
                  <form onSubmit={handleSendOtp} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="otp-phone-input" className="text-xs font-medium">
                        شماره موبایل
                      </Label>
                      <div className="relative">
                        <Input
                          id="otp-phone-input"
                          type="tel"
                          dir="ltr"
                          placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                          value={otpPhone}
                          onChange={(e) => {
                            setOtpPhone(e.target.value);
                            if (otpError) setOtpError(null);
                          }}
                          autoComplete="tel"
                          className="pl-10 text-left font-mono tracking-wider"
                          disabled={isOtpSending}
                        />
                        <Smartphone className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        کد تایید به این شماره پیامک خواهد شد.
                      </p>
                    </div>

                    <Button
                      type="submit"
                      className="w-full font-medium"
                      disabled={isOtpSending}
                    >
                      {isOtpSending ? (
                        <>
                          <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                          <span>در حال ارسال پیامک...</span>
                        </>
                      ) : (
                        <>
                          <ShieldCheck className="ml-2 h-4 w-4" />
                          <span>دریافت کد تایید</span>
                        </>
                      )}
                    </Button>
                  </form>
                ) : (
                  // Step 2: Verify OTP
                  <form onSubmit={handleVerifyOtp} className="space-y-4">
                    <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">کد پیامک‌شده به:</span>
                        <button
                          type="button"
                          onClick={() => {
                            setOtpStep("phone");
                            setOtpCode("");
                            setOtpError(null);
                          }}
                          className="font-medium text-primary hover:underline"
                        >
                          تغییر شماره
                        </button>
                      </div>
                      <p className="mt-1 font-mono text-sm font-semibold text-foreground" dir="ltr">
                        {toPersianDigits(otpPhone)}
                      </p>
                    </div>

                    <div className="space-y-3">
                      <Label htmlFor="otp-code-input" className="text-xs font-medium">
                        کد تایید ۶ رقمی
                      </Label>
                      <div className="flex justify-center" dir="ltr">
                        <InputOTPItem
                          id="otp-code-input"
                          maxLength={6}
                          value={otpCode}
                          autoFocus
                          disabled={isOtpVerifying}
                          onChange={(value: string) => {
                            const digitsOnly = toEnglishDigits(value).replace(/\D/g, "").slice(0, 6);
                            setOtpCode(digitsOnly);
                            if (otpError) setOtpError(null);
                          }}
                        >
                          <InputOTPGroup>
                            <InputOTPSlot index={0} />
                            <InputOTPSlot index={1} />
                            <InputOTPSlot index={2} />
                            <InputOTPSlot index={3} />
                            <InputOTPSlot index={4} />
                            <InputOTPSlot index={5} />
                          </InputOTPGroup>
                        </InputOTPItem>
                      </div>
                      <p className="text-center text-[11px] text-muted-foreground">
                        کد ۶ رقمی پیامک‌شده را وارد کنید
                      </p>
                    </div>

                    {/* Resend Countdown */}
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      {countdown > 0 ? (
                        <span className="flex items-center gap-1.5">
                          <span>ارسال مجدد کد تا</span>
                          <span className="font-mono font-semibold text-foreground">
                            {formatTimer(countdown)}
                          </span>
                          <span>دیگر</span>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={handleResendOtp}
                          disabled={isOtpSending}
                          className="flex items-center gap-1.5 font-medium text-primary transition-colors hover:text-primary/80 disabled:opacity-50"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          <span>ارسال مجدد کد تایید</span>
                        </button>
                      )}
                    </div>

                    <Button
                      type="submit"
                      className="w-full font-medium"
                      disabled={isOtpVerifying || otpCode.length < 4}
                    >
                      {isOtpVerifying ? (
                        <>
                          <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                          <span>در حال بررسی کد...</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="ml-2 h-4 w-4" />
                          <span>تایید و ورود</span>
                        </>
                      )}
                    </Button>
                  </form>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>

          <CardFooter className="flex flex-col gap-3 border-t border-border/40 pt-4 text-center text-xs">
            <p className="text-muted-foreground">
              حساب کاربری ندارید؟{" "}
              <Link
                href={`/register${searchParams.get("redirect") ? `?redirect=${encodeURIComponent(searchParams.get("redirect")!)}` : ""}`}
                className="font-semibold text-primary hover:underline"
              >
                ثبت‌نام در سایت
              </Link>
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-140px)] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
