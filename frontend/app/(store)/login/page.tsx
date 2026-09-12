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
  Shield,
  Truck,
  Phone,
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
import { toEnglishDigits, toPersianDigits, isValidIranPhone, normalizeIranPhone } from "@/lib/utils";

const OTP_COUNTDOWN_SECONDS = 120;

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { login, requestOtp, verifyOtp, isAuthenticated, isLoading: isAuthLoading, user } = useAuth();

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

  // If already authenticated with confirmed user profile, redirect only if authorized for target
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Verify that access_token cookie actually exists before auto-redirecting
    const hasAccessTokenCookie =
      typeof document !== "undefined" &&
      /(?:^|;\s*)access_token=([^;]+)/.test(document.cookie);

    if (isAuthenticated && !isAuthLoading && user) {
      if (!hasAccessTokenCookie) {
        // Stale client state: cookie is missing or expired, do not auto-redirect
        return;
      }

      // Avoid redirect loops: do not redirect to login or register
      if (redirectUrl.startsWith("/login") || redirectUrl.startsWith("/register")) {
        router.replace("/");
        return;
      }

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

    const cleanPhone = normalizeIranPhone(phone);
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
        password: toEnglishDigits(password),
      });

      toast({
        title: "ورود موفق",
        description: "به حساب کاربری خود خوش آمدید.",
        variant: "success",
      });

      // Navigation is owned by the auto-redirect effect below (single-path):
      // firing router.push here raced with the effect's router.replace and
      // both cancelled out, leaving the user stuck on /login after a
      // successful login.
    } catch (err: unknown) {
      const errorMsg =
        (err as { response?: { data?: { error?: { message?: string } } }; message?: string })?.response?.data?.error?.message ||
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

      const cleanPhone = normalizeIranPhone(otpPhone);
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
        // The OTP must never be rendered client-side, even if a dev-mode
        // backend echoes it — displaying it would let anyone log in as any
        // phone number. Auto-filling dev codes is also disabled here.
        setOtpCode("");
        toast({
          title: "کد تایید ارسال شد",
          description: res.message || `کد یکبار مصرف به شماره ${toPersianDigits(cleanPhone)} ارسال شد.`,
          variant: "success",
        });
      } catch (err: unknown) {
        const errorMsg =
          (err as { response?: { data?: { error?: { message?: string } } }; message?: string })?.response?.data?.error?.message ||
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

    const cleanPhone = normalizeIranPhone(otpPhone);
    const cleanCode = toEnglishDigits(otpCode.replace(/\D/g, "").trim());

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

      // Navigation is owned by the auto-redirect effect below (single-path):
      // firing router.push here raced with the effect's router.replace and
      // both cancelled out, leaving the user stuck on /login after a
      // successful login.
    } catch (err: unknown) {
      const errorMsg =
        (err as { response?: { data?: { error?: { message?: string } } }; message?: string })?.response?.data?.error?.message ||
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

  // Sync phone when switching tabs if empty, and reset stale OTP state
  const handleTabChange = (val: string) => {
    const tab = val as "password" | "otp";
    setActiveTab(tab);
    if (tab === "otp" && !otpPhone && phone) {
      setOtpPhone(phone);
    } else if (tab === "password" && !phone && otpPhone) {
      setPhone(otpPhone);
    }
    if (tab === "password" && otpStep === "code") {
      setOtpStep("phone");
      setOtpCode("");
      setOtpError(null);
    }
  };

  return (
    <div className="container mx-auto px-4 py-12" dir="rtl">
      <div className="mx-auto grid w-full max-w-5xl items-center gap-8 lg:grid-cols-5">
        {/* Form side — first in RTL reading order */}
        <div className="mx-auto w-full max-w-md lg:col-span-3 lg:mx-0 lg:max-w-none">
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
                          setPasswordError(null);
                        }}
                        className="text-[11px] text-primary hover:underline"
                      >
                        رمز عبور را فراموش کرده‌ام؟ ورود با کد یکبار مصرف
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
                      {otpCode && (
                        <div className="flex items-center justify-center gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 py-2 px-3 text-xs text-emerald-600 dark:text-emerald-400 font-semibold shadow-xs">
                          <span>کد تایید دریافتی:</span>
                          <span className="font-black text-sm tracking-wider font-sans tabular-nums">
                            {toPersianDigits(otpCode)}
                          </span>
                        </div>
                      )}
                      <p className="text-center text-[11px] text-muted-foreground">
                        کد ۶ رقمی پیامک‌شده را در کادرهای بالا وارد فرمایید.
                      </p>
                    </div>

                    {/* Resend Countdown */}
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      {countdown > 0 ? (
                        <span className="flex items-center gap-1.5">
                          <span>ارسال مجدد کد تا</span>
                          <span className="font-sans font-bold text-foreground tabular-nums">
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

        {/* Brand trust panel — desktop only */}
        <aside className="relative hidden overflow-hidden rounded-3xl bg-gradient-to-bl from-emerald-950 via-slate-900 to-slate-950 p-8 text-white shadow-xl lg:col-span-2 lg:flex lg:flex-col">
          {/* Soft brand glow */}
          <div className="pointer-events-none absolute -top-24 -left-24 h-64 w-64 rounded-full bg-emerald-500/20 blur-3xl" aria-hidden />
          <div className="pointer-events-none absolute -bottom-24 -right-16 h-56 w-56 rounded-full bg-teal-500/10 blur-3xl" aria-hidden />

          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 text-lg font-black text-white ring-1 ring-white/20">
              ف
            </div>
            <div>
              <p className="text-lg font-bold leading-tight">فروشگاه آنلاین</p>
              <p className="text-xs text-white/60">ضمانت اصالت و بهترین قیمت</p>
            </div>
          </div>

          <h2 className="mt-10 text-2xl font-black leading-[1.5]">
            خرید مطمئن، از انتخاب تا تحویل
          </h2>
          <p className="mt-3 text-sm leading-7 text-white/70">
            با خیال راحت گجت و لوازم دیجیتال بخر؛ ما اصالت، قیمت و ارسال را تضمین می‌کنیم.
          </p>

          <ul className="mt-8 space-y-5">
            {[
              { icon: Shield, title: "ضمانت اصالت کالا", desc: "همه کالاها اورجینال با گارانتی رسمی شرکتی" },
              { icon: Truck, title: "ارسال سریع سراسری", desc: "تحویل ۱ تا ۳ روز کاری در سراسر ایران" },
              { icon: RotateCcw, title: "۷ روز مهلت بازگشت", desc: "اگر راضی نبودی، بدون دردسر برگردان" },
            ].map((item) => (
              <li key={item.title} className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/30">
                  <item.icon className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-bold">{item.title}</p>
                  <p className="mt-0.5 text-xs leading-6 text-white/60">{item.desc}</p>
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-auto space-y-4 pt-10">
            <div className="grid grid-cols-2 gap-3 border-t border-white/10 pt-6 text-center">
              <div>
                <p className="text-xl font-black">+۵۰,۰۰۰</p>
                <p className="mt-0.5 text-[11px] text-white/60">مشتری وفادار</p>
              </div>
              <div>
                <p className="text-xl font-black text-emerald-300">۹۹.۸٪</p>
                <p className="mt-0.5 text-[11px] text-white/60">رضایت خریداران</p>
              </div>
            </div>
            <p className="flex items-center justify-center gap-1.5 text-xs text-white/60">
              <Phone className="h-3.5 w-3.5" />
              پشتیبانی ۲۴/۷
              <span dir="ltr" className="font-bold text-white/85">۰۲۱-۸۸۸۸۹۹۹۹</span>
            </p>
          </div>
        </aside>
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
