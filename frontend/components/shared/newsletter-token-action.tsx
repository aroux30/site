"use client";

/**
 * Shared token action screen for the newsletter lifecycle: the emailed link
 * carries (token, email); this component POSTs them to the matching endpoint
 * and renders the outcome. One component, two modes, because confirm and
 * unsubscribe are the same handshake with opposite effects.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { newsletterApi } from "@/lib/api/newsletter";

interface NewsletterTokenActionProps {
  mode: "confirm" | "unsubscribe";
  token: string | null;
  email: string | null;
}

const COPY = {
  confirm: {
    running: "در حال تأیید عضویت…",
    missing: "لینک تأیید نامعتبر است.",
    done: "عضویت شما در خبرنامه نهایی شد. از این پس تازه‌ترین مطالب را دریافت می‌کنید.",
    failed: "تأیید عضویت ناموفق بود؛ لینک ممکن است منقضی یا ناقص باشد.",
    title: "تأیید عضویت در خبرنامه",
  },
  unsubscribe: {
    running: "در حال لغو عضویت…",
    missing: "لینک لغو عضویت نامعتبر است.",
    done: "عضویت شما لغو شد و دیگر ایمیلی دریافت نخواهید کرد.",
    failed: "لغو عضویت ناموفق بود؛ لینک ممکن است ناقص باشد.",
    title: "لغو عضویت از خبرنامه",
  },
} as const;

export function NewsletterTokenAction({ mode, token, email }: NewsletterTokenActionProps) {
  const copy = COPY[mode];
  const [state, setState] = useState<"running" | "done" | "failed">("running");
  const [detail, setDetail] = useState<string>(copy.running);
  const ranOnce = useRef(false);

  useEffect(() => {
    if (ranOnce.current) return;
    ranOnce.current = true;
    if (!token || !email) {
      setState("failed");
      setDetail(copy.missing);
      return;
    }
    const action = mode === "confirm" ? newsletterApi.confirm : newsletterApi.unsubscribe;
    action(token, email)
      .then(() => {
        setState("done");
        setDetail(copy.done);
      })
      .catch(() => {
        setState("failed");
        setDetail(copy.failed);
      });
  }, [mode, token, email, copy]);

  return (
    <div className="container mx-auto flex max-w-lg items-center justify-center px-4 py-20">
      <Card className="w-full p-8 text-center">
        {state === "running" && (
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-primary" />
        )}
        {state === "done" && (
          <CheckCircle2 className="mx-auto mb-4 h-10 w-10 text-emerald-600" />
        )}
        {state === "failed" && <XCircle className="mx-auto mb-4 h-10 w-10 text-destructive" />}
        <h1 className="mb-3 text-lg font-bold">{copy.title}</h1>
        <p className="mb-6 text-sm leading-relaxed text-muted-foreground">{detail}</p>
        <Button asChild variant="outline" size="sm">
          <Link href="/">بازگشت به فروشگاه</Link>
        </Button>
      </Card>
    </div>
  );
}
