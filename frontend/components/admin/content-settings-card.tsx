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
  /** Returns false when the typed value should not be saved. */
  validate?: (value: string) => boolean;
  invalidHint?: string;
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
    key: "post_revisions_to_keep",
    label: "تعداد نسخه‌های نگه‌داشته‌شده برای هر نوشته",
    placeholder: "20",
    dir: "ltr",
    hint: "نسخه‌های قدیمی‌تر از این تعداد خودکار حذف می‌شوند. عدد ۱- یعنی «همه را نگه دار» و هرس را خاموش می‌کند.",
  },
  {
    key: "embed_cache_ttl_hours",
    label: "مدت کش شدن پیش‌نمایش لینک (ساعت)",
    placeholder: "168",
    dir: "ltr",
    hint: "نتیجهٔ oEmbed/Open Graph هر لینک این مدت کش می‌شود. اگر ارائه‌دهنده‌ای قالبش را عوض کرد، مقدار را کمتر کنید تا سریع‌تر به‌روز شود. بین ۱ و ۷۲۰ ساعت.",
  },
  {
    key: "embed_allowed_hosts",
    label: "دامنه‌های مجاز برای پیش‌نمایش لینک",
    placeholder: "youtube.com, aparat.com",
    dir: "ltr",
    hint: "با کاما جدا کنید. خالی = همهٔ دامنه‌ها. دامنه‌های خارج از این فهرست فقط کارت لینک (OG) می‌گیرند، نه پیش‌نمایش کامل؛ گارد SSRF همیشه اعمال می‌شود.",
  },
  {
    key: "moderation_keys",
    label: "کلیدواژه‌های تعدیل",
    placeholder: "کازینو، ارز دیجیتال",
    dir: "ltr",
    hint: "با کاما جدا کنید. دیدگاهی که شامل یکی از این‌ها باشد برای بررسی نگه داشته می‌شود.",
  },
  {
    key: "disallowed_keys",
    label: "کلیدواژه‌های ممنوع",
    placeholder: "پورتال، بوت‌کرپ",
    dir: "ltr",
    hint: "دیدگاهی که شامل یکی از این‌ها باشد اصلاً ثبت نمی‌شود.",
  },
  {
    key: "comments_notify",
    label: "ایمیل به نویسنده هنگام دیدگاه تازه",
    placeholder: "1",
    dir: "ltr",
    hint: "۱ = نویسنده هر دیدگاه را ایمیل می‌گیرد (با Reply-To روی آدرس خود دیدگاه‌دهنده).",
  },
  {
    key: "moderation_notify",
    label: "ایمیل به مدیران هنگام دیدگاه در انتظار بررسی",
    placeholder: "1",
    dir: "ltr",
    hint: "۱ = وقتی دیدگاهی منتظر بررسی است، مدیران مطلع می‌شوند.",
  },
  {
    key: "close_comments_days_old",
    label: "بستن دیدگاه روی محتوای قدیمی (روز)",
    placeholder: "0",
    dir: "ltr",
    hint: "۰ = هرگز بسته نشود. مثلاً ۳۰ یعنی روی نوشته یا برگه‌ای که بیش از ۳۰ روز از انتشارش گذشته، دیدگاه تازه پذیرفته نمی‌شود.",
  },
  {
    key: "comment_order",
    label: "ترتیب نمایش دیدگاه‌ها",
    placeholder: "asc",
    dir: "ltr",
    hint: "asc = قدیمی‌ها اول (مثل یک گفتگو). desc = تازه‌ها اول. روی پاسخ‌های داخل هر دیدگاه هم اعمال می‌شود.",
  },
  {
    key: "comment_previously_approved",
    label: "تأیید خودکار دیدگاه‌دهنده‌ی قبلاً تأییدشده",
    placeholder: "0",
    dir: "ltr",
    hint: "۰ = همه‌ی دیدگاه‌های مهمان در صف بررسی می‌مانند. ۱ = کسی که پیش‌تر دیدگاه تأییدشده داشته، بدون بررسی منتشر می‌شود. تطبیق با ایمیل انجام می‌شود (و برای مهمان، نام هم باید یکی باشد) — نشانی‌ای که شامل کلید تعدیل باشد همچنان صف می‌ماند.",
  },
  {
    key: "require_name_email",
    label: "الزام نام و ایمیل برای دیدگاه مهمان",
    placeholder: "0",
    dir: "ltr",
    hint: "۰ = مهمان بدون نام هم می‌تواند دیدگاه بگذارد. ۱ = بدون نام و ایمیل ثبت نمی‌شود (سمت سرور اعمال می‌شود، نه فقط فرم).",
  },
  {
    key: "comments_per_hour",
    label: "سقف دیدگاه در ساعت (هر نشانی)",
    placeholder: "5",
    dir: "ltr",
    hint: "۰ یعنی این سقف خاموش است. کنترل سیل ۱۵ ثانیه‌ای جداگانه همچنان کار می‌کند.",
  },
  {
    key: "comments_per_day",
    label: "سقف دیدگاه در روز (هر نشانی)",
    placeholder: "20",
    dir: "ltr",
    hint: "۰ یعنی خاموش. این سقف جلوی رباتی را می‌گیرد که هر دقیقه یکی می‌فرستد.",
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
  // Akismet, the external half of the spam decision. An empty key is a real,
  // supported state and not a misconfiguration: no key means no call is made
  // and the local filter decides alone — WordPress's own behaviour without a
  // key — so the field has to say so rather than implying one is owed.
  {
    key: "spam_akismet_api_key",
    label: "کلید API سرویس Akismet",
    placeholder: "",
    dir: "ltr",
    hint: "خالی = سرویس بیرونی خاموش؛ فیلتر محلی تنها تصمیم می‌گیرد و متن دیدگاه شما به Akismet فرستاده نمی‌شود — همان رفتار وردپرس بدون کلید. با کلید، Akismet نظر می‌دهد و تصمیم میانجی شما به‌عنوان بازخورد به آن برمی‌گردد.",
  },
  {
    key: "spam_akismet_api_url",
    label: "نشانی سرویس Akismet (اختیاری)",
    placeholder: "https://akismet.internal/1.1/",
    dir: "ltr",
    hint: "برای Akismet خودمیزبان. خالی = سرویس عمومی akismet.com. برای فروشگاهی که نمی‌خواهد متن دیدگاه‌ها به بیرون برود، این نشانی را پر کنید.",
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
  // Upload ceilings. These were module constants, so raising the video limit
  // needed a code change and a redeploy; the backend reads them per upload and
  // falls back to 10/100 MB when a row is missing or unreadable.
  {
    key: "media_max_file_size_mb",
    label: "حداکثر حجم آپلود تصویر و PDF (مگابایت)",
    placeholder: "10",
    dir: "ltr",
    hint: "پیش‌فرض ۱۰. بیشتر از ۲۰۴۸ نادیده گرفته می‌شود.",
  },
  // Date and time presentation. These were seeded and never read: lib/date.ts
  // hardcoded the pattern and the zone, so changing them here did nothing. The
  // values are PHP date() formats, translated to the formatter's vocabulary in
  // lib/date-settings.ts.
  // The content language registry. Read by GET /settings/public/routing, which
  // every storefront page already calls; there was no UI, so the two options
  // had no way to be anything but the seeded values.
  {
    key: "enabled_locales",
    label: "زبان‌های فعال محتوا",
    placeholder: "fa",
    dir: "ltr",
    hint: "با کاما جدا کنید. نمونه: fa,en — فقط این زبان‌ها در فیلترها و مسیرها پیشنهاد می‌شوند.",
    validate: (v) =>
      v.trim() === "" ||
      v
        .split(",")
        .map((x) => x.trim())
        .every((x) => /^[a-z]{2}(-[A-Za-z]{2,8})?$/.test(x) && x.length > 1),
    invalidHint: "هر زبان باید کد دوتایی باشد، مثل fa یا en (خالی مجاز است).",
  },
  {
    key: "default_locale",
    label: "زبان پیش‌فرض",
    placeholder: "fa",
    dir: "ltr",
    hint: "زبانی که وقتی مسیر مشخصی نداریم استفاده می‌شود.",
    validate: (v) => v.trim() === "" || /^[a-z]{2}(-[A-Za-z]{2,8})?$/.test(v.trim()),
    invalidHint: "کد زبان باید دوتایی باشد، مثل fa.",
  },
  // Where a new post starts. Read by BlogService.create_post, so it applies to
  // an API client too and not only to the admin form.
  {
    key: "default_category",
    label: "دسته‌ی پیش‌فرض نوشته‌ها",
    placeholder: "اخبار",
    dir: "ltr",
    hint: "نامک (slug) دسته. خالی = بدون دسته؛ نوشته‌ی جدید با دسته‌ی پیش‌فرض ساخته می‌شود.",
  },
  {
    key: "default_post_format",
    label: "فرمت پیش‌فرض نوشته",
    placeholder: "standard",
    dir: "ltr",
    hint: "standard، gallery، video، audio، quote، link، status یا image.",
  },
  {
    key: "date_format",
    label: "قالب نمایش تاریخ",
    placeholder: "Y/m/d",
    dir: "ltr",
    hint: "قالب PHP. نمونه‌ها: Y/m/d یا d/m/Y — به تاریخ شمسی تبدیل می‌شود.",
  },
  {
    key: "time_format",
    label: "قالب نمایش ساعت",
    placeholder: "H:i",
    dir: "ltr",
    hint: "قالب PHP ۲۴ ساعته. H:i یعنی ۱۴:۳۰.",
  },
  {
    key: "timezone_string",
    label: "منطقه‌ی زمانی فروشگاه",
    placeholder: "Asia/Tehran",
    dir: "ltr",
    hint: "منطقه‌ی زمانی IANA. تاریخ‌ها در این منطقه نمایش داده می‌شوند.",
  },
  {
    key: "media_max_media_file_size_mb",
    label: "حداکثر حجم آپلود صدا و ویدیو (مگابایت)",
    placeholder: "100",
    dir: "ltr",
    hint: "پیش‌فرض ۱۰۰. بیشتر از ۲۰۴۸ نادیده گرفته می‌شود.",
  },
];

export function ContentSettingsCard() {
  const { toast } = useToast();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  // Distinct from `loading`: a fetch that finished and found nothing is a very
  // different thing from one that never came back, and only the second must
  // block a write.
  const [loadFailed, setLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadFailed(false);
    try {
      const all = await siteOptionsApi.list();
      const next: Record<string, string> = {};
      for (const opt of CONTENT_OPTIONS) {
        next[opt.key] = all[opt.key] ?? "";
      }
      setValues(next);
    } catch {
      setLoadFailed(true);
      toast({ title: "بارگذاری تنظیمات محتوا ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSave = async () => {
    // Refuse to write while a load is in flight or after one failed. `values`
    // is empty in both states, and the save persists `values[key] || null` for
    // every option — so without this, a save right after a failed fetch wipes
    // every setting on the card, including the Akismet key.
    if (loading || loadFailed) {
      toast({
        title: "ابتدا تنظیمات باید با موفقیت بارگذاری شود",
        variant: "destructive",
      });
      return;
    }
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
                {/* Inline validation, because the hint above is advice and this
                    is the check: saving "fa,,en" or "farsi" makes the locale
                    filter on the storefront offer something no page can serve. */}
                {opt.validate && !opt.validate(values[opt.key] ?? "") && (
                  <p className="text-[11px] text-destructive">{opt.invalidHint}</p>
                )}
              </div>
            ))}
          </div>

          <div className="mt-5 flex justify-end">
            <Button
              onClick={() => void handleSave()}
              disabled={saving || loading || loadFailed}
            >
              <Save className="h-4 w-4" />
              {saving ? "در حال ذخیره…" : "ذخیره تنظیمات محتوا"}
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
