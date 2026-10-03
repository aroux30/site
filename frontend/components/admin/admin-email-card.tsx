"use client";

/**
 * The site admin email: propose, confirm, review.
 *
 * P1 "کاربران: تغییر ایمیل مدیریتی با تأییدیه و بازبینی دوره‌ای". This is
 * WordPress's ``new_admin_email`` flow: the address is where password resets
 * and order notices arrive, so it cannot be edited inline. A new address is
 * *proposed*; the confirmation link goes to the new address; the store's
 * address moves only when that link is redeemed.
 *
 * The review notice is the second half: an address that was confirmed long
 * ago may belong to somebody who left. "این ایمیل هنوز درست است" records a
 * fresh review without touching the address.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, Mail, ShieldCheck } from "lucide-react";

import { adminEmailApi, type AdminEmailStatus } from "@/lib/api/settings";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";

export function AdminEmailCard() {
  const { toast } = useToast();
  const [status, setStatus] = useState<AdminEmailStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [newEmail, setNewEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setStatus(await adminEmailApi.status());
      setError(null);
    } catch {
      // An unreadable status must not render as "no address": those are
      // different facts and an operator would act on the wrong one.
      setError("دریافت وضعیت ایمیل مدیریت ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // The confirmation link points back here with ?admin_email_token=… — the
  // operator is signed in, the token proves the mailbox. Redeemed on mount
  // and stripped from the URL afterwards so it does not linger in history.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("admin_email_token");
    if (!token) return;
    void (async () => {
      try {
        const res = await adminEmailApi.confirm(token);
        toast({
          title: res.status === "confirmed" ? "ایمیل مدیریت تأیید شد" : "تأیید ناموفق بود",
          description:
            res.status === "confirmed"
              ? `ایمیل مدیریت اکنون ${res.email ?? "نشانی جدید"} است.`
              : res.message || "لینک تأیید معتبر نیست یا منقضی شده است.",
          variant: res.status === "confirmed" ? "success" : "destructive",
        });
        await load();
      } catch {
        toast({
          title: "تأیید ایمیل مدیریت ناموفق بود",
          description: "لینک تأیید معتبر نیست یا منقضی شده است.",
          variant: "destructive",
        });
      } finally {
        params.delete("admin_email_token");
        const qs = params.toString();
        window.history.replaceState(null, "", window.location.pathname + (qs ? `?${qs}` : ""));
      }
    })();
  }, [load, toast]);

  async function proposeChange(): Promise<void> {
    const target = newEmail.trim();
    if (!target) return;
    setSending(true);
    try {
      const res = await adminEmailApi.requestChange(target);
      toast({
        title: res.status === "pending" ? "درخواست تغییر ثبت شد" : "تغییر اعمال نشد",
        description: res.message,
        variant: res.status === "pending" && res.email_sent !== false ? "success" : "destructive",
      });
      if (res.status === "pending") setNewEmail("");
      await load();
    } catch {
      toast({
        title: "درخواست تغییر ایمیل ناموفق بود",
        description: "لطفاً کمی بعد دوباره تلاش کنید.",
        variant: "destructive",
      });
    } finally {
      setSending(false);
    }
  }

  async function confirmStillCorrect(): Promise<void> {
    setReviewing(true);
    try {
      const res = await adminEmailApi.confirmCurrent();
      toast({
        title: res.status === "confirmed" ? "بازبینی ثبت شد" : "ثبت بازبینی ناموفق بود",
        description:
          res.status === "confirmed"
            ? "تاریخ بازبینی این ایمیل به‌روزرسانی شد."
            : "ایمیلی برای تأیید ثبت نشده است.",
        variant: res.status === "confirmed" ? "success" : "destructive",
      });
      await load();
    } catch {
      toast({
        title: "ثبت بازبینی ناموفق بود",
        variant: "destructive",
      });
    } finally {
      setReviewing(false);
    }
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <Mail className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">ایمیل مدیریت سایت</h2>
        {status?.needs_review && (
          <Badge variant="warning" className="gap-1 text-[10px]">
            <AlertTriangle className="h-3 w-3" />
            نیازمند بازبینی
          </Badge>
        )}
      </div>

      <p className="mb-4 text-xs leading-relaxed text-muted-foreground">
        ایمیل مدیریت جایی است که پیام‌های بازیابی رمز و اطلاع‌رسانی‌های فروشگاه به آن می‌رسد.
        برای تغییر، نشانی جدید پیشنهاد می‌شود و تا کلیک روی پیوند تأییدی که به همان نشانی
        فرستاده می‌شود، ایمیل فعلی تغییر نمی‌کند.
      </p>

      {error && (
        <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          در حال بارگذاری...
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs text-muted-foreground">ایمیل فعلی</span>
              <span className="font-mono text-sm" dir="ltr">
                {status?.admin_email || "—"}
              </span>
            </div>
            {status?.confirmed_at ? (
              <p className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
                <ShieldCheck className="h-3 w-3 text-emerald-600" />
                آخرین بازبینی: {new Date(status.confirmed_at).toLocaleDateString("fa-IR")}
                {" · "}
                بازبینی بعدی هر {status.review_interval_days.toLocaleString("fa-IR")} روز
              </p>
            ) : (
              <p className="mt-1 text-[11px] text-amber-600 dark:text-amber-400">
                این ایمیل هنوز بازبینی نشده است.
              </p>
            )}
          </div>

          {status?.pending_email && (
            <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2">
              <p className="text-xs text-amber-700 dark:text-amber-400">
                درخواست تغییر به <span dir="ltr" className="font-mono">{status.pending_email}</span> در
                انتظار تأیید است. پیوند تأیید به همان نشانی فرستاده شده و ایمیل فعلی تا کلیک روی
                آن تغییر نمی‌کند.
              </p>
            </div>
          )}

          {status?.needs_review && !status.pending_email && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2">
              <p className="text-xs text-amber-700 dark:text-amber-400">
                زمان بازبینی این ایمیل رسیده است. آیا هنوز درست است؟
              </p>
              <Button
                size="sm"
                variant="outline"
                disabled={reviewing}
                onClick={() => void confirmStillCorrect()}
              >
                {reviewing ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <>
                    <CheckCircle2 className="me-1 h-3.5 w-3.5" />
                    بله، درست است
                  </>
                )}
              </Button>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="admin-email-new" className="text-xs font-medium">
              تغییر ایمیل مدیریت
            </Label>
            <div className="flex gap-2">
              <Input
                id="admin-email-new"
                type="email"
                dir="ltr"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="new-admin@example.com"
                className="font-mono"
                disabled={sending}
              />
              <Button
                onClick={() => void proposeChange()}
                disabled={sending || !newEmail.trim()}
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : "ارسال پیوند تأیید"}
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              پیوند تأیید به نشانی جدید فرستاده می‌شود؛ پس از کلیک روی آن، ایمیل مدیریت عوض می‌شود.
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
