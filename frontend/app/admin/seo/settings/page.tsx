"use client";

/**
 * SEO Settings — the operator-level switches (Rank Math's "Settings" tab,
 * general section only).
 *
 * Deliberately narrow: this page owns the site-wide SEO inputs that have no
 * other home — the canonical origin, the extra robots.txt lines, and the
 * sitemap status read-out. Per-content SEO (titles, descriptions, focus
 * keywords) lives in the editor's SEO panel; schema defaults and title
 * templates belong to the schema/titles wave.
 */

import { useEffect, useState } from "react";
import { CheckCircle2, ExternalLink, Globe, Loader2, Save, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { apiClient } from "@/lib/api/client";

interface RoutingConfig {
  site_url?: string;
  blogname?: string;
}

export default function SeoSettingsPage() {
  const { toast } = useToast();
  const [siteUrl, setSiteUrl] = useState("");
  const [robotsExtra, setRobotsExtra] = useState("");
  const [savedSiteUrl, setSavedSiteUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingUrl, setSavingUrl] = useState(false);
  const [savingRobots, setSavingRobots] = useState(false);
  const [sitemapStatus, setSitemapStatus] = useState<"checking" | "ok" | "fail">("checking");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [routing, robots] = await Promise.all([
          apiClient.get<RoutingConfig>("/settings/public/routing").then((r) => r.data),
          apiClient
            .get<{ extra?: string }>("/settings/public/robots-extra")
            .then((r) => r.data)
            .catch(() => ({ extra: "" })),
        ]);
        if (cancelled) return;
        setSiteUrl(routing.site_url || "");
        setSavedSiteUrl(routing.site_url || "");
        setRobotsExtra(robots.extra || "");
      } finally {
        if (!cancelled) setLoading(false);
      }
      // Sitemap reachability — a HEAD against our own file, so "sitemap is
      // served" is a measured fact on this page, not a promise.
      try {
        const res = await fetch("/sitemap.xml", { method: "HEAD" });
        if (!cancelled) setSitemapStatus(res.ok ? "ok" : "fail");
      } catch {
        if (!cancelled) setSitemapStatus("fail");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const saveSiteUrl = async () => {
    setSavingUrl(true);
    try {
      const value = siteUrl.trim().replace(/\/$/, "");
      await apiClient.put(`/settings/admin/site-options/home`, { value });
      await apiClient.put(`/settings/admin/site-options/siteurl`, { value });
      setSavedSiteUrl(value);
      toast({
        title: "آدرس سایت ذخیره شد",
        description:
          "این آدرس در فیدها، IndexNow و آدرس‌های ساختهٔ سرور استفاده می‌شود. " +
          "کنونیکال و نقشه سایت از متغیر محیطی NEXT_PUBLIC_SITE_URL (frontend/.env) " +
          "ساخته می‌شوند. هنگام انتشار هر دو را روی یک دامنه تنظیم کنید.",
      });
    } catch {
      toast({ title: "ذخیره ناموفق بود", variant: "destructive" });
    } finally {
      setSavingUrl(false);
    }
  };

  const saveRobots = async () => {
    setSavingRobots(true);
    try {
      await apiClient.put(`/settings/admin/site-options/robots_extra_rules`, {
        value: robotsExtra,
      });
      toast({ title: "خطوط robots.txt ذخیره شد" });
    } catch {
      toast({ title: "ذخیره ناموفق بود", variant: "destructive" });
    } finally {
      setSavingRobots(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        در حال خواندن تنظیمات...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black">تنظیمات سئو</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          تنظیمات سراسری سئو. سئوی هر نوشته یا برگه در ویرایشگر خودش است.
        </p>
      </div>

      <Card className="rounded-2xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Globe className="h-4 w-4 text-emerald-600" />
            آدرس سایت (Canonical Origin)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2">
            <Label htmlFor="seo-site-url">آدرس کامل سایت</Label>
            <Input
              id="seo-site-url"
              value={siteUrl}
              onChange={(e) => setSiteUrl(e.target.value)}
              dir="ltr"
              placeholder="https://example.com"
              className="text-left font-mono text-xs"
            />
            <p className="text-[11px] text-muted-foreground">
              این آدرس در فیدها، IndexNow و آدرس‌های ساختهٔ سرور استفاده
              می‌شود. تگ کنونیکال و نقشه سایت از{" "}
              <span dir="ltr">NEXT_PUBLIC_SITE_URL</span> (فایل{" "}
              <span dir="ltr">frontend/.env</span>) می‌آیند؛ این آدرس باید با
              آن یکی باشد. بدون <span dir="ltr">/</span> انتهایی وارد کنید.
            </p>
          </div>
          <Button
            onClick={() => void saveSiteUrl()}
            disabled={savingUrl || !siteUrl.trim() || siteUrl.trim() === savedSiteUrl}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {savingUrl ? <Loader2 className="h-4 w-4 animate-spin ms-1" /> : <Save className="h-4 w-4 ms-1" />}
            ذخیره آدرس
          </Button>
        </CardContent>
      </Card>

      <Card className="rounded-2xl">
        <CardHeader>
          <CardTitle className="text-base">وضعیت نقشه سایت (Sitemap)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 text-sm">
            {sitemapStatus === "checking" && (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                در حال بررسی...
              </>
            )}
            {sitemapStatus === "ok" && (
              <>
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <span>نقشه سایت در حال سرو شدن است.</span>
              </>
            )}
            {sitemapStatus === "fail" && (
              <>
                <XCircle className="h-4 w-4 text-destructive" />
                <span>نقشه سایت پاسخ نداد — مسیر /sitemap.xml را بررسی کنید.</span>
              </>
            )}
          </div>
          <Button variant="outline" size="sm" asChild>
            <a href="/sitemap.xml" target="_blank" rel="noreferrer">
              <ExternalLink className="h-3.5 w-3.5 ms-1" />
              مشاهده نقشه سایت
            </a>
          </Button>
          <p className="text-[11px] text-muted-foreground">
            نقشه سایت خودکار ساخته می‌شود و نوشته‌ها، برگه‌ها، دسته‌ها،
            برچسب‌ها و آرشیوها را شامل می‌شود.
          </p>
        </CardContent>
      </Card>

      <Card className="rounded-2xl">
        <CardHeader>
          <CardTitle className="text-base">خطوط اضافی robots.txt</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2">
            <Label htmlFor="seo-robots-extra">دستورهای اضافی</Label>
            <Textarea
              id="seo-robots-extra"
              value={robotsExtra}
              onChange={(e) => setRobotsExtra(e.target.value)}
              dir="ltr"
              rows={5}
              placeholder={"Disallow: /private/\nAllow: /private/public/"}
              className="text-left font-mono text-xs"
            />
            <p className="text-[11px] text-muted-foreground">
              این خطوط بعد از قوانین خودکار به robots.txt اضافه می‌شوند.
            </p>
          </div>
          <Button
            onClick={() => void saveRobots()}
            disabled={savingRobots}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {savingRobots ? <Loader2 className="h-4 w-4 animate-spin ms-1" /> : <Save className="h-4 w-4 ms-1" />}
            ذخیره خطوط robots
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
