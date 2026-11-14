"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  Bell,
  CheckCheck,
  CheckCircle2,
  Gift,
  Loader2,
  Package,
  Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { apiErrorMessage } from "@/lib/api/error-message";
import { notificationsApi, type Notification } from "@/lib/api/notifications";

/**
 * Notification inbox — the surface that shows every in-app notification
 * written for this user (order updates, wallet events, and the referral /
 * bonus rewards).
 *
 * Why this exists: notifications were being created for years (order events,
 * refunds, wallet changes, and now referral rewards) but the account area
 * only had the *preferences* page — no list ever rendered `notificationsApi.
 * list`, so every notification was written and never read. The reward
 * feature made that gap visible.
 */

const TYPE_ICONS: Array<{ prefix: string; icon: React.ComponentType<{ className?: string }> }> = [
  { prefix: "wallet_referral", icon: Gift },
  { prefix: "wallet_recharge_bonus", icon: Wallet },
  { prefix: "wallet_", icon: Wallet },
  { prefix: "order_", icon: Package },
  { prefix: "payment_", icon: Wallet },
];

function iconFor(type: string): React.ComponentType<{ className?: string }> {
  for (const { prefix, icon } of TYPE_ICONS) {
    if (type.startsWith(prefix)) return icon;
  }
  return Bell;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("fa-IR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

const PAGE_SIZE = 20;

export function NotificationInbox() {
  const { toast } = useToast();
  const [items, setItems] = useState<Notification[]>([]);
  const [total, setTotal] = useState(0);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [marking, setMarking] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await notificationsApi.list({ skip: 0, limit: PAGE_SIZE });
      setItems(data.items);
      setTotal(data.total);
      setUnread(data.unread_count);
    } catch (err) {
      // A failed load must outrank an empty list (account-area rule).
      setError(apiErrorMessage(err, "دریافت اعلان‌ها ناموفق بود"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onMarkRead = async (id: string) => {
    setMarking(id);
    try {
      await notificationsApi.markAsRead(id);
      setItems((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n)),
      );
      setUnread((prev) => Math.max(0, prev - 1));
    } catch (err) {
      toast({
        title: "خطا",
        description: apiErrorMessage(err, "خوانده‌شدن اعلان ناموفق بود"),
        variant: "destructive",
      });
    } finally {
      setMarking(null);
    }
  };

  const onMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnread(0);
      toast({ title: "انجام شد", description: "همهٔ اعلان‌ها خوانده‌شده شدند." });
    } catch (err) {
      toast({
        title: "خطا",
        description: apiErrorMessage(err, "عملیات ناموفق بود"),
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm">در حال بارگذاری اعلان‌ها…</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive/30 bg-destructive/5 p-6">
        <p className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          {error}
        </p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => void load()}>
          تلاش دوباره
        </Button>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-bold text-foreground">اعلان‌های من</h3>
          {unread > 0 && (
            <Badge variant="destructive" className="text-[10px]">
              {unread.toLocaleString("fa-IR")} خوانده‌نشده
            </Badge>
          )}
        </div>
        {unread > 0 && (
          <Button variant="outline" size="sm" onClick={() => void onMarkAllRead()}>
            <CheckCheck className="me-1.5 h-3.5 w-3.5" />
            خواندن همه
          </Button>
        )}
      </div>

      {items.length === 0 ? (
        <Card className="p-10 text-center">
          <Bell className="mx-auto mb-3 h-10 w-10 opacity-25" />
          <p className="text-sm text-muted-foreground">هنوز اعلانی ندارید.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            نتیجهٔ خریدها، شارژ کیف پول و پاداش‌های دعوت دوستان اینجا نمایش داده می‌شود.
          </p>
        </Card>
      ) : (
        <div className="space-y-2">
          {items.map((n) => {
            const Icon = iconFor(n.type);
            return (
              <Card
                key={n.id}
                className={`flex items-start gap-3 p-4 transition-colors ${
                  n.is_read ? "" : "border-primary/30 bg-primary/5"
                }`}
              >
                <div
                  className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                    n.is_read ? "bg-muted text-muted-foreground" : "bg-primary/10 text-primary"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className={`text-sm ${n.is_read ? "text-foreground" : "font-bold text-foreground"}`}>
                      {n.title}
                    </p>
                    {!n.is_read && <span className="h-2 w-2 shrink-0 rounded-full bg-primary" />}
                  </div>
                  {n.body && (
                    <p className="mt-1 whitespace-pre-line text-xs leading-relaxed text-muted-foreground">
                      {n.body}
                    </p>
                  )}
                  <p className="mt-1.5 text-[10px] text-muted-foreground">{formatDate(n.created_at)}</p>
                </div>
                {!n.is_read && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="shrink-0 text-xs"
                    disabled={marking === n.id}
                    onClick={() => void onMarkRead(n.id)}
                  >
                    {marking === n.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <CheckCircle2 className="me-1 h-3.5 w-3.5" />
                    )}
                    خواندم
                  </Button>
                )}
              </Card>
            );
          })}
          {total > items.length && (
            <p className="pt-1 text-center text-xs text-muted-foreground">
              {items.length.toLocaleString("fa-IR")} از {total.toLocaleString("fa-IR")} اعلان نمایش داده شد.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
