"use client";

/**
 * Site identity: name, tagline, admin email, and search-engine visibility.
 *
 * P0 "تنظیمات: نام سایت، توضیح سایت و ایمیل ادمین از UI" and "نمایش/پنهان‌سازی
 * سایت از موتورهای جست‌وجو". All four keys were seeded, read by the feed, the
 * sitemap and the robots route, and written by nothing — so the store's name
 * in a feed could not be changed and the admin address for system mail was a
 * placeholder nobody could correct.
 *
 * The API and the typed client for these already existed
 * (`PUT /settings/admin/site-options/{key}`); only the screen was missing,
 * which is why the gap is a UI one rather than a backend one.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Globe, Save, ArrowLeft } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";
import { cmsPagesAdminApi } from "@/lib/api/content";
import { useAdminMutation } from "@/lib/api/admin-query";

const KEYS = {
  blogname: "blogname",
  blogdescription: "blogdescription",
  showOnFront: "show_on_front",
  pageOnFront: "page_on_front",
} as const;

export function SiteIdentityCard() {
  const { toast } = useToast();
  const runMutation = useAdminMutation();
  const [saving, setSaving] = useState(false);

  const [siteName, setSiteName] = useState("");
  const [tagline, setTagline] = useState("");
  // Static front page: the storefront already asks /public/front-page whether a
  // page is pinned to "/", but no screen could set one — the backend handled a
  // stale slug correctly and nothing could ever create a fresh one.
  const [showOnFront, setShowOnFront] = useState<"posts" | "page">("posts");
  const [pageOnFront, setPageOnFront] = useState("");
  const [pages, setPages] = useState<Array<{ id: string; title: string; slug: string }>>([]);

  const load = useCallback(async () => {
    try {
      const opts = await siteOptionsApi.list();
      setSiteName(opts[KEYS.blogname] ?? "");
      setTagline(opts[KEYS.blogdescription] ?? "");
      setShowOnFront((opts[KEYS.showOnFront] ?? "posts") === "page" ? "page" : "posts");
      setPageOnFront(opts[KEYS.pageOnFront] ?? "");
    } catch {
      toast({ title: "خواندن تنظیمات سایت ناموفق بود", variant: "destructive" });
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // Only published pages can be pinned: the resolver degrades to the default
  // home when the chosen page is gone, so offering a draft here would produce a
  // setting that silently does nothing.
  useEffect(() => {
    let cancelled = false;
    cmsPagesAdminApi
      .listPages({ status: "published" })
      .then((res) => {
        if (cancelled) return;
        setPages(
          res.items.map((p) => ({ id: p.id, title: p.title, slug: p.slug })),
        );
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const save = async () => {
    if (!siteName.trim()) {
      toast({ title: "نام سایت نمی‌تواند خالی باشد", variant: "destructive" });
      return;
    }
    setSaving(true);
    // Saved one key per request because that is the shape the API takes. The
    // alternative — a bulk endpoint — would need one for every option screen,
    // and only this screen needs four.
    const writes: Array<[string, string]> = [
      [KEYS.blogname, siteName.trim()],
      [KEYS.blogdescription, tagline.trim()],
      [KEYS.showOnFront, showOnFront],
      // An empty string is the honest value for "no page chosen"; the resolver
      // reads it as "fall back to the default home".
      [KEYS.pageOnFront, showOnFront === "page" ? pageOnFront : ""],
    ];
    for (const [key, value] of writes) {
      const result = await runMutation(() => siteOptionsApi.set(key, value), {
        fallbackError: "ذخیره تنظیمات ناموفق بود",
      });
      if (!result.ok) {
        setSaving(false);
        toast({ title: result.error, variant: "destructive" });
        return;
      }
    }
    setSaving(false);
    toast({ title: "هویت سایت ذخیره شد" });
    // Re-read rather than trusting local state: the feed, sitemap and robots
    // all read these values, so the operator should see what was actually kept.
    await load();
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <Globe className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">هویت سایت</h2>
      </div>

      <p className="mb-4 text-xs text-muted-foreground">
        این مقادیر در فید RSS، نقشه‌ی سایت و عنوان صفحات خوانده می‌شوند؛ با ذخیره، بلافاصله
        در خروجی‌های عمومی اعمال می‌شوند.
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="site-name">نام سایت</Label>
          <Input
            id="site-name"
            value={siteName}
            onChange={(e) => setSiteName(e.target.value)}
            placeholder="نام فروشگاه"
            // WordPress fa_IR parity: the admin is RTL, so its text fields
            // are right-aligned whatever the value is. dir="auto" flipped an
            // empty or Latin-valued field to LTR and the Persian text sat at
            // the left edge — hence the explicit rtl here.
            dir="rtl"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="site-tagline">توضیح کوتاه</Label>
          <Input
            id="site-tagline"
            value={tagline}
            onChange={(e) => setTagline(e.target.value)}
            placeholder="یک جمله درباره فروشگاه"
            dir="rtl"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="front-page-mode">صفحهٔ نخست</Label>
          <select
            id="front-page-mode"
            value={showOnFront}
            onChange={(e) => setShowOnFront(e.target.value as "posts" | "page")}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="posts">آخرین نوشته‌ها</option>
            <option value="page">یک برگهٔ ثابت</option>
          </select>
          {showOnFront === "page" && pages.length === 0 && (
            <p className="text-xs text-amber-600">
              هیچ برگهٔ منتشرشده‌ای وجود ندارد؛ ابتدا یک برگه منتشر کنید.
            </p>
          )}
        </div>

        {showOnFront === "page" && (
          <div className="space-y-2">
            <Label htmlFor="front-page-slug">برگهٔ نخست</Label>
            <select
              id="front-page-slug"
              value={pageOnFront}
              onChange={(e) => setPageOnFront(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">انتخاب کنید</option>
              {pages.map((pg) => (
                <option key={pg.id} value={pg.slug}>
                  {pg.title} ({pg.slug})
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              این برگه به‌جای خانهٔ فروشگاه در نشانی «/» نمایش داده می‌شود. اگر برگه
              حذف یا از انتشار خارج شود، خانهٔ پیش‌فرض برمی‌گردد.
            </p>
          </div>
        )}

        <div className="space-y-2 sm:col-span-2">
          <Label>نمایش در موتورهای جست‌وجو</Label>
          {/* The switch itself moved to SEO → Search visibility (owner
              request: one write path for blog_public). This screen links
              there instead of carrying a second copy that could drift. */}
          <Link
            href="/admin/seo/visibility"
            className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 text-sm transition-colors hover:bg-muted"
          >
            <span className="text-muted-foreground">
              این تنظیم به بخش سئو منتقل شد
            </span>
            <span className="flex items-center gap-1 text-xs font-medium text-primary">
              مدیریت در سئو
              <ArrowLeft className="h-3.5 w-3.5" />
            </span>
          </Link>
          <p className="text-xs text-muted-foreground">
            مجاز یا پنهان‌کردن کل سایت برای خزنده‌ها در منوی سئو مدیریت می‌شود.
          </p>
        </div>
      </div>

      <div className="mt-5 flex justify-end">
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 ms-1" />
          {saving ? "در حال ذخیره..." : "ذخیره هویت سایت"}
        </Button>
      </div>
    </Card>
  );
}

export default SiteIdentityCard;
