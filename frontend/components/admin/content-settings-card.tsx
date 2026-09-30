"use client";

/**
 * Content settings card (WordPress reading/permalink parity).
 *
 * Edits the site_options rows that control content behavior: posts per page,
 * excerpt length, permalink structure, comment defaults, and media sizes.
 * Values are stored server-side and consumed by the blog and storefront.
 */

import { useCallback, useEffect, useState } from "react";
import { Settings2, Save, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";

// Keys this card owns, with Persian labels and input hints.
// permalink_structure/category_base/tag_base are LIVE: the backend RSS feed
// and the public routing endpoint consume them, and the middleware resolves
// the structured paths (see the delivery report for the resolution wiring).
const CONTENT_OPTIONS: Array<{
  key: string;
  label: string;
  placeholder?: string;
  dir?: "ltr" | "rtl";
  hint?: string;
  readOnly?: boolean;
}> = [
  {
    key: "posts_per_page",
    label: "تعداد نوشته در هر صفحه",
    placeholder: "10",
    dir: "ltr",
  },
  {
    key: "posts_per_rss",
    label: "تعداد آیتم در فید RSS",
    placeholder: "20",
    dir: "ltr",
  },
  {
    key: "excerpt_length",
    label: "طول خلاصه (تعداد کلمه)",
    placeholder: "55",
    dir: "ltr",
  },
  {
    key: "excerpt_more",
    label: "متن ادامه خلاصه",
    placeholder: "...",
  },
  {
    key: "permalink_structure",
    label: "ساختار پیوند یکتا",
    placeholder: "/blog/%postname%/",
    dir: "ltr",
    hint: "تگ‌ها: %postname% %post_id% %year% %monthnum% %day% %category% %author% — لینک‌های فروشگاه، فید RSS و sitemap از همین ساختار ساخته می‌شوند و مسیرهای قدیمی /blog/<اسلاگ> همچنان کار می‌کنند.",
  },
  {
    key: "category_base",
    label: "پیشوند دسته‌بندی",
    placeholder: "category",
    dir: "ltr",
    hint: "مثلاً «موضوع» آرشیو دسته را به /موضوع/<اسلاگ> منتقل می‌کند.",
  },
  {
    key: "tag_base",
    label: "پیشوند برچسب",
    placeholder: "tag",
    dir: "ltr",
  },
  {
    key: "default_comment_status",
    label: "وضعیت پیش‌فرض دیدگاه‌ها",
    placeholder: "open",
    dir: "ltr",
    hint: "open = باز، closed = بسته",
  },
  {
    key: "comments_per_page",
    label: "تعداد دیدگاه در هر صفحه",
    placeholder: "20",
    dir: "ltr",
  },
  {
    key: "thread_comments_depth",
    label: "حداکثر عمق پاسخ‌های تودرتو",
    placeholder: "3",
    dir: "ltr",
  },
  {
    key: "comment_registration",
    label: "ثبت دیدگاه فقط با حساب کاربری",
    placeholder: "0",
    dir: "ltr",
    hint: "0 = مهمان‌ها هم می‌توانند دیدگاه بدهند، 1 = فقط کاربران واردشده",
  },
  {
    key: "comment_moderation",
    label: "بررسی همهٔ دیدگاه‌ها پیش از انتشار",
    placeholder: "1",
    dir: "ltr",
    hint: "1 = هر دیدگاه (حتی از کاربر واردشده) تا تأیید شما در صف بماند؛ 0 = دیدگاه کاربران واردشده خودکار منتشر می‌شود. روی همهٔ صفحات و نوشته‌ها اثر دارد.",
  },
  {
    key: "comment_max_links",
    label: "حداکثر پیوند در هر دیدگاه",
    placeholder: "2",
    dir: "ltr",
    hint: "0 = هیچ پیوندی مجاز نیست. بیشتر از این تعداد، دیدگاه پذیرفته نمی‌شود.",
  },
  {
    key: "site_icon",
    label: "آیکون سایت (favicon)",
    placeholder: "/uploads/media/…",
    dir: "ltr",
    hint: "آدرس تصویر انتخاب‌شده از کتابخانه مدیا؛ خالی = آیکون پیش‌فرض فروشگاه",
  },
  {
    key: "blog_public",
    label: "نمایش وبلاگ در موتورهای جست‌وجو",
    placeholder: "1",
    dir: "ltr",
    hint: "0 = صفحات وبلاگ با noindex سرو می‌شوند (ساختار کل سایت حفظ می‌شود، فقط ایندکس نمی‌شود)",
  },
];

export function ContentSettingsCard() {
  const { toast } = useToast();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const all = await siteOptionsApi.list();
      const next: Record<string, string> = {};
      for (const opt of CONTENT_OPTIONS) {
        next[opt.key] = all[opt.key] ?? "";
      }
      setValues(next);
    } catch {
      toast({ title: "بارگذاری تنظیمات محتوا ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await Promise.all(
        // Read-only rows are shown for reference; persisting them would imply
        // they drive behaviour, which they do not.
        CONTENT_OPTIONS.filter((opt) => !opt.readOnly).map((opt) =>
          siteOptionsApi.set(opt.key, values[opt.key] || null),
        ),
      );
      toast({ title: "تنظیمات محتوا ذخیره شد" });
    } catch {
      toast({ title: "ذخیره تنظیمات ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleSeed = async () => {
    setSeeding(true);
    try {
      const res = await siteOptionsApi.seedDefaults();
      toast({ title: `${res.seeded} تنظیم پیش‌فرض اضافه شد` });
      await load();
    } catch {
      toast({ title: "افزودن پیش‌فرض‌ها ناموفق بود", variant: "destructive" });
    } finally {
      setSeeding(false);
    }
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Settings2 className="h-5 w-5 text-primary" />
          <h2 className="text-base font-bold text-foreground">تنظیمات محتوا و پیوند</h2>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void handleSeed()} disabled={seeding}>
            {seeding ? "…" : "افزودن پیش‌فرض‌ها"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {loading ? (
        <p className="py-6 text-center text-xs text-muted-foreground">در حال بارگذاری…</p>
      ) : (
        <>
          {/* WordPress-style structure presets — picking one fills the
              permalink_structure input; custom structures stay free-form. */}
          <div className="mb-5 space-y-2">
            <Label className="text-xs">ساختارهای آماده (وردپرسی)</Label>
            <div className="flex flex-wrap gap-2">
              {[
                { label: "نام نوشته", value: "/blog/%postname%/" },
                { label: "سال و نام", value: "/%year%/%monthnum%/%postname%/" },
                { label: "روز، ماه و نام", value: "/%year%/%monthnum%/%day%/%postname%/" },
                { label: "عددی", value: "/archives/%post_id%" },
                { label: "دسته و نام", value: "/blog/%category%/%postname%/" },
              ].map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  onClick={() =>
                    setValues((prev) => ({ ...prev, permalink_structure: preset.value }))
                  }
                  className={`rounded-full border px-3 py-1 text-[11px] transition-colors ${
                    values.permalink_structure === preset.value
                      ? "border-primary bg-primary/10 font-medium text-primary"
                      : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
                  }`}
                >
                  {preset.label}
                  <span className="ms-1.5 font-mono text-[10px]" dir="ltr">
                    {preset.value}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CONTENT_OPTIONS.map((opt) => (
              <div key={opt.key} className="space-y-2">
                <Label htmlFor={`opt-${opt.key}`}>{opt.label}</Label>
                <Input
                  id={`opt-${opt.key}`}
                  value={values[opt.key] ?? ""}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [opt.key]: e.target.value }))
                  }
                  placeholder={opt.placeholder}
                  dir={opt.dir}
                  readOnly={opt.readOnly}
                  aria-readonly={opt.readOnly || undefined}
                  disabled={opt.readOnly}
                  className={
                    (opt.dir === "ltr" ? "text-left font-mono text-xs " : "") +
                    (opt.readOnly ? "bg-muted" : "")
                  }
                />
                {opt.hint && (
                  <p className="text-[11px] text-muted-foreground">{opt.hint}</p>
                )}
              </div>
            ))}
          </div>

          <div className="mt-5 flex justify-end">
            <Button onClick={() => void handleSave()} disabled={saving}>
              <Save className="h-4 w-4" />
              {saving ? "در حال ذخیره…" : "ذخیره تنظیمات محتوا"}
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
