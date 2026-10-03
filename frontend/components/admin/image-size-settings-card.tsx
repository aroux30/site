"use client";

/** Image size settings (WordPress's Media → Settings screen).
 *
 * These seven options were seeded and looked editable, but the sizes were
 * hardcoded in image_processor.py, so changing a value here did nothing. They
 * are now read at generation time; the card says so explicitly, because the
 * sizes only apply to images generated *after* a change unless the operator
 * regenerates.
 */
import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";
import { toPersianDigits } from "@/lib/utils";

const FIELDS = [
  { key: "thumbnail_size_w", label: "عرض بندانگشتی", fallback: "150" },
  { key: "thumbnail_size_h", label: "ارتفاع بندانگشتی", fallback: "150" },
  { key: "medium_size_w", label: "عرض متوسط", fallback: "300" },
  { key: "medium_size_h", label: "ارتفاع متوسط", fallback: "300" },
  { key: "large_size_w", label: "عرض بزرگ", fallback: "1024" },
  { key: "large_size_h", label: "ارتفاع بزرگ", fallback: "1024" },
  // Not a derivative size: this is the ceiling on the *stored original*. A
  // phone camera produces 4000px files, and scaling those down at upload is the
  // difference between a product page that loads on a phone and one that does
  // not. 0 turns it off.
  { key: "big_image_size_threshold", label: "سقف پیکسل تصویر اصلی", fallback: "2560" },
] as const;

/** One operator-registered size, mirroring the backend's parser shape. */
interface CustomSize {
  name: string;
  width: number;
  height: number | null;
  crop: boolean;
}

/** Parse the `custom_image_sizes` option, tolerating anything malformed. */
function parseCustomSizes(raw: string | null | undefined): CustomSize[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (e): e is CustomSize =>
        e && typeof e === "object" && typeof e.name === "string" && typeof e.width === "number",
    );
  } catch {
    return [];
  }
}

export function ImageSizeSettingsCard() {
  const { toast } = useToast();
  const [values, setValues] = useState<Record<string, string>>({});
  const [crop, setCrop] = useState("1");
  // WordPress's add_image_size(): the four built-ins are editable above; a
  // storefront that needs a fifth size (a 2:1 hero, a 4:5 portrait tile) adds
  // it here. Applies to images uploaded after the save — the card's own note
  // says so, and the regeneration button applies them to existing files.
  const [customSizes, setCustomSizes] = useState<CustomSize[]>([]);
  const [newSize, setNewSize] = useState<CustomSize>({
    name: "",
    width: 0,
    height: null,
    crop: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const all = await siteOptionsApi.list();
      const next: Record<string, string> = {};
      for (const f of FIELDS) next[f.key] = all[f.key] ?? f.fallback;
      setValues(next);
      setCrop(all["thumbnail_crop"] ?? "1");
      setCustomSizes(parseCustomSizes(all["custom_image_sizes"]));
    } catch {
      toast({ variant: "destructive", title: "خواندن تنظیمات اندازه تصویر ناموفق بود." });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      for (const f of FIELDS) {
        const raw = (values[f.key] ?? "").trim();
        if (!raw) continue;
        if (!/^\d+$/.test(raw)) {
          toast({
            variant: "destructive",
            title: `«${f.label}» باید عدد باشد.`,
          });
          return;
        }
        await siteOptionsApi.set(f.key, raw);
      }
      await siteOptionsApi.set("thumbnail_crop", crop);
      await siteOptionsApi.set("custom_image_sizes", JSON.stringify(customSizes));
      toast({ title: "اندازه‌ها ذخیره شد." });
    } catch {
      toast({ variant: "destructive", title: "ذخیره اندازه‌ها ناموفق بود." });
    } finally {
      setSaving(false);
    }
  };

  /** Validate and append the draft size. The same rules the server enforces,
   *  surfaced before the round trip so a bad name is not silently dropped. */
  const addCustomSize = () => {
    const name = newSize.name.trim().toLowerCase();
    if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(name)) {
      toast({
        variant: "destructive",
        title: "نام اندازه باید با حرف/عدد شروع شود و فقط a-z، 0-9، _ و - داشته باشد.",
      });
      return;
    }
    const builtIn = ["thumbnail", "medium", "medium_large", "large"];
    if (builtIn.includes(name) || customSizes.some((s) => s.name === name)) {
      toast({ variant: "destructive", title: `اندازه‌ای با نام «${name}» از قبل وجود دارد.` });
      return;
    }
    if (!(newSize.width >= 16 && newSize.width <= 4096)) {
      toast({ variant: "destructive", title: "عرض باید بین ۱۶ و ۴۰۹۶ باشد." });
      return;
    }
    if (newSize.height !== null && !(newSize.height >= 16 && newSize.height <= 4096)) {
      toast({ variant: "destructive", title: "ارتفاع باید بین ۱۶ و ۴۰۹۶ باشد (یا خالی)." });
      return;
    }
    setCustomSizes((prev) => [...prev, { ...newSize, name }]);
    setNewSize({ name: "", width: 0, height: null, crop: false });
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">اندازه‌های تصویر</CardTitle>
        </CardHeader>
        <CardContent>
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <RefreshCw className="h-4 w-4" />
          اندازه‌های تصویر
        </CardTitle>
        <CardDescription>
          این ابعاد هنگام ساخت نسخه‌های کوچک‌تر استفاده می‌شوند. پس از تغییر، برای اعمال روی
          تصاویر موجود یک‌بار دکمهٔ «بازتولید همهٔ تصاویر» را بزنید.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FIELDS.map((f) => (
            <div key={f.key} className="space-y-2">
              <Label htmlFor={f.key} className="text-sm">
                {f.label} (پیکسل)
              </Label>
              <Input
                id={f.key}
                dir="ltr"
                inputMode="numeric"
                value={values[f.key] ?? ""}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [f.key]: e.target.value.replace(/\D/g, "") }))
                }
              />
            </div>
          ))}
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={crop === "1"}
            onChange={(e) => setCrop(e.target.checked ? "1" : "0")}
          />
          برش مربعی بندانگشتی
        </label>

        {/* Registered extra sizes — WordPress's add_image_size(). */}
        <div className="space-y-3 border-t border-border pt-3">
          <div className="text-sm font-medium">اندازه‌های سفارشی</div>
          <p className="text-xs text-muted-foreground">
            اندازه‌های اضافه بر چهار اندازهٔ بالا. هر اندازه یک فایل
            «-نام» کنار فایل اصلی می‌سازد؛ هنگام حذف فایل، خودکار پاک می‌شود.
          </p>

          {customSizes.length > 0 && (
            <ul className="space-y-1.5">
              {customSizes.map((s) => (
                <li
                  key={s.name}
                  className="flex items-center justify-between gap-2 rounded-md border border-border px-2 py-1.5 text-xs"
                >
                  <span className="font-mono" dir="ltr">
                    {s.name} — {s.width}
                    {s.height ? `×${s.height}` : ""}
                    {s.crop ? " (برش)" : ""}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs text-destructive"
                    onClick={() =>
                      setCustomSizes((prev) => prev.filter((x) => x.name !== s.name))
                    }
                  >
                    حذف
                  </Button>
                </li>
              ))}
            </ul>
          )}

          <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto_auto_auto] items-end">
            <div className="grid gap-1">
              <Label htmlFor="cs-name" className="text-[11px]">
                نام (انگلیسی)
              </Label>
              <Input
                id="cs-name"
                dir="ltr"
                className="text-xs"
                value={newSize.name}
                onChange={(e) => setNewSize((p) => ({ ...p, name: e.target.value }))}
                placeholder="hero"
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="cs-w" className="text-[11px]">
                عرض
              </Label>
              <Input
                id="cs-w"
                type="number"
                dir="ltr"
                className="w-20 text-xs"
                value={newSize.width || ""}
                onChange={(e) =>
                  setNewSize((p) => ({ ...p, width: Number(e.target.value) || 0 }))
                }
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="cs-h" className="text-[11px]">
                ارتفاع (خالی = خودکار)
              </Label>
              <Input
                id="cs-h"
                type="number"
                dir="ltr"
                className="w-24 text-xs"
                value={newSize.height ?? ""}
                onChange={(e) =>
                  setNewSize((p) => ({
                    ...p,
                    height: e.target.value === "" ? null : Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <label className="flex items-center gap-1 pb-2 text-xs">
              <input
                type="checkbox"
                checked={newSize.crop}
                onChange={(e) => setNewSize((p) => ({ ...p, crop: e.target.checked }))}
              />
              برش
            </label>
            <Button type="button" variant="outline" size="sm" onClick={addCustomSize}>
              افزودن
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>
            محدودهٔ مجاز: {toPersianDigits("16")} تا {toPersianDigits("4096")} پیکسل
          </span>
        </div>

        <Button onClick={() => void save()} disabled={saving}>
          {saving ? (
            <Loader2 className="ml-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="ml-2 h-4 w-4" />
          )}
          ذخیره اندازه‌ها
        </Button>
      </CardContent>
    </Card>
  );
}
