"use client";

/**
 * Watermark settings (WordPress has no core equivalent; this is the panel for
 * the `media_watermark_*` site options).
 *
 * The backend service has been complete for a while — it rewrites every
 * uploaded raster in place so the original, the thumbnail and every variant
 * carry the mark — but the three options were seeded with no UI, so the
 * feature could only be switched on by writing to the options table by hand.
 * This is the switch.
 */

import { useCallback, useEffect, useState } from "react";
import { Loader2, Save, Stamp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";
import { toPersianDigits } from "@/lib/utils";

const POSITIONS = [
  { value: "bottom_right", label: "پایین راست" },
  { value: "center", label: "وسط" },
] as const;

export function WatermarkSettingsCard() {
  const { toast } = useToast();
  const [enabled, setEnabled] = useState(false);
  const [position, setPosition] = useState("bottom_right");
  const [opacity, setOpacity] = useState("0.35");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const all = await siteOptionsApi.list();
      setEnabled(["1", "true", "yes", "on"].includes((all["media_watermark_enabled"] ?? "0").toLowerCase()));
      setPosition(all["media_watermark_position"] ?? "bottom_right");
      setOpacity(all["media_watermark_opacity"] ?? "0.35");
    } catch {
      toast({ variant: "destructive", title: "خواندن تنظیمات واترمارک ناموفق بود." });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    const opacityNum = Number(opacity);
    if (!Number.isFinite(opacityNum) || opacityNum < 0 || opacityNum > 1) {
      toast({
        variant: "destructive",
        title: "شفافیت باید عددی بین ۰ و ۱ باشد (مثلاً ۰٫۳۵).",
      });
      return;
    }
    setSaving(true);
    try {
      await siteOptionsApi.set("media_watermark_enabled", enabled ? "1" : "0");
      await siteOptionsApi.set("media_watermark_position", position);
      await siteOptionsApi.set("media_watermark_opacity", String(opacityNum));
      toast({ title: "تنظیمات واترمارک ذخیره شد." });
    } catch {
      toast({ variant: "destructive", title: "ذخیره تنظیمات واترمارک ناموفق بود." });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">واترمارک تصاویر</CardTitle>
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
          <Stamp className="h-4 w-4" />
          واترمارک تصاویر
        </CardTitle>
        <CardDescription>
          متن واترمارک روی تصاویر جدید (jpg / png / webp) در لحظهٔ آپلود درج
          می‌شود؛ نسخهٔ اصلی، بندانگشتی و همهٔ اندازه‌ها مهر می‌خورند. تصاویر
          موجود دست‌نخورده می‌مانند. SVG و PDF هرگز مهر نمی‌خورند.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="h-4 w-4 rounded border-input"
          />
          فعال‌سازی واترمارک هنگام آپلود
        </label>

        <div className="grid gap-4 sm:grid-cols-2 max-w-xl">
          <div className="grid gap-1.5">
            <Label htmlFor="wm-position" className="text-sm">
              موقعیت
            </Label>
            <select
              id="wm-position"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              disabled={!enabled}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            >
              {POSITIONS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="wm-opacity" className="text-sm">
              شفافیت (۰ تا ۱)
            </Label>
            <Input
              id="wm-opacity"
              dir="ltr"
              inputMode="decimal"
              value={opacity}
              onChange={(e) => setOpacity(e.target.value)}
              disabled={!enabled}
            />
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>
            مقدار پیشنهادی شفافیت: {toPersianDigits("0.35")} — عدد کمتر یعنی
            واترمارک محو‌تر.
          </span>
        </div>

        <Button onClick={() => void save()} disabled={saving}>
          {saving ? (
            <Loader2 className="ml-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="ml-2 h-4 w-4" />
          )}
          ذخیره تنظیمات واترمارک
        </Button>
      </CardContent>
    </Card>
  );
}
