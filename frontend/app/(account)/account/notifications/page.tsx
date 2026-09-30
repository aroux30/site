"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Bell,
  Mail,
  Smartphone,
  MessageSquare,
  Globe,
  Inbox,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Link2,
  Unlink,
  RefreshCw,
  ArrowRight,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { BrowserPushCard } from "@/components/account/browser-push-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import apiClient from "@/lib/api/client";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type PreferencesResponse = {
  channels: Record<string, boolean>;
  categories: Record<string, boolean>;
  telegram_linked: boolean;
  telegram_chat_id_masked: string | null;
};

type LinkCodeResponse = {
  code: string;
  expires_at: string;
  bot_deep_link: string | null;
};

const CHANNEL_META: Array<{
  key: string;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { key: "in_app", label: "اعلان درون‌برنامه‌ای", hint: "نمایش در پنل کاربری", icon: Inbox },
  { key: "email", label: "ایمیل", hint: "ارسال به نشانی ایمیل حساب", icon: Mail },
  { key: "sms", label: "پیامک", hint: "ارسال به شماره موبایل حساب", icon: Smartphone },
  { key: "telegram", label: "تلگرام", hint: "نیازمند اتصال حساب تلگرام", icon: MessageSquare },
  { key: "push", label: "اعلان مرورگر (Push)", hint: "نمایش در مرورگر یا گوشی", icon: Globe },
];

const CATEGORY_META: Array<{ key: string; label: string }> = [
  { key: "order", label: "سفارش‌ها" },
  { key: "payment", label: "پرداخت و بازگشت وجه" },
  { key: "shipping", label: "ارسال و تحویل" },
  { key: "promotion", label: "تخفیف‌ها و کمپین‌ها" },
  { key: "system", label: "پیام‌های سیستمی و امنیتی" },
];

export default function AccountNotificationsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [channels, setChannels] = useState<Record<string, boolean>>({});
  const [categories, setCategories] = useState<Record<string, boolean>>({});
  const [telegramLinked, setTelegramLinked] = useState(false);
  const [telegramMasked, setTelegramMasked] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<{ ok: boolean; text: string } | null>(null);

  // Telegram link flow state
  const [linkCode, setLinkCode] = useState<LinkCodeResponse | null>(null);
  const [linkLoading, setLinkLoading] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await apiClient.get<PreferencesResponse>("/notifications/preferences");
        if (cancelled) return;
        setChannels(data.channels);
        setCategories(data.categories);
        setTelegramLinked(data.telegram_linked);
        setTelegramMasked(data.telegram_chat_id_masked);
      } catch {
        if (!cancelled)
          setError("بارگذاری تنظیمات اعلان‌ها ناموفق بود. صفحه را دوباره بارگذاری کنید.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const persist = async (patch: {
    channels?: Record<string, boolean>;
    categories?: Record<string, boolean>;
  }) => {
    const { data } = await apiClient.put<PreferencesResponse>(
      "/notifications/preferences",
      patch
    );
    setChannels(data.channels);
    setCategories(data.categories);
  };

  const toggleChannel = async (key: string) => {
    const next = !channels[key];
    setChannels({ ...channels, [key]: next });
    setSavingKey(`ch:${key}`);
    setSaveMessage(null);
    try {
      await persist({ channels: { [key]: next } });
      setSaveMessage({ ok: true, text: "تنظیمات اعلان‌ها ذخیره شد." });
    } catch {
      setChannels({ ...channels, [key]: !next }); // revert
      setSaveMessage({ ok: false, text: "ذخیره تنظیمات ناموفق بود. دوباره تلاش کنید." });
    } finally {
      setSavingKey(null);
    }
  };

  const toggleCategory = async (key: string) => {
    const next = !categories[key];
    setCategories({ ...categories, [key]: next });
    setSavingKey(`cat:${key}`);
    setSaveMessage(null);
    try {
      await persist({ categories: { [key]: next } });
      setSaveMessage({ ok: true, text: "تنظیمات اعلان‌ها ذخیره شد." });
    } catch {
      setCategories({ ...categories, [key]: !next }); // revert
      setSaveMessage({ ok: false, text: "ذخیره تنظیمات ناموفق بود. دوباره تلاش کنید." });
    } finally {
      setSavingKey(null);
    }
  };

  const handleGenerateLinkCode = async () => {
    setLinkLoading(true);
    setLinkError(null);
    try {
      const { data } = await apiClient.post<LinkCodeResponse>(
        "/notifications/telegram/link-code"
      );
      setLinkCode(data);
    } catch {
      setLinkError("صدور کد اتصال ناموفق بود. دوباره تلاش کنید.");
    } finally {
      setLinkLoading(false);
    }
  };

  const handleRefreshLinkStatus = async () => {
    setLinkLoading(true);
    setLinkError(null);
    try {
      const { data } = await apiClient.get<{
        linked: boolean;
        telegram_chat_id_masked: string | null;
      }>("/notifications/telegram/link-status");
      setTelegramLinked(data.linked);
      setTelegramMasked(data.telegram_chat_id_masked);
      if (data.linked) setLinkCode(null);
    } catch {
      setLinkError("بررسی وضعیت اتصال ناموفق بود.");
    } finally {
      setLinkLoading(false);
    }
  };

  const handleUnlink = async () => {
    setLinkLoading(true);
    setLinkError(null);
    try {
      await apiClient.delete("/notifications/telegram/link");
      setTelegramLinked(false);
      setTelegramMasked(null);
      setLinkCode(null);
    } catch {
      setLinkError("قطع اتصال تلگرام ناموفق بود.");
    } finally {
      setLinkLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm">در حال بارگذاری تنظیمات اعلان‌ها…</span>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 py-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">تنظیمات اعلان‌ها</h1>
          <p className="text-sm text-muted-foreground">
            انتخاب کنید کدام اعلان‌ها از کدام کانال به شما برسد
          </p>
        </div>
        <Link
          href="/account"
          className="flex items-center gap-1 text-sm text-primary hover:underline"
        >
          <ArrowRight className="h-4 w-4" />
          بازگشت به حساب کاربری
        </Link>
      </div>

      {error && (
        <Card className="border-destructive/30 bg-destructive/5 p-4">
          <p className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {error}
          </p>
        </Card>
      )}

      {saveMessage && (
        <p
          className={`flex items-center gap-1.5 text-xs ${
            saveMessage.ok ? "text-emerald-600" : "text-destructive"
          }`}
        >
          {saveMessage.ok ? (
            <CheckCircle2 className="h-3.5 w-3.5" />
          ) : (
            <AlertCircle className="h-3.5 w-3.5" />
          )}
          {saveMessage.text}
        </p>
      )}

      {/* Channels */}
      <Card className="p-6">
        <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
          <Bell className="h-5 w-5 text-primary" />
          <h2 className="text-base font-bold text-foreground">کانال‌های دریافت اعلان</h2>
        </div>
        <div className="space-y-3">
          {CHANNEL_META.map(({ key, label, hint, icon: Icon }) => (
            <div
              key={key}
              className="flex items-center justify-between rounded-lg border border-border/60 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <Icon className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium text-foreground">{label}</p>
                  <p className="text-xs text-muted-foreground">{hint}</p>
                </div>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={Boolean(channels[key])}
                disabled={savingKey === `ch:${key}`}
                onClick={() => void toggleChannel(key)}
                className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
                  channels[key] ? "bg-primary" : "bg-muted"
                } ${savingKey === `ch:${key}` ? "opacity-60" : ""}`}
              >
                <span
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
                    channels[key] ? "right-0.5" : "right-[22px]"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      </Card>

      {/* Categories */}
      <Card className="p-6">
        <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
          <Inbox className="h-5 w-5 text-primary" />
          <h2 className="text-base font-bold text-foreground">نوع اعلان‌ها</h2>
        </div>
        <div className="space-y-3">
          {CATEGORY_META.map(({ key, label }) => (
            <div
              key={key}
              className="flex items-center justify-between rounded-lg border border-border/60 px-4 py-3"
            >
              <p className="text-sm font-medium text-foreground">{label}</p>
              <button
                type="button"
                role="switch"
                aria-checked={Boolean(categories[key])}
                disabled={savingKey === `cat:${key}`}
                onClick={() => void toggleCategory(key)}
                className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
                  categories[key] ? "bg-primary" : "bg-muted"
                } ${savingKey === `cat:${key}` ? "opacity-60" : ""}`}
              >
                <span
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
                    categories[key] ? "right-0.5" : "right-[22px]"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      </Card>

      {/* Browser push (device-level, distinct from the preference toggle) */}
      <BrowserPushCard />

      {/* Telegram linking */}
      <Card className="p-6">
        <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-primary" />
            <h2 className="text-base font-bold text-foreground">اتصال حساب تلگرام</h2>
          </div>
          <Badge variant="outline" className="text-xs">
            {telegramLinked ? `متصل (${telegramMasked || "•••"})` : "متصل نیست"}
          </Badge>
        </div>

        {telegramLinked ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              حساب تلگرام شما متصل است و اعلان‌ها از طریق ربات برایتان ارسال می‌شود.
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void handleUnlink()}
              disabled={linkLoading}
              className="gap-1.5 text-destructive"
            >
              {linkLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Unlink className="h-4 w-4" />
              )}
              قطع اتصال تلگرام
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              برای دریافت اعلان‌ها در تلگرام، کد اتصال بگیرید و آن را برای ربات فروشگاه بفرستید.
              پس از ارسال کد، اتصال توسط پشتیبانی تأیید می‌شود.
            </p>
            {linkCode ? (
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 text-center">
                <p className="mb-1 text-xs text-muted-foreground">کد اتصال شما (۱۰ دقیقه اعتبار):</p>
                <p className="font-mono text-2xl font-bold tracking-[0.3em] text-primary" dir="ltr">
                  {linkCode.code}
                </p>
                {linkCode.bot_deep_link && (
                  <a
                    href={linkCode.bot_deep_link}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 inline-block text-sm text-primary hover:underline"
                    dir="ltr"
                  >
                    {linkCode.bot_deep_link}
                  </a>
                )}
                <p className="mt-2 text-xs text-muted-foreground">
                  این کد را در گفتگو با ربات ارسال کنید و سپس دکمه «بررسی اتصال» را بزنید.
                </p>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                onClick={() => void handleGenerateLinkCode()}
                disabled={linkLoading}
                className="gap-1.5"
              >
                {linkLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Link2 className="h-4 w-4" />
                )}
                {linkCode ? "صدور کد جدید" : "دریافت کد اتصال"}
              </Button>
              {linkCode && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void handleRefreshLinkStatus()}
                  disabled={linkLoading}
                  className="gap-1.5"
                >
                  <RefreshCw className="h-4 w-4" />
                  بررسی اتصال
                </Button>
              )}
            </div>
          </div>
        )}

        {linkError && (
          <p className="mt-3 flex items-center gap-1.5 text-xs text-destructive">
            <AlertCircle className="h-3.5 w-3.5" />
            {linkError}
          </p>
        )}
      </Card>

      <Separator />
      <p className="text-center text-xs text-muted-foreground">
        تغییرات بلافاصله ذخیره می‌شود. غیرفعال‌کردن یک کانال فقط ارسال‌های بعدی را متوقف می‌کند.
      </p>
    </div>
  );
}
