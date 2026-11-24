"use client";

import React, { useState, useEffect } from "react";
import { Paintbrush, Check, RotateCcw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useBuilderStore } from "@/stores/builder-store";
import { toValidHexColor } from "@/lib/builder/color-utils";

function toAsciiHex(val: string): string {
  if (!val) return "";
  return val.replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d).toString()).trim();
}

interface GlobalStylesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const COLOR_PRESETS = [
  { name: "زمردی (Emerald)", hex: "#059669" },
  { name: "یشمی روشن", hex: "#10b981" },
  { name: "فیروزه‌ای (Teal)", hex: "#0d9488" },
  { name: "آبی درباری", hex: "#2563eb" },
  { name: "بنفش سلطنتی", hex: "#7c3aed" },
  { name: "یاقوتی (Rose)", hex: "#e11d48" },
  { name: "کهربایی (Amber)", hex: "#f59e0b" },
  { name: "زغالی (Slate)", hex: "#334155" },
];

const RADIUS_OPTIONS = [
  { label: "بدون گردی (0px)", value: "0px" },
  { label: "کوچک (6px)", value: "6px" },
  { label: "متوسط (10px)", value: "10px" },
  { label: "استاندارد (12px)", value: "12px" },
  { label: "بزرگ (16px)", value: "16px" },
  { label: "خیلی بزرگ (24px)", value: "24px" },
];

export function GlobalStylesDialog({ open, onOpenChange }: GlobalStylesDialogProps) {
  const ast = useBuilderStore((s) => s.ast);
  const updateGlobalStyles = useBuilderStore((s) => s.updateGlobalStyles);

  const globalStyles = ast.globalStyles || {};

  const [primary, setPrimary] = useState<string>(
    String(globalStyles.primaryColor || "#059669")
  );
  const [secondary, setSecondary] = useState<string>(
    String(globalStyles.secondaryColor || "#0d9488")
  );
  const [radius, setRadius] = useState<string>(
    String(globalStyles.borderRadius || "12px")
  );
  const [fontFamily, setFontFamily] = useState<string>(
    String(globalStyles.fontFamily || "vazirmatn")
  );
  const [textColor, setTextColor] = useState<string>(
    String(globalStyles.textColor || "")
  );
  const [backgroundColor, setBackgroundColor] = useState<string>(
    String(globalStyles.backgroundColor || "")
  );

  useEffect(() => {
    if (open) {
      setPrimary(String(globalStyles.primaryColor || "#059669"));
      setSecondary(String(globalStyles.secondaryColor || "#0d9488"));
      setRadius(String(globalStyles.borderRadius || "12px"));
      setFontFamily(String(globalStyles.fontFamily || "vazirmatn"));
      setTextColor(String(globalStyles.textColor || ""));
      setBackgroundColor(String(globalStyles.backgroundColor || ""));
    }
  }, [open, globalStyles.primaryColor, globalStyles.secondaryColor, globalStyles.borderRadius, globalStyles.fontFamily, globalStyles.textColor, globalStyles.backgroundColor]);

  const handleSave = () => {
    updateGlobalStyles({
      primaryColor: primary,
      secondaryColor: secondary,
      borderRadius: radius,
      fontFamily,
      textColor: textColor || undefined,
      backgroundColor: backgroundColor || undefined,
    });
    onOpenChange(false);
  };

  const handleResetToSiteTheme = () => {
    setPrimary("#059669");
    setSecondary("#0d9488");
    setRadius("12px");
    setFontFamily("vazirmatn");
    setTextColor("");
    setBackgroundColor("");
    updateGlobalStyles({
      primaryColor: undefined,
      secondaryColor: undefined,
      borderRadius: undefined,
      fontFamily: undefined,
      textColor: undefined,
      backgroundColor: undefined,
    });
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" dir="rtl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base font-bold">
            <Paintbrush className="w-4 h-4 text-primary" />
            <span>تنظیمات استایل سراسری برگه (Design Tokens)</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2 text-xs">
          {/* Primary Brand Color */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">رنگ اصلی برند (Primary Color)</Label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={toValidHexColor(primary, "#059669")}
                onChange={(e) => setPrimary(e.target.value)}
                className="w-8 h-8 rounded-lg cursor-pointer border border-border"
              />
              <Input
                value={primary}
                onChange={(e) => setPrimary(toAsciiHex(e.target.value))}
                className="h-8 font-mono text-xs"
                placeholder="#059669"
                dir="ltr"
              />
            </div>
            <div className="flex flex-wrap gap-1 mt-1">
              {COLOR_PRESETS.map((c) => (
                <button
                  key={c.hex}
                  type="button"
                  onClick={() => setPrimary(c.hex)}
                  className="w-5 h-5 rounded-full border border-border shadow-xs transition hover:scale-110 flex items-center justify-center"
                  style={{ backgroundColor: c.hex }}
                  title={c.name}
                >
                  {primary.toLowerCase() === c.hex.toLowerCase() && (
                    <Check className="w-3 h-3 text-white drop-shadow" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Secondary Accent Color */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">رنگ مکمل / ثانویه (Secondary Color)</Label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={toValidHexColor(secondary, "#0d9488")}
                onChange={(e) => setSecondary(e.target.value)}
                className="w-8 h-8 rounded-lg cursor-pointer border border-border"
              />
              <Input
                value={secondary}
                onChange={(e) => setSecondary(toAsciiHex(e.target.value))}
                className="h-8 font-mono text-xs"
                placeholder="#0d9488"
                dir="ltr"
              />
            </div>
            <div className="flex flex-wrap gap-1 mt-1">
              {COLOR_PRESETS.map((c) => (
                <button
                  key={c.hex}
                  type="button"
                  onClick={() => setSecondary(c.hex)}
                  className="w-5 h-5 rounded-full border border-border shadow-xs transition hover:scale-110 flex items-center justify-center"
                  style={{ backgroundColor: c.hex }}
                  title={c.name}
                >
                  {secondary.toLowerCase() === c.hex.toLowerCase() && (
                    <Check className="w-3 h-3 text-white drop-shadow" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Base Border Radius */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">شعاع گردی پیش‌فرض (Border Radius)</Label>
            <Select value={radius} onValueChange={setRadius}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RADIUS_OPTIONS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Font Family */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">تایپوگرافی سراسری</Label>
            <Select value={fontFamily} onValueChange={setFontFamily}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="vazirmatn">فونت وزیرمتن (Vazirmatn استاندارد)</SelectItem>
                <SelectItem value="system-ui">فونت سیستمی (System UI)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Text Color Token */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">رنگ متن پیش‌فرض سراسری</Label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={toValidHexColor(textColor, "#09090b")}
                onChange={(e) => setTextColor(e.target.value)}
                className="w-8 h-8 rounded-lg cursor-pointer border border-border"
              />
              <Input
                value={textColor}
                onChange={(e) => setTextColor(toAsciiHex(e.target.value))}
                className="h-8 font-mono text-xs"
                placeholder="اختیاری (مثلاً #09090b)"
                dir="ltr"
              />
            </div>
          </div>

          {/* Background Color Token */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">رنگ پس‌زمینه سراسری برگه</Label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={toValidHexColor(backgroundColor, "#ffffff")}
                onChange={(e) => setBackgroundColor(e.target.value)}
                className="w-8 h-8 rounded-lg cursor-pointer border border-border"
              />
              <Input
                value={backgroundColor}
                onChange={(e) => setBackgroundColor(toAsciiHex(e.target.value))}
                className="h-8 font-mono text-xs"
                placeholder="اختیاری (مثلاً #ffffff)"
                dir="ltr"
              />
            </div>
          </div>
        </div>

        <DialogFooter className="flex flex-row items-center justify-between gap-2 pt-3 border-t">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            data-testid="reset-global-styles-btn"
            onClick={handleResetToSiteTheme}
            className="text-muted-foreground hover:text-foreground text-xs gap-1 border border-border/60"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>بازنشانی به تم سایت</span>
          </Button>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              انصراف
            </Button>
            <Button size="sm" data-testid="save-global-styles-btn" onClick={handleSave} className="bg-primary text-primary-foreground font-bold">
              اعمال تغییرات
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
