"use client";

/**
 * Breadcrumbs card (Rank Math Pro parity: the Breadcrumbs panel).
 *
 * The storefront renders every trail — visible nav and BreadcrumbList
 * JSON-LD — from these settings (backend: shared/content/breadcrumbs.py),
 * so what the operator sets here is exactly what readers and crawlers see.
 */

import { useCallback, useEffect, useState } from "react";
import { Milestone, Save } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";
import { useAdminMutation } from "@/lib/api/admin-query";

export function BreadcrumbSettingsCard() {
  const { toast } = useToast();
  const runMutation = useAdminMutation();
  const [saving, setSaving] = useState(false);
  const [homeLabel, setHomeLabel] = useState("خانه");
  const [separator, setSeparator] = useState("/");
  const [showBlog, setShowBlog] = useState(true);

  const load = useCallback(async () => {
    try {
      const opts = await siteOptionsApi.list();
      setHomeLabel(opts.seo_breadcrumb_home_label ?? "خانه");
      setSeparator(opts.seo_breadcrumb_separator ?? "/");
      setShowBlog((opts.seo_breadcrumb_show_blog ?? "1") !== "0");
    } catch {
      toast({ title: "خواندن تنظیمات مسیر ناموفق بود", variant: "destructive" });
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    const pairs: Array<[string, string]> = [
      ["seo_breadcrumb_home_label", homeLabel.trim() || "خانه"],
      ["seo_breadcrumb_separator", separator.trim() || "/"],
      ["seo_breadcrumb_show_blog", showBlog ? "1" : "0"],
    ];
    for (const [key, value] of pairs) {
      const result = await runMutation(() => siteOptionsApi.set(key, value), {
        fallbackError: "ذخیره تنظیمات مسیر ناموفق بود",
      });
      if (!result.ok) {
        setSaving(false);
        toast({ title: result.error, variant: "destructive" });
        return;
      }
    }
    setSaving(false);
    toast({ title: "تنظیمات مسیر ذخیره شد" });
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <Milestone className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">مسیر صفحه (Breadcrumbs)</h2>
      </div>

      <p className="mb-4 text-xs text-muted-foreground">
        مسیری که بالای نوشته‌ها و محصولات نمایش داده می‌شود — و همان مسیر در
        داده‌های ساخت‌یافته (BreadcrumbList) گوگل ثبت می‌شود.
      </p>

      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="bc-home">متن اولین مسیر (خانه)</Label>
            <Input
              id="bc-home"
              value={homeLabel}
              onChange={(e) => setHomeLabel(e.target.value)}
              placeholder="خانه"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="bc-sep">جداکنندهٔ نمایشی</Label>
            <Input
              id="bc-sep"
              dir="ltr"
              value={separator}
              onChange={(e) => setSeparator(e.target.value)}
              placeholder="/"
              className="w-24"
            />
          </div>
        </div>

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={showBlog}
            onChange={(e) => setShowBlog(e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-input"
          />
          <span>
            <span className="block text-sm font-medium">نمایش «وبلاگ» در مسیر نوشته‌ها</span>
            <span className="block text-xs text-muted-foreground">
              با خاموش‌کردن، مسیر نوشته‌ها به شکل خانه ← دسته‌بندی ← نوشته می‌شود.
            </span>
          </span>
        </label>
      </div>

      <div className="mt-5 flex justify-end">
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 ms-1" />
          {saving ? "در حال ذخیره..." : "ذخیره تنظیمات مسیر"}
        </Button>
      </div>
    </Card>
  );
}

export default BreadcrumbSettingsCard;
