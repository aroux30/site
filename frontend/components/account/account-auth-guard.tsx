"use client";

import React, { Suspense, useEffect } from "react";
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
 *
 * The Suspense boundary is kept (the inner component no longer reads
 * `useSearchParams` — the email-token bypass was removed on 2026-10-07 — but
 * the fallback is still the "checking your session" panel the guard shows
 * while the auth probe runs, so both states look identical).
 */
export function AccountAuthGuard({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<AuthCheckPanel />}>
      <AccountAuthGuardInner>{children}</AccountAuthGuardInner>
    </Suspense>
  );
}

function AuthCheckPanel() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <Loader2 className="h-10 w-10 animate-spin text-primary" />
      <p className="text-sm font-medium text-foreground">
        در حال بررسی وضعیت حساب کاربری...
      </p>
      <p className="text-xs text-muted-foreground">
        برای مشاهده این صفحه باید وارد حساب کاربری خود شوید.
      </p>
    </div>
  );
}

function AccountAuthGuardInner({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading, fetchCurrentUser } = useAuth();

  // Cookie-only session discovery. The storefront mount probe is skipped when
  // the client store holds no session signal (a guest never signs in, and the
  // probe's 401 is console noise for them). On a protected route that is too
  // aggressive: edge middleware already let this request through, which means
  // an HttpOnly access/refresh cookie may exist even when localStorage was
  // cleared. Probe explicitly here so that session is still discovered.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem("auth-storage");
      const parsed = raw ? JSON.parse(raw) : null;
      if (parsed?.state?.isAuthenticated) return;
    } catch {
      /* unreadable storage — probe anyway */
    }
    fetchCurrentUser().catch(() => {
      /* 401 -> the redirect effect below sends the visitor to /login */
    });
    // Mount-only: fetchCurrentUser is recreated on every store update, so
    // depending on it would re-probe (and 401) on each state change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The email-token bypass (`?email_token=`) was removed on 2026-10-07 with
  // the rest of the email feature; every account page now requires a session.
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

