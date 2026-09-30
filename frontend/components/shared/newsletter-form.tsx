"use client";

/**
 * Newsletter signup form (double opt-in).
 *
 * Submits the address to the public subscribe endpoint and shows the server's
 * generic confirmation message — deliberately identical for new, pending, and
 * already-subscribed addresses, so the form cannot be used to probe which
 * emails exist. The emailed link leads to /newsletter/confirm.
 */

import { useState } from "react";
import { Loader2, Mail, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { newsletterApi } from "@/lib/api/newsletter";

export function NewsletterForm() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const res = await newsletterApi.subscribe(email.trim(), "footer");
      setMessage(res.message);
      setEmail("");
    } catch {
      setError("ارسال درخواست ناموفق بود؛ لطفاً دوباره تلاش کنید.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-border bg-background p-5">
      <div className="mb-3 flex items-center gap-2">
        <Mail className="h-4 w-4 text-primary" />
        <h4 className="text-sm font-bold text-foreground">عضویت در خبرنامه</h4>
      </div>
      <p className="mb-4 text-xs leading-relaxed text-muted-foreground">
        تازه‌ترین مقالات و پیشنهادهای ویژه را در ایمیل خود دریافت کنید. پس از
        ثبت، لینک تأیید برایتان ارسال می‌شود.
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          type="email"
          required
          dir="ltr"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          aria-label="آدرس ایمیل"
          className="h-9 flex-1 text-left text-xs"
        />
        <Button type="submit" size="sm" disabled={submitting} className="gap-1.5">
          {submitting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
          عضویت
        </Button>
      </form>
      {message && (
        <p className="mt-3 text-xs leading-relaxed text-emerald-600 dark:text-emerald-400">
          {message}
        </p>
      )}
      {error && (
        <p className="mt-3 text-xs leading-relaxed text-destructive">{error}</p>
      )}
    </div>
  );
}
