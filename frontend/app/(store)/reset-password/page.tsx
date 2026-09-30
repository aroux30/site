"use client";

/** Redeems a reset token and sets a new password.
 *
 * The token arrives in the query string of the emailed link. Every session is
 * revoked server-side on success, so the user is sent to /login rather than
 * left holding cookies that no longer work.
 */
import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, CheckCircle2, Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";
import { authApi } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";

function ResetForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setError("رمزهای واردشده یکسان نیستند.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.resetPassword({ token, new_password: password });
      setDone(true);
      toast({ title: res.message });
      setTimeout(() => router.push("/login"), 2500);
    } catch (err) {
      // An expired or already-used token lands here.
      setError("پیوند بازیابی نامعتبر یا منقضی شده است. لطفاً دوباره درخواست دهید.");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="space-y-4 text-center" dir="rtl">
        <AlertCircle className="mx-auto h-10 w-10 text-destructive" />
        <p className="text-sm text-muted-foreground">
          پیوند بازیابی نامعتبر است. لطفاً از صفحه‌ی بازیابی رمز، درخواست تازه‌ای بفرستید.
        </p>
      </div>
    );
  }

  if (done) {
    return (
      <div className="space-y-4 text-center" dir="rtl">
        <CheckCircle2 className="mx-auto h-10 w-10 text-primary" />
        <p className="text-sm text-muted-foreground">
          رمز عبور تغییر کرد. همه‌ی دستگاه‌ها از حساب خارج شدند؛ اکنون وارد شوید.
        </p>
        <Button asChild className="w-full">
          <Link href="/login">ورود به حساب</Link>
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" dir="rtl">
      <div className="space-y-2">
        <Label htmlFor="new-password">رمز عبور جدید</Label>
        <div className="relative">
          <Input
            id="new-password"
            type={show ? "text" : "password"}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
          <button
            type="button"
            onClick={() => setShow((v) => !v)}
            className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
            aria-label={show ? "پنهان کردن رمز" : "نمایش رمز"}
          >
            {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          حداقل ۸ نویسه، شامل حرف و رقم.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirm-password">تکرار رمز عبور جدید</Label>
        <Input
          id="confirm-password"
          type={show ? "text" : "password"}
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
      </div>

      {error && (
        <p className="flex items-start gap-1.5 text-sm text-destructive" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </p>
      )}

      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? (
          <>
            <Loader2 className="ml-2 h-4 w-4 animate-spin" />
            در حال ثبت…
          </>
        ) : (
          "ثبت رمز عبور جدید"
        )}
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="container flex min-h-[70vh] items-center justify-center py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <KeyRound className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-xl">تعیین رمز عبور جدید</CardTitle>
          <CardDescription>
            پس از تغییر رمز، همه‌ی نشست‌های فعال شما باطل می‌شود.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={null}>
            <ResetForm />
          </Suspense>
        </CardContent>
        <CardFooter>
          <Button variant="ghost" className="w-full" asChild>
            <Link href="/login">بازگشت به ورود</Link>
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
