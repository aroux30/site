"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";

/**
 * Reactive client-side guard for the customer account area (/account/*).
 *
 * The edge middleware only runs on full-page navigations, so a guest who ends
 * up on an account page without a server round-trip (e.g. right after logout,
 * or an expired JS cookie) would otherwise strand there as a "guest" shell.
 * Guests are bounced to /login?redirect=<current path>; authenticated users
 * render immediately from the persisted session.
 */
export function AccountAuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();

  const isGuest = !isLoading && !isAuthenticated;

  useEffect(() => {
    if (isGuest) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [isGuest, pathname, router]);

  if (isAuthenticated) {
    return <>{children}</>;
  }

  // Guest: either the session probe is still running or the redirect to
  // /login has been kicked off — never render the account page itself.
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <Loader2 className="h-10 w-10 animate-spin text-primary" />
      <p className="text-sm font-medium text-foreground">
        {isGuest
          ? "در حال انتقال به صفحه ورود..."
          : "در حال بررسی وضعیت حساب کاربری..."}
      </p>
      <p className="text-xs text-muted-foreground">
        برای مشاهده این صفحه باید وارد حساب کاربری خود شوید.
      </p>
    </div>
  );
}
