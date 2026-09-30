"use client";

/** «رمزم را فراموش کرده‌ام» — asks the API for a reset link.
 *
 * The server answers identically for a registered and an unregistered
 * address, so this screen must not claim success or failure based on what
 * comes back — only echo the neutral message it returns.
 */
import { useState } from "react";
import Link from "next/link";
import { ArrowRight, KeyRound, Loader2, Mail, ShieldCheck } from "lucide-react";
import { authApi } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";

export default function ForgotPasswordPage() {
  const { toast } = useToast();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      toast({ variant: "destructive", title: "ایمیل را وارد کنید" });
      return;
    }
    setLoading(true);
    try {
      const res = await authApi.forgotPassword(email.trim());
      setSent(true);
      toast({ title: res.message });
    } catch {
      // A failure here is deliberately vague: telling the user "no such
      // account" would turn the form into an account-existence oracle.
      toast({
        variant: "destructive",
        title: "ارسال پیوند بازیابی ممکن نشد. لطفاً کمی بعد دوباره تلاش کنید.",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container flex min-h-[70vh] items-center justify-center py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <KeyRound className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-xl">بازیابی رمز عبور</CardTitle>
          <CardDescription>
            ایمیلی که با آن ثبت‌نام کرده‌اید را وارد کنید تا پیوند بازیابی برایتان ارسال شود.
          </CardDescription>
        </CardHeader>

        <CardContent>
          {sent ? (
            <div className="space-y-4 text-center" dir="rtl">
              <Mail className="mx-auto h-10 w-10 text-primary" />
              <p className="text-sm text-muted-foreground">
                اگر این ایمیل در سامانه ثبت شده باشد، پیوند بازیابی ارسال شد.
                پیوند تا ۳۰ دقیقه معتبر است.
              </p>
              <p className="text-xs text-muted-foreground">
                ایمیلی را که نمی‌بینید؟ پوشه‌ی هرزنامه (Spam) را بررسی کنید.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4" dir="rtl">
              <div className="space-y-2">
                <Label htmlFor="email">ایمیل</Label>
                <Input
                  id="email"
                  type="email"
                  dir="ltr"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                    در حال ارسال…
                  </>
                ) : (
                  "ارسال پیوند بازیابی"
                )}
              </Button>
            </form>
          )}
        </CardContent>

        <CardFooter className="flex-col gap-2">
          <Button variant="ghost" className="w-full" asChild>
            <Link href="/login">
              بازگشت به ورود
              <ArrowRight className="mr-2 h-4 w-4" />
            </Link>
          </Button>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5" />
            پس از بازیابی، همه‌ی دستگاه‌های شما از حساب خارج می‌شوند.
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
