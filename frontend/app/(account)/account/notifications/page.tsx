"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Bell,
  Smartphone,
  Inbox,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowRight,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import apiClient from "@/lib/api/client";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type PreferencesResponse = {
  channels: Record<string, boolean>;
  categories: Record<string, boolean>;
};

const CHANNEL_META: Array<{
  key: string;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { key: "in_app", label: "اعلان درون‌برنامه‌ای", hint: "نمایش در پنل کاربری", icon: Inbox },
  { key: "sms", label: "پیامک", hint: "ارسال به شماره موبایل حساب", icon: Smartphone },
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
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await apiClient.get<PreferencesResponse>("/notifications/preferences");
        if (cancelled) return;
        setChannels(data.channels);
        setCategories(data.categories);
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

      <Separator />
      <p className="text-center text-xs text-muted-foreground">
        تغییرات بلافاصله ذخیره می‌شود. غیرفعال‌کردن یک کانال فقط ارسال‌های بعدی را متوقف می‌کند.
      </p>
    </div>
  );
}
