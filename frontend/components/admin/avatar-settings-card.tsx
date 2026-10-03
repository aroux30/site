"use client";

/**
 * Avatar settings card (WordPress parity).
 *
 * P1 "تنظیمات: گزینه‌های آواتار سراسری". The keys ``show_avatars`` /
 * ``avatar_default`` / ``avatar_rating`` did not exist, and the Gravatar helper
 * hardcoded ``d=mp, r=g`` — so a store could not hide avatars, pick a different
 * fallback image, or restrict the gravatar rating. This screen writes all three
 * and the readers in ``shared.content.gravatar`` honour them.
 */

import { useCallback, useEffect, useState } from "react";
import { Save, UserCircle } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi, avatarOptionsApi } from "@/lib/api/wp-parity";
import { useAdminMutation } from "@/lib/api/admin-query";

// Persian labels for the gravatar built-in defaults. Keys are the gravatar `d=`
// values; an unknown stored value is coerced server-side to `mp`.
const DEFAULT_LABELS: Record<string, string> = {
  mp: "مخفی (شخص ناشناس)",
  identicon: "هندسی (Identicon)",
  monsterid: "هیولای تصادفی",
  wavatar: "چهره (Wavatar)",
  retro: "رترو",
  robohash: "ربات (Robohash)",
  blank: "تصویر خالی",
  "404": "بدون تصویر",
};

const RATING_LABELS: Record<string, string> = {
  g: "همه سنین (G)",
  pg: "راهنمایی والدین (PG)",
  r: "محدود (R)",
  x: "بزرگسال (X)",
};

export function AvatarSettingsCard() {
  const { toast } = useToast();
  const runMutation = useAdminMutation();
  const [saving, setSaving] = useState(false);
  const [showAvatars, setShowAvatars] = useState(true);
  const [avatarDefault, setAvatarDefault] = useState("mp");
  const [avatarRating, setAvatarRating] = useState("g");
  const [defaults, setDefaults] = useState<string[]>(Object.keys(DEFAULT_LABELS));
  const [ratings, setRatings] = useState<string[]>(Object.keys(RATING_LABELS));

  const load = useCallback(async () => {
    try {
      const opts = await siteOptionsApi.list();
      setShowAvatars((opts.show_avatars ?? "1") !== "0");
      setAvatarDefault(opts.avatar_default ?? "mp");
      setAvatarRating(opts.avatar_rating ?? "g");
    } catch {
      toast({ title: "خواندن تنظیمات آواتار ناموفق بود", variant: "destructive" });
    }
    // The option lists come from the public endpoint so the picker cannot drift
    // from what the backend will accept (an unknown value is coerced to `mp`).
    try {
      const meta = await avatarOptionsApi.get();
      if (meta.defaults.length) setDefaults(meta.defaults);
      if (meta.ratings.length) setRatings(meta.ratings);
    } catch {
      /* keep the built-in lists */
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    const writes: Array<[string, string]> = [
      ["show_avatars", showAvatars ? "1" : "0"],
      ["avatar_default", avatarDefault],
      ["avatar_rating", avatarRating],
    ];
    for (const [key, value] of writes) {
      const result = await runMutation(() => siteOptionsApi.set(key, value), {
        fallbackError: "ذخیره تنظیمات آواتار ناموفق بود",
      });
      if (!result.ok) {
        setSaving(false);
        toast({ title: result.error, variant: "destructive" });
        return;
      }
    }
    setSaving(false);
    toast({ title: "تنظیمات آواتار ذخیره شد" });
    await load();
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <UserCircle className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">آواتارها</h2>
      </div>

      <p className="mb-4 text-xs text-muted-foreground">
        آواتار دیدگاه‌دهندگان و نویسندگان. اگر کاربر تصویر بارگذاری‌شده داشته باشد از آن
        استفاده می‌شود، در غیر این صورت از گرواتار ایمیل او.
      </p>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label>نمایش آواتارها</Label>
          <button
            type="button"
            onClick={() => setShowAvatars((v) => !v)}
            aria-pressed={showAvatars}
            className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 text-sm"
          >
            <span className={showAvatars ? "" : "text-muted-foreground line-through"}>
              {showAvatars ? "فعال" : "غیرفعال"}
            </span>
          </button>
          <p className="text-xs text-muted-foreground">
            خاموش‌کردن، هم تصویر بارگذاری‌شده و هم گرواتار را در کل فروشگاه پنهان می‌کند.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="avatar-default">آواتار پیش‌فرض</Label>
          <select
            id="avatar-default"
            value={avatarDefault}
            onChange={(e) => setAvatarDefault(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            {defaults.map((key) => (
              <option key={key} value={key}>
                {DEFAULT_LABELS[key] ?? key}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted-foreground">تصویری که برای کاربران بدون گرواتار نمایش داده می‌شود.</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="avatar-rating">حداکثر رده‌بندی</Label>
          <select
            id="avatar-rating"
            value={avatarRating}
            onChange={(e) => setAvatarRating(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            {ratings.map((key) => (
              <option key={key} value={key}>
                {RATING_LABELS[key] ?? key}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted-foreground">بالاترین رده‌بندی محتوایی که برای آواتار نمایش داده می‌شود.</p>
        </div>
      </div>

      <div className="mt-5 flex justify-end">
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 ms-1" />
          {saving ? "در حال ذخیره..." : "ذخیره تنظیمات آواتار"}
        </Button>
      </div>
    </Card>
  );
}

export default AvatarSettingsCard;