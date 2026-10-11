"use client";

/**
 * SEO dashboard — the SEO menu's landing panel (Rank Math's "Dashboard").
 *
 * This replaces the old /admin/seo scoring page, which the owner removed
 * ("تحلیل سئو … اصن کار نمیکنه و ناقصه"). The scoring engine itself was
 * not removed: it runs live inside the blog editor's SEO panel
 * (`post-seo-panel.tsx`), where the writer actually needs it. This page is
 * the overview an operator opens to see the state of the site's SEO at a
 * glance — counts, not another analyzer form.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  FileSearch,
  Loader2,
  Search,
  Signpost,
  Sparkles,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { fetchSeoDashboard, type SeoDashboard } from "@/lib/api/seo";
import { toPersianDigits } from "@/lib/utils";

export default function SeoDashboardPage() {
  const [data, setData] = useState<SeoDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const d = await fetchSeoDashboard();
        if (!cancelled) setData(d);
      } catch {
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        در حال خواندن وضعیت سئو...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-2xl border border-destructive/40 bg-destructive/5 p-6 text-sm">
        <p className="flex items-center gap-2 font-bold text-destructive">
          <AlertTriangle className="h-4 w-4" />
          خواندن وضعیت سئو ناموفق بود
        </p>
        <p className="mt-2 text-muted-foreground">
          اتصال به سرور را بررسی کنید و صفحه را دوباره باز کنید.
        </p>
      </div>
    );
  }

  const tiles = [
    {
      label: "ریدایرکت‌های فعال",
      value: data.redirects_active,
      sub: `از ${toPersianDigits(String(data.redirects_total))} قانون`,
      href: "/admin/redirects",
      icon: Signpost,
    },
    {
      label: "مسیرهای ۴۰۴",
      value: data.not_found_distinct_paths,
      sub: `${toPersianDigits(String(data.not_found_total_hits))} بازدید کل`,
      href: "/admin/seo/404",
      icon: FileSearch,
      warn: data.not_found_distinct_paths > 0,
    },
    {
      label: "۴۰۴ در ۷ روز اخیر",
      value: data.not_found_paths_last_7_days,
      sub: "مسیرهای تازه دیده‌شده",
      href: "/admin/seo/404",
      icon: AlertTriangle,
      warn: data.not_found_paths_last_7_days > 0,
    },
    {
      label: "نوشته‌های دارای سئو",
      value: data.blog_posts_with_seo,
      sub:
        data.blog_posts_missing_seo > 0
          ? `${toPersianDigits(String(data.blog_posts_missing_seo))} نوشته بدون تنظیمات سئو`
          : "همه نوشته‌ها تنظیم شده‌اند",
      href: "/admin/blog",
      icon: Sparkles,
      warn: data.blog_posts_missing_seo > 0,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black">داشبورد سئو</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          نمای کلی وضعیت سئوی فروشگاه. برای امتیاز و پیشنهادهای هر مقاله، از
          ویرایشگر همان مقاله استفاده کنید.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {tiles.map((t) => (
          <Link key={t.label} href={t.href} className="group">
            <Card className="h-full rounded-2xl transition-colors group-hover:border-primary/50">
              <CardContent className="flex h-full flex-col gap-3 p-5">
                <div className="flex items-center justify-between">
                  <span
                    className={
                      "flex h-9 w-9 items-center justify-center rounded-xl " +
                      (t.warn
                        ? "bg-amber-500/15 text-amber-600"
                        : "bg-emerald-500/10 text-emerald-600")
                    }
                  >
                    <t.icon className="h-4 w-4" />
                  </span>
                  <ArrowLeft className="h-4 w-4 text-muted-foreground transition-transform group-hover:-translate-x-1" />
                </div>
                <div>
                  <p className="text-2xl font-black tabular-nums">
                    {toPersianDigits(String(t.value))}
                  </p>
                  <p className="text-sm font-medium">{t.label}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{t.sub}</p>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <Card className="rounded-2xl">
        <CardContent className="flex items-start gap-3 p-5 text-sm text-muted-foreground">
          <Search className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          <p>
            امتیاز زندهٔ سئو هر مقاله در ویرایشگر آن است (بخش «سئو»). آنجا کلمه
            کلیدی کانونی، عنوان سئو و توضیحات متا را تنظیم می‌کنید و امتیاز
            ۰ تا ۱۰۰ با پیشنهادهای بهبود نمایش داده می‌شود.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
