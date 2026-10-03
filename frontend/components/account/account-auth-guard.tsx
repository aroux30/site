"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
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
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();

  // An email-confirmation link must work for a logged-out visitor. The endpoint
  // it calls is unauthenticated by design — the single-use, short-lived, hashed
  // token is the credential — so bouncing to /login would make the flow
  // unreachable for exactly the case it exists to serve, and the login redirect
  // carries only the pathname, so the token would be dropped on the way back.
  // Relaxing the edge middleware alone is not enough: this guard runs on the
  // client and would undo it.
  //
  // The privacy-request confirmation link has the same shape and the same
  // reason: a subject whose session has expired since they raised the request
  // must still be able to confirm it from the mailbox the link went to.
  const isEmailConfirmation = searchParams.has("email_token");
  const isPrivacyConfirmation = searchParams.has("privacy_confirm_token");
  const isTokenConfirmation = isEmailConfirmation || isPrivacyConfirmation;

  const isGuest = !isLoading && !isAuthenticated && !isTokenConfirmation;

  useEffect(() => {
    if (isGuest) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [isGuest, pathname, router]);

  if (isAuthenticated || isTokenConfirmation) {
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
