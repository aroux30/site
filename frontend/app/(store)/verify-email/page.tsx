"use client";

/** Redeems the email-verification token from the emailed link.
 *
 * Lives outside /account on purpose: the link is clicked from an inbox, often
 * on a device with no session. The token is the credential, so the page works
 * signed in or out. On success it marks `is_verified` — the flag the OTP flow
 * used to set from phone ownership, which never actually proved the email.
 */
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, CheckCircle2, Loader2, MailCheck } from "lucide-react";
import { authApi } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type State =
  | { kind: "loading" }
  | { kind: "done"; email: string }
  | { kind: "error"; message: string };

function VerifyForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (!token) {
      setState({
        kind: "error",
        message: "پیوند تأیید ناقص است. لطفاً از ایمیل دریافتی دوباره روی پیوند کلیک کنید.",
      });
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await authApi.confirmEmailVerification(token);
        if (!cancelled) setState({ kind: "done", email: res.email });
      } catch (err) {
        if (cancelled) return;
        // The server answers with a specific reason (expired, already used,
        // superseded); surfacing a generic "invalid" would leave the user
        // re-clicking a link that can never work.
        const detail = (
          err as { response?: { data?: { error?: { message?: string }; detail?: string } } }
        )?.response?.data;
        setState({
          kind: "error",
          message:
            detail?.error?.message ||
            detail?.detail ||
            "تأیید ایمیل ناموفق بود. ممکن است پیوند منقضی شده باشد.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (state.kind === "loading") {
    return (
      <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        در حال تأیید ایمیل…
      </div>
    );
  }

  if (state.kind === "done") {
    return (
      <div className="space-y-4 text-center" dir="rtl">
        <CheckCircle2 className="mx-auto h-10 w-10 text-primary" />
        <p className="text-sm text-muted-foreground">
          ایمیل <span dir="ltr" className="font-mono">{state.email}</span> با موفقیت تأیید شد.
        </p>
        <Button asChild className="w-full">
          <Link href="/account">رفتن به حساب کاربری</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 text-center" dir="rtl">
      <AlertCircle className="mx-auto h-10 w-10 text-destructive" />
      <p className="text-sm text-muted-foreground">{state.message}</p>
      <p className="text-xs text-muted-foreground">
        می‌توانید از صفحه‌ی حساب، پیوند تأیید تازه‌ای درخواست کنید.
      </p>
      <Button asChild variant="outline" className="w-full">
        <Link href="/account/profile">صفحه‌ی حساب</Link>
      </Button>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="container flex min-h-[70vh] items-center justify-center py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <MailCheck className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-xl">تأیید ایمیل</CardTitle>
          <CardDescription>
            با تأیید ایمیل، اطلاع‌رسانی‌های مهم حساب به نشانی درست می‌رسد.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={null}>
            <VerifyForm />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}
