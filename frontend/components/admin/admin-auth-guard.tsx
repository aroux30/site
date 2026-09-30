"use client";

import React, { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ShieldAlert, Loader2, Home, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";

export function AdminAuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const idleTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 1. Inactivity idle timeout (30 minutes)
  useEffect(() => {
    if (!isAuthenticated) return;

    const resetTimer = () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      idleTimerRef.current = setTimeout(async () => {
        try {
          await logout({ redirectTo: null });
          router.replace("/login?reason=idle_timeout&redirect=/admin/dashboard");
        } catch {
          router.replace("/login?reason=idle_timeout&redirect=/admin/dashboard");
        }
      }, 30 * 60 * 1000);
    };

    const events = ["mousedown", "mousemove", "keydown", "scroll", "touchstart", "click"];
    resetTimer();
    events.forEach((ev) => window.addEventListener(ev, resetTimer, { passive: true }));

    return () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      events.forEach((ev) => window.removeEventListener(ev, resetTimer));
    };
  }, [isAuthenticated, logout, router]);

  // 2. Role & permission authorization check
  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated) {
      setIsAuthorized(false);
      router.replace("/login?redirect=/admin/dashboard");
      return;
    }

    const isAdmin = Boolean(
      user?.is_superuser ||
        user?.role === "admin" ||
        user?.roles?.includes("super_admin") ||
        user?.roles?.includes("admin") ||
        user?.permissions?.includes("*"),
    );

    setIsAuthorized(isAdmin);
  }, [isLoading, isAuthenticated, user, router]);

  // Render controls strictly inside a single return block without early returns
  return (
    <>
      {isLoading || isAuthorized === null ? (
        <div className="flex min-h-[400px] flex-col items-center justify-center bg-background px-4">
          <div className="flex flex-col items-center gap-4 text-center">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-base font-medium text-foreground">
              در حال بررسی دسترسی امنیتی پنل مدیریت...
            </p>
            <p className="text-xs text-muted-foreground">لطفاً چند لحظه صبر کنید</p>
          </div>
        </div>
      ) : !isAuthorized ? (
        <div className="flex min-h-[400px] flex-col items-center justify-center bg-background px-4" dir="rtl">
          <div className="mx-auto max-w-md text-center">
            <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-destructive/10 text-destructive">
              <ShieldAlert className="h-10 w-10" />
            </div>
            <h1 className="mb-2 text-2xl font-bold text-foreground">
              دسترسی غیرمجاز به پنل مدیریت (۴۰۳)
            </h1>
            <p className="mb-6 text-sm text-muted-foreground">
              حساب کاربری فعلی شما مجوز دسترسی به داشبورد و ابزارهای مدیریتی سیستم را ندارد.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link href="/" className="w-full sm:w-auto">
                <Button variant="outline" className="w-full gap-2">
                  <Home className="h-4 w-4" />
                  بازگشت به فروشگاه
                </Button>
              </Link>
              <Link href="/login?redirect=/admin/dashboard" className="w-full sm:w-auto">
                <Button className="w-full gap-2">
                  <LogIn className="h-4 w-4" />
                  ورود با حساب مدیر
                </Button>
              </Link>
            </div>
          </div>
        </div>
      ) : (
        children
      )}
    </>
  );
}
