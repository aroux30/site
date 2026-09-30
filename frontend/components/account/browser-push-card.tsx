"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, BellOff, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  hasPushSubscription,
  isPwaSupported,
  subscribeToPush,
  unsubscribeFromPush,
} from "@/lib/pwa";

/**
 * The browser-side push switch, kept separate from the notification
 * *preference* toggles on purpose.
 *
 * The preference says "I want push notifications"; this card says whether
 * *this browser* can receive them. Conflating the two produces the classic
 * support call — "push is on, why do I get nothing" — where the preference
 * was enabled but no browser ever subscribed.
 */
export function BrowserPushCard() {
  const { toast } = useToast();
  const [supported, setSupported] = useState<boolean | null>(null);
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setSupported(isPwaSupported());
    if (isPwaSupported()) {
      setSubscribed(await hasPushSubscription());
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const enable = async () => {
    setBusy(true);
    try {
      const result = await subscribeToPush();
      if (result.ok) {
        toast({
          title: "اعلان مرورگر فعال شد",
          description: "از این پس اعلان‌ها روی این مرورگر نمایش داده می‌شوند.",
          variant: "success",
        });
        setSubscribed(true);
      } else if (result.reason === "denied") {
        toast({
          title: "اجازه اعلان داده نشد",
          description:
            "مرورگر اجازه نمایش اعلان را نداد. برای تغییر، از تنظیمات خود مرورگر اجازه دهید.",
          variant: "destructive",
        });
      } else if (result.reason === "no-vapid-key") {
        toast({
          title: "اعلان مرورگر روی سرور پیکربندی نشده است",
          description:
            "کلیدهای VAPID تنظیم نشده‌اند؛ بدون آن‌ها اعلان مرورگر ارسال نمی‌شود.",
          variant: "destructive",
        });
      } else if (result.reason === "unsupported") {
        toast({
          title: "این مرورگر پشتیبانی نمی‌کند",
          variant: "destructive",
        });
      } else {
        toast({ title: "فعال‌سازی ناموفق بود", variant: "destructive" });
      }
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    setBusy(true);
    try {
      const ok = await unsubscribeFromPush();
      if (ok) {
        toast({
          title: "اعلان مرورگر غیرفعال شد",
          variant: "success",
        });
      } else {
        toast({ title: "غیرفعال‌سازی ناموفق بود", variant: "destructive" });
      }
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {subscribed ? (
            <Bell className="mt-0.5 h-5 w-5 text-emerald-600" />
          ) : (
            <BellOff className="mt-0.5 h-5 w-5 text-muted-foreground" />
          )}
          <div>
            <h3 className="font-semibold">اعلان مرورگر روی این دستگاه</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              مرورگر می‌تواند حتی وقتی سایت بسته است اعلان نمایش دهد — پس از
              دادن اجازه، اعلان‌های انتخابی شما روی همین دستگاه می‌آید.
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {supported === false && (
                <Badge variant="outline" className="text-[10px]">
                  <AlertTriangle className="ms-1 h-3 w-3" />
                  این مرورگر پشتیبانی نمی‌کند
                </Badge>
              )}
              {supported && subscribed && (
                <Badge variant="default" className="text-[10px]">
                  <CheckCircle2 className="ms-1 h-3 w-3" />
                  فعال روی این دستگاه
                </Badge>
              )}
              {supported && !subscribed && (
                <Badge variant="secondary" className="text-[10px]">
                  فعال نیست
                </Badge>
              )}
            </div>
          </div>
        </div>
        <div className="shrink-0">
          {supported && !subscribed && (
            <Button onClick={enable} disabled={busy}>
              {busy ? (
                <Loader2 className="ms-2 h-4 w-4 animate-spin" />
              ) : (
                <Bell className="ms-2 h-4 w-4" />
              )}
              فعال‌سازی روی این دستگاه
            </Button>
          )}
          {supported && subscribed && (
            <Button variant="outline" onClick={disable} disabled={busy}>
              {busy ? (
                <Loader2 className="ms-2 h-4 w-4 animate-spin" />
              ) : (
                <BellOff className="ms-2 h-4 w-4" />
              )}
              غیرفعال‌سازی
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
