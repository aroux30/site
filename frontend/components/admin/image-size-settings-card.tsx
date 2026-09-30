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
] as const;

export function ImageSizeSettingsCard() {
  const { toast } = useToast();
  const [values, setValues] = useState<Record<string, string>>({});
  const [crop, setCrop] = useState("1");
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
      toast({ title: "اندازه‌ها ذخیره شد." });
    } catch {
      toast({ variant: "destructive", title: "ذخیره اندازه‌ها ناموفق بود." });
    } finally {
      setSaving(false);
    }
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
