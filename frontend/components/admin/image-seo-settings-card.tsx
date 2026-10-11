"use client";

/**
 * Image SEO card (Rank Math Pro parity: the Image SEO module).
 *
 * Rank Math rewrites missing alt/title at render time; this store keeps the
 * values on the media row, so the equivalent settings drive the upload path
 * (backend: media/application/image_seo_service.py). The card edits the same
 * site options that service reads — one write, applied to the next upload.
 */

import { useCallback, useEffect, useState } from "react";
import { ImageIcon, Save } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";
import { useAdminMutation } from "@/lib/api/admin-query";

interface ImageSeoSettings {
  auto_alt: boolean;
  auto_title: boolean;
  auto_caption: boolean;
  auto_description: boolean;
  case: "none" | "lower" | "upper";
  separators: string;
}

const DEFAULTS: ImageSeoSettings = {
  auto_alt: true,
  auto_title: true,
  auto_caption: false,
  auto_description: false,
  case: "none",
  separators: "-_",
};

function asBool(value: string | null | undefined, fallback: boolean): boolean {
  if (value === undefined || value === null || value === "") return fallback;
  return value !== "0";
}

export function ImageSeoSettingsCard() {
  const { toast } = useToast();
  const runMutation = useAdminMutation();
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<ImageSeoSettings>(DEFAULTS);

  const load = useCallback(async () => {
    try {
      const opts = await siteOptionsApi.list();
      setSettings({
        auto_alt: asBool(opts.image_seo_auto_alt, DEFAULTS.auto_alt),
        auto_title: asBool(opts.image_seo_auto_title, DEFAULTS.auto_title),
        auto_caption: asBool(opts.image_seo_auto_caption, DEFAULTS.auto_caption),
        auto_description: asBool(
          opts.image_seo_auto_description,
          DEFAULTS.auto_description,
        ),
        case: (opts.image_seo_case as ImageSeoSettings["case"]) || "none",
        separators: opts.image_seo_filename_separators ?? DEFAULTS.separators,
      });
    } catch {
      toast({ title: "خواندن تنظیمات سئوی تصویر ناموفق بود", variant: "destructive" });
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    const pairs: Array<[string, string]> = [
      ["image_seo_auto_alt", settings.auto_alt ? "1" : "0"],
      ["image_seo_auto_title", settings.auto_title ? "1" : "0"],
      ["image_seo_auto_caption", settings.auto_caption ? "1" : "0"],
      ["image_seo_auto_description", settings.auto_description ? "1" : "0"],
      ["image_seo_case", settings.case],
      ["image_seo_filename_separators", settings.separators],
    ];
    for (const [key, value] of pairs) {
      const result = await runMutation(() => siteOptionsApi.set(key, value), {
        fallbackError: "ذخیره تنظیمات سئوی تصویر ناموفق بود",
      });
      if (!result.ok) {
        setSaving(false);
        toast({ title: result.error, variant: "destructive" });
        return;
      }
    }
    setSaving(false);
    toast({ title: "تنظیمات سئوی تصویر ذخیره شد" });
  };

  const toggles: Array<{
    key: keyof Pick<
      ImageSeoSettings,
      "auto_alt" | "auto_title" | "auto_caption" | "auto_description"
    >;
    label: string;
    hint: string;
  }> = [
    {
      key: "auto_alt",
      label: "پرکردن خودکار متن جایگزین (alt)",
      hint: "وقتی آپلودکننده خالی بگذارد، از نام فایل پر می‌شود. تصویر بدون alt برای جست‌وجوی تصویر نامرئی است.",
    },
    {
      key: "auto_title",
      label: "پرکردن خودکار عنوان",
      hint: "فیلد عنوان فایل، وقتی خالی باشد از نام فایل پر می‌شود.",
    },
    {
      key: "auto_caption",
      label: "پرکردن خودکار زیرنویس",
      hint: "زیرنویس زیر تصویر نمایش داده می‌شود؛ فقط اگر این را می‌خواهید روشن کنید.",
    },
    {
      key: "auto_description",
      label: "پرکردن خودکار توضیحات",
      hint: "متن بلند توضیحات فایل، وقتی خالی باشد از نام فایل پر می‌شود.",
    },
  ];

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <ImageIcon className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">سئوی تصویر</h2>
      </div>

      <p className="mb-4 text-xs text-muted-foreground">
        وقتی فایل خالی باشد، از نام فایل پر می‌شود (مثل{" "}
        <code dir="ltr" className="mx-1">my-product-photo.jpg</code> →
        «my product photo»). متنی که خودتان نوشته‌اید هرگز بازنویسی نمی‌شود —
        فقط جاهای خالی پر می‌شوند.
      </p>

      <div className="space-y-4">
        {toggles.map((t) => (
          <label key={t.key} className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={settings[t.key]}
              onChange={(e) => setSettings({ ...settings, [t.key]: e.target.checked })}
              className="mt-1 h-4 w-4 rounded border-input"
            />
            <span>
              <span className="block text-sm font-medium">{t.label}</span>
              <span className="block text-xs text-muted-foreground">{t.hint}</span>
            </span>
          </label>
        ))}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="image-seo-case">حالت حروف</Label>
            <select
              id="image-seo-case"
              value={settings.case}
              onChange={(e) =>
                setSettings({ ...settings, case: e.target.value as ImageSeoSettings["case"] })
              }
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="none">بدون تغییر</option>
              <option value="lower">کوچک (lowercase)</option>
              <option value="upper">بزرگ (UPPERCASE)</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="image-seo-separators">جداکننده‌های نام فایل</Label>
            <Input
              id="image-seo-separators"
              dir="ltr"
              value={settings.separators}
              onChange={(e) => setSettings({ ...settings, separators: e.target.value })}
              placeholder="-_"
            />
            <p className="text-xs text-muted-foreground">
              این نویسه‌ها در متن تولیدشده به فاصله تبدیل می‌شوند.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-5 flex justify-end">
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 ms-1" />
          {saving ? "در حال ذخیره..." : "ذخیره تنظیمات سئوی تصویر"}
        </Button>
      </div>
    </Card>
  );
}

export default ImageSeoSettingsCard;
